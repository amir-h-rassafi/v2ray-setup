## [V2Ray](https://www.v2ray.com/) Setup + STUNNEL
(Before start check __other branches__ for other setups)
![img.png](img.png)

https://charlesreid1.github.io/stunnel.html


### What Does Stunnel Do?

Stunnel is a tool for creating SSL tunnels between a client and a server.

### Setup
As you see in above photo we will setup stunnel as our secure tunnel and pass v2ray traffic over it.
(__Local Services__ in above photo in this case is __v2ray node__)

### Steps

1 - Run `install.sh` to install requirements in each VPS.(we can not run them on pods as we are using `systemctl`)

2 - Setup stunnel `server-side`:
```Bash
cd v2ray-setup
vim server.conf # Modify V2RAY-PORT to a real free port like 9999
cp server.conf /etc/stunnel/
cd /etc/stunnel/
openssl genrsa -out stunnel.key 2048
# Please avoid to use some random stuff like test.
openssl req -new -key stunnel.key -out stunnel.csr
openssl x509 -req -days 365 -in stunnel.csr -signkey stunnel.key -out stunnel.crt
cat stunnel.crt stunnel.key > stunnel.pem # You need to use it in client as well
sudo systemctl restart stunnel4.service
systemctl status stunnel4.service # You should see everything is fine
```

2 - Setup stunnel `client-side`:
```Bash
cd v2ray-setup
vim client.conf # Use your server ip in the config
cp client.conf /etc/stunnel/
scp {STUNNEL_SERVER}:/etc/stunnel/stunnel.pem /etc/stunnel/stunnel.pem
sudo systemctl restart stunnel4.service
systemctl status stunnel4.service # You should see everything is fine
```

3 - Setup x-ui in server (on stunnel VPS) and create an account there with a port listening to `V2RAY-PORT` like 9999

Sample config(default)
```json
{
  "api": {
    "services": [
      "HandlerService",
      "LoggerService",
      "StatsService"
    ],
    "tag": "api"
  },
  "inbounds": [
    {
      "listen": "127.0.0.1",
      "port": 62789,
      "protocol": "dokodemo-door",
      "settings": {
        "address": "127.0.0.1"
      },
      "tag": "api"
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "settings": {}
    },
    {
      "protocol": "blackhole",
      "settings": {},
      "tag": "blocked"
    }
  ],
  "policy": {
    "system": {
      "statsInboundDownlink": true,
      "statsInboundUplink": true
    }
  },
  "routing": {
    "rules": [
      {
        "inboundTag": [
          "api"
        ],
        "outboundTag": "api",
        "type": "field"
      },
      {
        "ip": [
          "geoip:private"
        ],
        "outboundTag": "blocked",
        "type": "field"
      },
      {
        "outboundTag": "blocked",
        "protocol": [
          "bittorrent"
        ],
        "type": "field"
      }
    ]
  },
  "stats": {}
}
```
4 - setup x-ui in client

Notice that in client config you should use `localhost:4443` rather than server ip, port like following:
```json
{
  "api": {
    "services": [
      "HandlerService",
      "LoggerService",
      "StatsService"
    ],
    "tag": "api"
  },
  "inbounds": [
    {
      "listen": "127.0.0.1",
      "port": 62789,
      "protocol": "dokodemo-door",
      "settings": {
        "address": "127.0.0.1"
      },
      "tag": "api"
    }
  ],
  "outbounds": [
      {
        "tag": "proxy",
        "protocol": "vmess",
        "settings": {
          "vnext": [
             {
            "address": "localhost",
            "port": 4443,
            "users": [
              {
                "alterId": 0,
                "encryption": "",
                "flow": "",
                "id": "{VMESS-ID}",
                "level": 8,
                "security": "auto"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "none",
        "tcpSettings": {
          "header": {
            "type": "none"
          }
        }
      },
      "tag": "proxy"
    },

    {
      "protocol": "blackhole",
      "settings": { },
      "tag": "blocked"
    },
    {
      "tag": "InternalDNS",
      "protocol": "dns"
    }
  ],
  "policy": {
    "system": {
      "statsInboundDownlink": true,
      "statsInboundUplink": true
    }
  },
  "routing": {
    "rules": [
      {
        "type": "field",
        "outboundTag": "freedom",
        "domain": [
          "regexp:.*\\.ir$",
          "domain:digikala.com",
          "snapp.express",
          "aparat.com",
          "full:google.com",
          "overleaf.com",
        ]
      },
      {
        "inboundTag": [
          "api"
        ],
        "outboundTag": "api",
        "type": "field"
      },
      {
        "outboundTag": "blocked",
        "protocol": [
          "bittorrent"
        ],
        "type": "field"
      }
    ]
  },
  "stats": { }
}
```

Feel free to manage your accounts just over the client server!


## Debug

1 - use `journalctl -fu stunnel4.service` to check related logs

2 - to check your stunnel server you can use following command:

```bash
openssl s_client -connect {STUNNEL_SERVER/CLIENT}:4443 -debug -msg -servername cloudflare.com -tls1_2 
```

3 - Check firewall

4 - `iftop, tcpdump, telnet, ss, nc` is general helpful network tools