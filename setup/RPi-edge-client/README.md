# File Structure

```
📁 RPi-edge-client

    📄 config.txt
    📄 default.script
    📄 README.md
```

# OS Setup

- Install RASPBERRY PI OS LITE (64-Bit)
- Setup SSH, WIFI, Hostname
- Copy config.txt into bootfs folder on SD card

```
sudo apt update
sudo apt upgrade
sudo apt install -y build-essential libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev openssl docker.io git tldr ncdu minicom pigpio libsqlite3-dev wget screen udhcpc
```

```
sudo raspi-config
Enable I2C Interface
```

# Docker Setup

```
nano /etc/docker/daemon.json
#Add:
{
    "dns": ["8.8.8.8", "1.1.1.1",  "8.8.4.4"]
}
```

```
sudo usermod -aG docker $USER
sudo git config --system --add safe.directory '*'
sudo reboot
```

# Python

```
wget https://www.python.org/ftp/python/3.12.8/Python-3.12.8.tgz
sudo tar zxf Python-3.12.8.tgz
cd Python-3.12.8
sudo ./configure --enable-optimizations --enable-loadable-sqlite-extensions
sudo make -j 4
sudo make install
curl -sSL https://install.python-poetry.org/ | python3.12 -
```

# Modem

## AT Modem Commands

```
# open modem interface
sudo minicom -D /dev/ttyS0
# check modem functionality
AT
# see terminal input
ATE1
# switch to RNDIS
AT+CUSBPIDSWITCH=9001,1,1
# Wait for a possible modem restart

# set SIM APN
AT+CGDCONT=1,"IP","iotde.telefonica.com"
# set network registration to automatic
AT+COPS=0
# set LTE only
AT+CNMP=38
```

## Install Driver

```
cd /home/pi
wget https://www.waveshare.net/w/upload/8/89/SIM8200_for_RPI.7z
7z x SIM8200_for_RPI.7z -r -o./SIM8200_for_RPI
sudo chmod 777 -R SIM8200_for_RPI
cd SIM8200_for_RPI/Goonline
make clean
make
```

### Setup UDHCPC default script

```
copy default.script to /usr/share/udhcpc/default.script
sudo chmod -R 0777 /usr/share/udhcpc/
```

## Update Crontab

```
crontab -e
#Add:
@reboot sudo pigpiod -n "127.0.0.1"
@reboot sleep 10 && sudo -b /home/pi/SIM8200_for_RPI/Goonline/simcom-cm -f /home/pi/SIM8200_log.txt
@reboot sleep 15 && sudo -b udhcpc -i wwan0 -b
```

# Setup Gateway

```
cd /home/pi
mkdir /home/pi/acropolis
cd /home/pi/acropolis/
mkdir data
mkdir logs
```

### Copy Files

- Copy `run_dockerized_gateway.sh` to /home/pi/acropolis/
- Update `THINGSBOARD_PROVISION_*` environment parameters

```
git clone https://github.com/tum-esm/ACROPOLIS-edge.git ./acropolis-edge
sudo git config --system --add safe.directory '*'
sudo ./build_gateway_runner_docker_image.sh
./run_dockerized_gateway.sh
docker logs --tail 50 -f acropolis_edge_gateway
```

# Create Image of SDCard

```
dd status=progress bs=4M  if=/dev/disk4 | gzip > //Users/.../acropolis-edge-image.gz
```

# Flash image back to SDCard

```
diskutil list
diskutil umountDisk /dev/disk{i}
gzip -dc //Users/.../acropolis-edge-image.gz | sudo dd of=/dev/disk4 bs=4M status=progres
```
