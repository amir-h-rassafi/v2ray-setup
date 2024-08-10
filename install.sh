echo "Install dependencies"
cd ~
mkdir v2ray_setup
cd v2ray_setup
sudo apt update
sudo apt install stunnel4 -y
sudo apt install openssl -y
sudo apt install btop -y
sudo apt install net-tools -y
sudo apt install btop -y
wget -N https://github.com/fatedier/frp/releases/download/v0.58.1/frp_0.58.1_linux_amd64.tar.gz
tar -xvf frp_0.58.1_linux_amd64.tar.gz
mv frp_0.58.1_linux_amd64 frp
curl -Ls https://raw.githubusercontent.com/vaxilu/x-ui/master/install.sh > v2ray-xui.sh
sudo chmod +x v2ray-xui.sh
sudo ./v2ray-xui.sh < /dev/null