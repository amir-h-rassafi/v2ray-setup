#!/usr/bin/env python3
"""Rotate the single VPN node to the next provider region (UpCloud + Cloudflare APIs, no browser).

preflight -> backup -> create node in next zone -> provision from backup -> direct health checks ->
final sync (stop x-ui on old node, copy fresh DB) -> re-check -> switch DNS (DIRECT_HOST DNS-only,
CDN_HOST proxied) -> verify via DoH + through the CDN (Xray tests + subscription fetch) ->
delete old node + storage -> delete orphan storages -> summary.

Failure before the DNS switch: delete the NEW node, restart x-ui on the old one (old node untouched).
Failure during post-switch verification: revert DNS, restart old x-ui, delete the NEW node.
Usage: rotate.py [--zone ZONE] [--dry-run]"""
import os,sys,time,json,logging,argparse,base64,subprocess,urllib.request,tarfile
HERE=os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0,HERE)
from common import uc,cf,cfg,ApiError
from node import Node,wait_ssh
import backup as B, xraytest as X

ROTATION=cfg('ROTATION').split(','); PLAN=cfg('PLAN'); DISK_GB=int(cfg('DISK_GB','10'))
PREFIX=cfg('NODE_PREFIX'); ZONE_ID=cfg('CF_ZONE_ID'); DIRECT=cfg('DIRECT_HOST'); CDN=cfg('CDN_HOST')
CLEAN_IP=cfg('CLEAN_EDGE_IP'); ECH=cfg('ECH_CONFIG')
TEMPLATE_TITLES=['Ubuntu Server 26.04','Ubuntu Server 24.04 LTS (Noble']
log=logging.getLogger('vpn'); T={}; t_start=time.time()
def step(name): T[name]=round(time.time()-t_start,1); log.info('==== %s (t+%ss)',name,T[name])

# ---------- UpCloud ----------
def servers(): return uc('GET','/server')['servers']['server']
def server(uuid): return uc('GET',f'/server/{uuid}')['server']
def public_ipv4(d):
    for itf in d['networking']['interfaces']['interface']:
        if itf['type']=='public':
            for a in itf['ip_addresses']['ip_address']:
                if a['family']=='IPv4': return a['address']
def wait_state(uuid,state,timeout=600):
    t0=time.time()
    while time.time()-t0<timeout:
        if server(uuid)['state']==state: return
        time.sleep(5)
    raise TimeoutError(f'server {uuid[:8]} not {state} after {timeout}s')
def delete_server(uuid,label=''):
    d=server(uuid)
    if d['state']!='stopped':
        if d['state']=='maintenance': wait_state(uuid,'started',300)
        uc('POST',f'/server/{uuid}/stop',{"stop_server":{"stop_type":"hard","timeout":"60"}}); wait_state(uuid,'stopped',300)
    uc('DELETE',f'/server/{uuid}?storages=1&backups=delete')
    for _ in range(60):
        if uuid not in [s['uuid'] for s in servers()]: break
        time.sleep(5)
    log.info('deleted server %s %s (with storages)',uuid[:8],label)
def delete_orphans(keep=()):
    for st in uc('GET','/storage/private')['storages']['storage']:
        if st['uuid'] in keep: continue
        d=uc('GET',f"/storage/{st['uuid']}")['storage']
        if d.get('servers',{}).get('server'): continue
        for _ in range(60):
            if uc('GET',f"/storage/{d['uuid']}")['storage']['state']=='online': break
            time.sleep(5)
        uc('DELETE',f"/storage/{d['uuid']}?backups=delete"); log.info('deleted orphan storage %s',d['title'])
def template_uuid():
    tl=uc('GET','/storage/template')['storages']['storage']
    for want in TEMPLATE_TITLES:
        for t in tl:
            if t['title'].startswith(want): return t['uuid'],t['title']
    raise RuntimeError('no Ubuntu template found')
