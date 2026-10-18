"""Config + thin API clients for UpCloud and Cloudflare (stdlib only)."""
import json,os,base64,urllib.request,urllib.error
HERE=os.path.dirname(os.path.abspath(__file__))
def _load_env(path):
    d={}
    if os.path.exists(path):
        for l in open(path):
            l=l.strip()
            if l and not l.startswith('#') and '=' in l:
                k,v=l.split('=',1); d[k.strip()]=v.split('#',1)[0].strip()
    return d
CFG={**_load_env(os.path.join(HERE,'config.env')),**{k:v for k,v in os.environ.items() if k.isupper()}}
def cfg(key,default=None):
    v=CFG.get(key,default)
    if v is None: raise SystemExit(f'missing config {key} (see config.example.env)')
    return v
def _kv(p):
    return dict(l.strip().split('=',1) for l in open(os.path.expanduser(p)) if '=' in l)
class ApiError(Exception): pass
def _req(url,method,headers,body=None,timeout=60):
    data=json.dumps(body).encode() if body is not None else None
    r=urllib.request.Request(url,data=data,method=method,headers={**headers,'Content-Type':'application/json','Accept':'application/json'})
    try:
        raw=urllib.request.urlopen(r,timeout=timeout).read(); return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise ApiError(f"{method} {url.split('?')[0]} -> {e.code}: {e.read()[:400].decode(errors='replace')}")
def uc(method,path,body=None,timeout=60):
    c=_kv(cfg('UPCLOUD_CRED_FILE'))
    auth='Basic '+base64.b64encode(f"{c['user'].strip()}:{c['pass'].strip()}".encode()).decode()
    return _req('https://api.upcloud.com/1.3'+path,method,{'Authorization':auth},body,timeout)
def cf(method,path,body=None):
    tok=open(os.path.expanduser(cfg('CF_TOKEN_FILE'))).read().strip()
    r=_req('https://api.cloudflare.com/client/v4'+path,method,{'Authorization':'Bearer '+tok},body)
    if not r.get('success',True): raise ApiError(str(r.get('errors')))
    return r
