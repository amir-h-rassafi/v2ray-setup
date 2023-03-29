## [V2Ray](v2ray.com) Setup


In this repo we will setup v2ray with [x-ui](https://github.com/vaxilu/x-ui) dashboards


client  **⇨**  (shadowsocks, vmess) **⇨** bridge(xui) **⇨** tls-vmess **⇨** upstream(nginx(SSL) -> xui)

what we need for setup?

1 - domain (preferred to handle with cloudflare)
2 - two vps (bridge, upstream)

------------------------------------------------

on **bridge** just need need to setup this!

simple `docker-compose.yml` for setup xui 
```
version: "3"
services:
  xui:
    image: enwaiax/x-ui
    container_name: xui
    volumes:
      - $PWD/db/:/etc/x-ui/
      - $PWD/cert/:/root/cert/
    network_mode: host
```

`docker-compose -f docker-compose-xui.yml up -d`

_panel will set up on port 54321 , user:admin, pass:admin_

----------------------------------------------------

on upstream you need to have nginx & certbot also installed

```
sudo apt-get update
sudo apt-get install nginx certbot python3-certbot-nginx
```

then add an A record on dns with upstream IP and domain name.

after that you need to sign with 
```
certbot --nginx -d {domain}
```
----------------------------------------------------

How should I config them?

##### UPSTREAM :
you need to create a vmess account on upstream through panel with localhost, websocket and path /ws (check img)

then config nginx as reverse proxy (check nginx.conf and use it on `/etc/nginx/sites-enabled/default`)

##### BRIDGE :
you need to complete config.yml with UID, HOST, PORT and put the config on x-ui panel of bridge.

then create account on bridge and enjoy!!!

----------------------------------------------------

TODO:

1 - add cloudflare proxy config
2 - add some script for automation