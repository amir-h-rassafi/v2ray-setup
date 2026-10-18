# rotation/: move the single VPN node to a new region via provider APIs

Generic version of the scripts described in [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md#rotation-every-2-nights).
They assume a 3x-ui node where:

* `DIRECT_HOST` is a DNS-only A record and the node's certificate is issued for it;
* `CDN_HOST` is a proxied A record used by the TLS (CDN) inbounds and the subscription server.

| File | Purpose |
|---|---|
| `config.example.env` | Copy to `config.env` (git-ignored) and fill in. |
| `common.py` | Config loader plus minimal UpCloud / Cloudflare API clients. |
| `node.py` | SSH helper (paramiko). |
| `backup.py` | Consistent snapshot of x-ui DB, certs and system bits. Can run standalone. |
| `xraytest.py` | Local Xray client tests. Inbounds are discovered from the node's config. |
| `rotate.py` | The full rotation with rollback. |

```bash
python3 -m venv venv && . venv/bin/activate && pip install -r requirements.txt
cp config.example.env config.env   # edit
python3 backup.py                  # try a backup first
python3 rotate.py --dry-run        # shows current node and next zones
python3 rotate.py                  # rotate now
# every 2 nights:
# 0 3 */2 * * cd /path/to/rotation && venv/bin/python rotate.py >> logs/cron.log 2>&1
```

Logs and a JSON summary are written to `logs/`. Backups go to `BACKUP_DIR` (they contain the full DB, so keep them private).
