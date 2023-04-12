ip=$(curl -s ifconfig.io)
echo "Your Ip is:  $ip , please give me domain:"
read domain
certbot --nginx -d $domain
cp ./nginx.conf default
sed -i "s/{{domain}}/$domain/g" default
cp default /etc/nginx/sites-enabled/default
sudo service nginx restart