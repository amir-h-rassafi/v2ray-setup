#!/usr/bin/env python3
"""Snapshot a node's 3x-ui state into BACKUP_DIR/<ts>-<ip>.tar.gz (keeps the last BACKUP_KEEP).
Usage: backup.py [node_ip]   (default: current A record of DIRECT_HOST)"""
import os,sys,time,glob,logging
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from common import cfg,cf
from node import Node
BK=os.path.abspath(cfg('BACKUP_DIR','./backups')); KEEP=int(cfg('BACKUP_KEEP','14'))
log=logging.getLogger('vpn')
PATHS=['etc/x-ui','root/cert','root/.acme.sh','usr/local/x-ui','etc/systemd/system/x-ui.service','usr/bin/x-ui','etc/default/x-ui',
       'etc/fail2ban/jail.d','etc/fail2ban/filter.d/3x-ipl.conf','etc/fail2ban/action.d/3x-ipl.conf','etc/fail2ban/jail.local',
       'etc/sysctl.d','root/.ssh/authorized_keys','var/spool/cron/crontabs/root','root/xui-meta']
REMOTE_SNAPSHOT=r'''
set -e
rm -rf /root/xui-meta && mkdir -p /root/xui-meta
python3 - <<'PY'
import sqlite3
src=sqlite3.connect('/etc/x-ui/x-ui.db',timeout=30); dst=sqlite3.connect('/root/xui-meta/x-ui.db')
src.backup(dst); dst.close(); src.close()
assert sqlite3.connect('/root/xui-meta/x-ui.db').execute('pragma integrity_check').fetchone()[0]=='ok'
PY
{ /usr/local/x-ui/x-ui -v 2>&1 | head -1; /usr/local/x-ui/bin/xray-linux-amd64 version 2>&1 | head -1; . /etc/os-release; echo "$PRETTY_NAME"; date -u +%FT%TZ; } > /root/xui-meta/versions.txt
dpkg-query -W -f='${Package}\n' fail2ban socat cron 2>/dev/null > /root/xui-meta/packages.txt || true
'''
def snapshot(ip,stop_xui=False):
    """stop_xui=True stops x-ui first (final sync: traffic counters are flushed)."""
    os.makedirs(BK,exist_ok=True); os.chmod(BK,0o700)
    n=Node(ip)
    try:
        if stop_xui: n.run('systemctl stop x-ui')
        n.run(REMOTE_SNAPSHOT)
        exist=n.run('cd / && for p in '+' '.join(PATHS)+'; do [ -e "$p" ] && echo "$p"; done; true').split()
        ts=time.strftime('%Y%m%d-%H%M%S',time.gmtime()); rpath=f'/root/xui-backup-{ts}.tar.gz'
        n.run(f"cd / && tar --exclude=etc/x-ui/x-ui.db --exclude=etc/x-ui/x-ui.db-wal --exclude=etc/x-ui/x-ui.db-shm -czf {rpath} {' '.join(exist)}")
        local=f'{BK}/{ts}-{ip}.tar.gz'; n.get(rpath,local); os.chmod(local,0o600); n.run(f'rm -f {rpath}')
    finally: n.close()
    for f in sorted(glob.glob(f'{BK}/*.tar.gz'))[:-KEEP]: os.remove(f)
    log.info('backup saved %s (%.1f MB)',local,os.path.getsize(local)/1e6)
    return local
if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s'); logging.getLogger('paramiko').setLevel(logging.WARNING)
    ip=sys.argv[1] if len(sys.argv)>1 else cf('GET',f"/zones/{cfg('CF_ZONE_ID')}/dns_records?type=A&name={cfg('DIRECT_HOST')}")['result'][0]['content']
    print(snapshot(ip))
