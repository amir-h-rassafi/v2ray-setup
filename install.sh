echo "Install dependencies"
sudo apt update
sudo apt install stunnel4 -y
sudo apt install openssl -y
sudo apt install btop -y
sudo apt install net-tools -y
curl -Ls https://raw.githubusercontent.com/vaxilu/x-ui/master/install.sh > v2ray-xui.sh
sudo chmod +x v2ray-xui.sh
sudo ./v2ray-xui.sh

