"""End-to-end checks with a local Xray client (socks -> curl IP-echo). Inbounds are discovered from the
node's generated config: the REALITY inbound by security, CDN inbounds by network (ws/httpupgrade/grpc/xhttp + tls)."""
import json,os,subprocess,time,socket,tempfile,logging,random
from common import cfg
HERE=os.path.dirname(os.path.abspath(__file__)); XRAY=os.path.join(HERE,'bin','xray')
log=logging.getLogger('vpn')
def ensure_xray(version='26.9.30'):
    if os.path.exists(XRAY): return
    os.makedirs(os.path.dirname(XRAY),exist_ok=True); z=XRAY+'.zip'
    subprocess.run(['curl','-sSL','-o',z,f'https://github.com/XTLS/Xray-core/releases/download/v{version}/Xray-linux-64.zip'],check=True)
    import zipfile; zipfile.ZipFile(z).extract('xray',os.path.dirname(XRAY)); os.chmod(XRAY,0o755); os.remove(z)
def load_inbounds(node):
    """Returns {'reality': inbound, 'ws': inbound, 'grpc': ..., 'xhttp': ..., 'httpupgrade': ...}, reality_public_key."""
    cfgj=json.loads(node.run('cat /usr/local/x-ui/bin/config.json',quiet=True)); ib={}; pub=None
    for i in cfgj['inbounds']:
        s=i.get('streamSettings') or {}
        if i.get('protocol')!='vless' or not i['settings'].get('clients'): continue
        if s.get('security')=='reality': ib['reality']=i
        elif s.get('security')=='tls': ib.setdefault(s.get('network'),i)
    if 'reality' in ib:
        out=subprocess.run([XRAY,'x25519','-i',ib['reality']['streamSettings']['realitySettings']['privateKey']],capture_output=True,text=True).stdout
        pub=[l.split(':',1)[1].strip() for l in out.splitlines() if 'PublicKey' in l][0]
    return ib,pub
def _outbound(i,addr,sni,pub=None,ech=None):
    s=i['streamSettings']; n=s['network']; host=cfg('CDN_HOST')
    st={"network":n,"security":s['security']}
    if s['security']=='reality':
        r=s['realitySettings']; st["realitySettings"]={"serverName":r['serverNames'][0],"fingerprint":"chrome","publicKey":pub,"shortId":r['shortIds'][0],"spiderX":"/"}
    else:
        t={"serverName":sni,"alpn":s['tlsSettings'].get('alpn') or ["h2","http/1.1"]}
        if ech: t.update(echConfigList=ech,echForceQuery="full")
        else: t["fingerprint"]="chrome"
        st["tlsSettings"]=t
    if n=='xhttp':
        st["xhttpSettings"]={"path":s['xhttpSettings']['path'],"mode":"auto"}
        if s['security']!='reality': st["xhttpSettings"]["host"]=host
    if n=='ws': st["wsSettings"]={"path":s['wsSettings']['path'],"host":host}
    if n=='httpupgrade': st["httpupgradeSettings"]={"path":s['httpupgradeSettings']['path'],"host":host}
    if n=='grpc': st["grpcSettings"]={"serviceName":s['grpcSettings']['serviceName'],"authority":host}
    return {"protocol":"vless","settings":{"vnext":[{"address":addr,"port":i['port'],"users":[{"id":i['settings']['clients'][0]['id'],"encryption":"none"}]}]},"streamSettings":st}
def run_test(inbound,addr,sni=None,pub=None,ech=None,expect_ip=None,label=''):
    port=random.randint(20000,40000)
    c={"log":{"loglevel":"warning"},"inbounds":[{"port":port,"listen":"127.0.0.1","protocol":"socks"}],"outbounds":[_outbound(inbound,addr,sni,pub,ech)]}
    fd,path=tempfile.mkstemp(suffix='.json'); os.write(fd,json.dumps(c).encode()); os.close(fd); os.chmod(path,0o600)
    p=subprocess.Popen([XRAY,'run','-c',path],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        time.sleep(2); ok=False; ip=''
        for _ in range(3):
            r=subprocess.run(['curl','-s','-m','20','--socks5-hostname',f'127.0.0.1:{port}','https://api.ipify.org'],capture_output=True,text=True)
            ip=r.stdout.strip()
            if ip and (expect_ip is None or ip==expect_ip): ok=True; break
            time.sleep(3)
        log.info('xray test %-26s -> %s',label,'OK' if ok else f'FAIL (exit={ip or "-"})'); return ok
    finally:
        p.terminate(); p.wait(); os.remove(path)
def tcp_ports(ip,ports,timeout=5):
    res={}
    for pt in ports:
        try: socket.create_connection((ip,pt),timeout=timeout).close(); res[pt]=True
        except Exception: res[pt]=False
    return res
