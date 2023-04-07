echo 'Install dependencies'
sudo apt update
sudo apt install docker.io docker-compose -y
sudo apt install nginx python3-certbot-nginx -y
docker-compose -f docker-compose-xui.yml up -d

ip=$(curl -s ifconfig.io)
echo "Your Ip is:  \033[1m${ip}\033[0m , please set domain !!!"
