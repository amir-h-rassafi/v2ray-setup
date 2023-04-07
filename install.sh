sudo apt update
sudo apt install docker.io docker-compose -y
sudo apt install nginx python3-certbot-nginx -y
docker-compose -f docker-compose-xui.yml up -d