def create_server(zone,keys):
    tpl,title=template_uuid(); host=PREFIX+zone
    body={"server":{"zone":zone,"title":host,"hostname":host,"plan":PLAN,"metadata":"yes",
        "storage_devices":{"storage_device":[{"action":"clone","storage":tpl,"title":host+"-disk","size":DISK_GB,"tier":"standard"}]},
        "networking":{"interfaces":{"interface":[{"ip_addresses":{"ip_address":[{"family":"IPv4"}]},"type":"public"},
                                                   {"ip_addresses":{"ip_address":[{"family":"IPv6"}]},"type":"public"},
                                                   {"ip_addresses":{"ip_address":[{"family":"IPv4"}]},"type":"utility"}]}},
        "login_user":{"username":"root","create_password":"no","ssh_keys":{"ssh_key":keys}}}}
    d=uc('POST','/server',body,timeout=120)['server']; log.info('created %s in %s (%s, %s)',d['uuid'][:8],zone,PLAN,title)
    return d['uuid']

# ---------- DNS ----------
def records(): return {r['name']:r for r in cf('GET',f'/zones/{ZONE_ID}/dns_records?type=A&per_page=100')['result']}
def set_record(name,ip,proxied):
    r=records()[name]
    if r['content']==ip and r['proxied']==proxied: return
    cf('PATCH',f"/zones/{ZONE_ID}/dns_records/{r['id']}",{"content":ip,"proxied":proxied,"ttl":1}); log.info('DNS %s updated (proxied=%s)',name,proxied)
def doh(name):
    req=urllib.request.Request(f'https://cloudflare-dns.com/dns-query?name={name}&type=A',headers={'accept':'application/dns-json'})
    return [a['data'] for a in json.loads(urllib.request.urlopen(req,timeout=15).read()).get('Answer',[]) if a['type']==1]

# ---------- provisioning ----------
def listening_ports(n):
    """All TCP ports Xray/x-ui should expose, derived from the node's own config + sub server."""
    c=json.loads(n.run('cat /usr/local/x-ui/bin/config.json',quiet=True))
    return sorted({22}|{i['port'] for i in c['inbounds'] if i.get('listen','') not in ('127.0.0.1',)})
def wait_listen(n,timeout=90):
    t0=time.time(); miss=None
    while time.time()-t0<timeout:
        try:
            out=n.run('ss -tlnH',quiet=True); miss=[p for p in listening_ports(n) if f':{p} ' not in out]
            if not miss and n.run('systemctl is-active x-ui',check=False,quiet=True).strip()=='active': return
        except Exception as e: miss=str(e)
        time.sleep(3)
    raise RuntimeError(f'x-ui not ready on {n.ip}: {miss}')
def provision(n,tarpath):
    n.run('cloud-init status --wait >/dev/null 2>&1 || true',timeout=900)
    pk=sorted(set(tarfile.open(tarpath).extractfile('root/xui-meta/packages.txt').read().decode().split())|{'fail2ban','socat','cron'})
    n.run('export DEBIAN_FRONTEND=noninteractive; apt-get -o DPkg::Lock::Timeout=600 update -q >/dev/null && '
          f'apt-get -o DPkg::Lock::Timeout=600 install -y -q {" ".join(pk)} >/dev/null',timeout=1200)
    n.put(tarpath,'/root/restore.tar.gz')
    n.run('systemctl stop x-ui 2>/dev/null; cd / && tar -xzf /root/restore.tar.gz && '
          'install -d -m755 /etc/x-ui /var/log/x-ui && touch /var/log/x-ui/3xipl.log /var/log/x-ui/3xipl-banned.log /var/log/x-ui/3xipl-ap.log && '
          'rm -f /etc/x-ui/x-ui.db-wal /etc/x-ui/x-ui.db-shm && install -m600 /root/xui-meta/x-ui.db /etc/x-ui/x-ui.db && '
          'chown root:crontab /var/spool/cron/crontabs/root 2>/dev/null; chmod 600 /var/spool/cron/crontabs/root 2>/dev/null; '
          'chmod 700 /root/.ssh; chmod 600 /root/.ssh/authorized_keys; '
          'systemctl daemon-reload && systemctl enable --now x-ui && systemctl restart cron && '
          '(systemctl enable fail2ban && systemctl restart fail2ban || true) && rm -f /root/restore.tar.gz')
    wait_listen(n)
