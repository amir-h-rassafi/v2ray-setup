sudo apt update
sudo apt install docker.io docker-compose -y
sudo apt install python3-certbot-nginx
docker-compose -f docker-compose-xui.yml up -d