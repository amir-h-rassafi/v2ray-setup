echo "Install dependencies"
sudo apt update
sudo apt install docker.io docker-compose -y
sudo apt install certbot nginx python3-certbot-nginx -y
docker-compose -f docker-compose-xui.yml up -d

echo "Disable UFW"
sudo disable ufw

ip=$(curl -s ifconfig.io)
echo "Your Ip is:  $ip , please give me domain:"
read domain
cp ./nginx.conf default
sed -i "s/{{domain}}/$domain/g" default
sed -i "/certificate*/d" default
cp default /etc/nginx/sites-enabled/default
certbot --nginx -d $domain
sudo service nginx restart
echo "Now check your domain!!SSL signing done!"