def restore_db_only(n,tarpath):
    n.put(tarpath,'/root/final.tar.gz')
    n.run('systemctl stop x-ui && cd / && tar -xzf /root/final.tar.gz root/xui-meta/x-ui.db && rm -f /etc/x-ui/x-ui.db-wal /etc/x-ui/x-ui.db-shm && '
          'install -m600 /root/xui-meta/x-ui.db /etc/x-ui/x-ui.db && systemctl start x-ui && rm -f /root/final.tar.gz')
    wait_listen(n)

# ---------- checks ----------
def direct_health(n,ip):
    ports=X.tcp_ports(ip,listening_ports(n)); log.info('ports: %s',ports)
    if not all(ports.values()): raise RuntimeError(f'closed ports: {[p for p,v in ports.items() if not v]}')
    ib,pub=X.load_inbounds(n)
    # Direct TLS tests use the certificate's own name (DIRECT_HOST); the CDN host header is still sent.
    # Tip: if your test machine's egress re-routes :443 by SNI, keep direct tests on non-443 inbounds.
    tests=[(k,v) for k,v in ib.items() if k!='reality' and v['port']!=443]
    ok=all(X.run_test(v,ip,sni=DIRECT,expect_ip=ip,label=f'{k} direct') for k,v in tests)
    if 'reality' in ib: ok=ok and X.run_test(ib['reality'],ip,pub=pub,expect_ip=ip,label='reality direct')
    if not ok: raise RuntimeError('direct xray tests failed')
    return ib
def cdn_health(n,ip,ib):
    edge=doh(CDN); assert edge,'no DoH answer for CDN host'
    tests=[(k,v,edge[0],None) for k,v in ib.items() if k!='reality']+[(k,v,CLEAN_IP,ECH) for k,v in ib.items() if k=='grpc']
    ok=all(X.run_test(v,addr,sni=CDN,ech=e,expect_ip=ip,label=f'{k} via CDN'+(' +ECH' if e else '')) for k,v,addr,e in tests)
    if not ok: raise RuntimeError('xray tests through the CDN failed')
    sp,(sid,uuid)=json.loads(n.run('python3 -c "import sqlite3,json;db=sqlite3.connect(\'file:/etc/x-ui/x-ui.db?mode=ro\',uri=True);'
        'print(json.dumps([db.execute(\'select value from settings where key=\\"subPath\\"\').fetchone()[0],db.execute(\'select sub_id,uuid from clients order by id limit 1\').fetchone()]))"',quiet=True))
    port=int(n.run('python3 -c "import sqlite3;r=sqlite3.connect(\'file:/etc/x-ui/x-ui.db?mode=ro\',uri=True).execute(\'select value from settings where key=\\"subPort\\"\').fetchone();print(r[0] if r else 2096)"',quiet=True))
    r=subprocess.run(['curl','-s','-m','20','--resolve',f'{CDN}:{port}:{edge[0]}','-w','\n%{http_code}',f'https://{CDN}:{port}{sp}{sid}'],capture_output=True,text=True).stdout
    body,_,code=r.rpartition('\n')
    links=[l for l in base64.b64decode(body+'==').decode(errors='replace').splitlines() if '://' in l] if code=='200' else []
    if not (links and all(uuid in l for l in links if l.startswith('vless://'))): raise RuntimeError(f'subscription via CDN failed (HTTP {code})')
    log.info('subscription via CDN: HTTP 200, %d links',len(links))

