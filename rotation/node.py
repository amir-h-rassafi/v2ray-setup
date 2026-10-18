"""SSH helpers (paramiko)."""
import os,time,socket,paramiko,logging
from common import cfg
KEY=os.path.expanduser(cfg('SSH_KEY'))
log=logging.getLogger('vpn')
class Node:
    def __init__(self,ip,timeout=20):
        self.ip=ip; k=paramiko.Ed25519Key.from_private_key_file(KEY)
        self.c=paramiko.SSHClient(); self.c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.c.connect(ip,username='root',pkey=k,timeout=timeout,allow_agent=False,look_for_keys=False,banner_timeout=30,auth_timeout=30)
        self.c.get_transport().set_keepalive(15)
    def run(self,cmd,check=True,timeout=900,stdin=None,quiet=False):
        i,o,e=self.c.exec_command(cmd,timeout=timeout)
        if stdin is not None: i.write(stdin); i.channel.shutdown_write()
        out=o.read().decode(errors='replace'); err=e.read().decode(errors='replace'); rc=o.channel.recv_exit_status()
        if not quiet: log.debug('[%s] $ %s -> rc=%s',self.ip,cmd[:200],rc)
        if check and rc!=0: raise RuntimeError(f'[{self.ip}] cmd failed rc={rc}: {cmd[:120]} :: {err[-600:]}')
        return out
    def get(self,remote,local): self.c.open_sftp().get(remote,local)
    def put(self,local,remote): self.c.open_sftp().put(local,remote)
    def close(self): self.c.close()
def wait_ssh(ip,deadline_s=600):
    t0=time.time(); last=None
    while time.time()-t0<deadline_s:
        try:
            s=socket.create_connection((ip,22),timeout=5); s.close()
            n=Node(ip); n.run('true'); return n
        except Exception as e: last=e; time.sleep(5)
    raise TimeoutError(f'SSH to {ip} not ready after {deadline_s}s: {last}')
