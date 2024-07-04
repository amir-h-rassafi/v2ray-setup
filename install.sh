echo "Install dependencies"
sudo apt update
sudo apt install stunnel4 -y
sudo apt install openssl -y
sudo bash <(curl -Ls https://raw.githubusercontent.com/vaxilu/x-ui/master/install.sh)