# ---------- main ----------
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--zone'); ap.add_argument('--dry-run',action='store_true'); a=ap.parse_args()
    os.makedirs(f'{HERE}/logs',exist_ok=True); ts=time.strftime('%Y%m%d-%H%M%S',time.gmtime())
    fmt=logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    for h in (logging.FileHandler(f'{HERE}/logs/rotate-{ts}.log'),logging.StreamHandler()): h.setFormatter(fmt); log.addHandler(h)
    log.setLevel(logging.INFO); logging.getLogger('paramiko').setLevel(logging.WARNING); X.ensure_xray()
    step('preflight')
    old_ip=records()[DIRECT]['content']; allsrv=servers()
    cur=[s for s in allsrv if public_ipv4(server(s['uuid']))==old_ip]
    if len(cur)!=1: raise SystemExit('cannot identify the current node from DNS')
    cur=cur[0]; old_uuid,old_zone,old_host=cur['uuid'],cur['zone'],cur['hostname']; log.info('current: %s (%s)',old_host,old_zone)
    for s in allsrv:
        if s['uuid']==old_uuid: continue
        if not s['hostname'].startswith(PREFIX): raise SystemExit(f"unexpected server {s['hostname']}; aborting")
        log.warning('leftover %s from a previous run -> deleting',s['hostname']); delete_server(s['uuid'],s['hostname'])
    delete_orphans()
    i=ROTATION.index(old_zone)+1 if old_zone in ROTATION else 0
    zones=[z for z in dict.fromkeys(([a.zone] if a.zone else [])+ROTATION[i:]+ROTATION[:i]) if z!=old_zone]
    log.info('zone candidates: %s',zones[:4])
    if a.dry_run: return
    step('backup'); tar=B.snapshot(old_ip)
    keys=[l.strip() for l in tarfile.open(tar).extractfile('root/.ssh/authorized_keys').read().decode().splitlines() if l.strip().startswith('ssh-')]
    mypub=open(os.path.expanduser(cfg('SSH_KEY'))+'.pub').read().strip()
    if not any(mypub.split()[1] in k for k in keys): keys.append(mypub)
    step('create'); new_uuid=new_zone=None
    for z in zones:
        try: new_uuid=create_server(z,keys); new_zone=z; break
        except ApiError as e: log.warning('create in %s failed: %s',z,str(e)[:200])
    if not new_uuid: raise SystemExit('could not create a server in any zone')
    old_stopped=dns_switched=False; tar2=None; new_ip=None
    try:
        wait_state(new_uuid,'started',900); new_ip=public_ipv4(server(new_uuid)); log.info('new node in %s',new_zone)
        step('ssh'); n=wait_ssh(new_ip,900)
        step('provision'); provision(n,tar)
        step('health-direct'); direct_health(n,new_ip)
        step('final-sync'); old_stopped=True; tar2=B.snapshot(old_ip,stop_xui=True); restore_db_only(n,tar2)
        ib=direct_health(n,new_ip)
        step('dns-switch'); dns_switched=True
        set_record(DIRECT,new_ip,False); set_record(CDN,new_ip,True)
        step('verify-cdn'); t0=time.time()
        while doh(DIRECT)!=[new_ip]:
            if time.time()-t0>360: raise RuntimeError('DoH still shows the old address')
            time.sleep(10)
        time.sleep(5); cdn_health(n,new_ip,ib); n.close()
    except BaseException as e:
        log.error('FAILED: %s -> rolling back',e)
        try:
            if dns_switched: set_record(DIRECT,old_ip,False); set_record(CDN,old_ip,True)
            if old_stopped: Node(old_ip).run('systemctl start x-ui')
        finally: delete_server(new_uuid,'(new, rollback)')
        log.error('rollback complete; old node untouched'); raise
    step('delete-old'); delete_server(old_uuid,old_host)
    delete_orphans(keep=[s['storage'] for s in server(new_uuid)['storage_devices']['storage_device']])
    step('done')
    srv=[(s['hostname'],s['zone'],s['state']) for s in servers()]
    sto=[(s['title'],s['zone']) for s in uc('GET','/storage/private')['storages']['storage']]
    summary={'old_zone':old_zone,'new_zone':new_zone,'timings_s':T,'total_s':round(time.time()-t_start,1),'servers':srv,'storages':sto}
    json.dump(summary,open(f'{HERE}/logs/summary-{ts}.json','w'),indent=1); log.info('SUMMARY %s',json.dumps(summary))
    if len(srv)!=1 or len(sto)!=1: log.error('expected exactly one server and one storage!')
if __name__=='__main__': main()
