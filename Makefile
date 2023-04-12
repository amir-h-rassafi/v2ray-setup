xui_session :=
UID :=

all:
	install
	xui
	disable_firewall
	sign
	xui_login
	add

install:
	sudo apt update
	sudo apt install docker.io docker-compose curl -y
	sudo apt install certbot nginx python3-certbot-nginx -y

xui: 
	docker-compose -f docker-compose-xui.yml up -d

disable_firewall:
	sudo ufw disable

sign:
	sh sign.sh
	
xui_login:
	$(eval xui_session := $(shell curl -c - 'http://localhost:54321/login' \
	-H 'Accept: application/json, text/plain, */*' \
	--data-raw 'username=admin&password=admin' \
	--compressed -s | awk '{print $$7}' | grep -oE '[a-zA-Z0-9_-]+$$'))

add:
	xui_login
	$(eval UID := $(shell uuidgen))
	@curl 'http://localhost:54321/xui/inbound/add' \
	-H 'Accept: application/json, text/plain, */*' \
	-H 'Accept-Language: en-US,en;q=0.9' \
	-H 'Connection: keep-alive' \
	-H 'Content-Type: application/x-www-form-urlencoded; charset=UTF-8' \
	-H "Cookie: session=$(xui_session)" \
	--data-raw "up=0&down=0&total=0&remark=localhost&enable=true&expiryTime=0&listen=localhost&port=30000&protocol=vmess&settings=%7B%0A%20%20%22clients%22%3A%20%5B%0A%20%20%20%20%7B%0A%20%20%20%20%20%20%22id%22%3A%20%22$(UID)%22%2C%0A%20%20%20%20%20%20%22alterId%22%3A%200%0A%20%20%20%20%7D%0A%20%20%5D%2C%0A%20%20%22disableInsecureEncryption%22%3A%20false%0A%7D&streamSettings=%7B%0A%20%20%22network%22%3A%20%22ws%22%2C%0A%20%20%22security%22%3A%20%22none%22%2C%0A%20%20%22wsSettings%22%3A%20%7B%0A%20%20%20%20%22acceptProxyProtocol%22%3A%20false%2C%0A%20%20%20%20%22path%22%3A%20%22%2Fws%22%2C%0A%20%20%20%20%22headers%22%3A%20%7B%7D%0A%20%20%7D%0A%7D&sniffing=%7B%0A%20%20%22enabled%22%3A%20true%2C%0A%20%20%22destOverride%22%3A%20%5B%0A%20%20%20%20%22http%22%2C%0A%20%20%20%20%22tls%22%0A%20%20%5D%0A%7D"
	@echo "\n$(UID)"

help:
	@echo "Available targets:"
	@echo " - install"
	@echo " - xui"
	@echo " - disable_firewall"
	@echo " - sign"
	@echo " - xui_login"
	@echo " - add"
	@echo " - run"
