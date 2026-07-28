# Raspberry Pi 4 Edge Client Setup

This guide provides step-by-step instructions to set up a Raspberry Pi 4 as an edge client for the Acropolis project. It includes OS installation, dependency setup, modem configuration, and running the gateway.

## File Structure

```bash
📁 RPi-edge-client
    📁 modem
        📄 default.script
        📄 modem-keepalive.service
        📄 modem-keepalive.sh
        📄 network-lost-reboot.service
        📄 network-lost-reboot.sh
        📄 network-lost-reboot.timer
        📄 simcom-cm.service
    📄 config.txt
    📄 crontab.txt
    📄 run_dockerized_gateway.sh
    📄 pigpiod.service
    📄 README.md
    
```

## 1. Install Raspberry Pi OS

- Download and install **Raspberry Pi OS Lite (64-bit)**.
- Configure **SSH, WiFi, and Hostname**.
- Copy `config.txt` into the `bootfs` folder on the SD card.

## 2. Install Dependencies

Update the package list and install required dependencies:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y \
    build-essential libssl-dev libbz2-dev \
    libexpat1-dev liblzma-dev zlib1g-dev \
    libffi-dev openssl docker.io git \
    ncdu minicom libsqlite3-dev \
    wget screen udhcpc \
    python3-gpiozero python3-lgpio
```

Enable **I2C Interface** using:

```bash
sudo raspi-config
# Navigate to: Interface Options → I2C → Enable
```

## 3. Set Up Docker

Create a Docker daemon configuration file:

```bash
sudo nano /etc/docker/daemon.json
# Add:
{
    "dns": ["8.8.8.8", "1.1.1.1", "8.8.4.4"]
}
```

Add the current user to the Docker group and reboot:

```bash
sudo usermod -aG docker $USER
sudo reboot
```

## 4. Install Poetry

```bash
curl -sSL https://install.python-poetry.org/ | python3.13 -
```

## Reduce Log Sizes

```bash
sudo nano /etc/systemd/journald.conf
# Set:
SystemMaxUse=200M
SystemMaxFileSize=50M
```

## 5. Configure Modem

### **AT Commands for Modem Setup**

(only needed if a new modem is used or if the modem is reset to factory settings)

```bash
sudo minicom -D /dev/ttyS0
# Check modem functionality
AT
# Enable terminal echo
ATE1
# Switch modem to RNDIS mode
AT+CUSBPIDSWITCH=9001,1,1
# Set SIM APN
AT+CGDCONT=1,"IP","iotde.telefonica.com"
# Enable automatic network registration
AT+COPS=0
# Set LTE only mode
AT+CNMP=38
```

### **Install SIM8200 Modem Driver**

```bash
cd /home/pi
wget https://www.waveshare.com/w/upload/8/89/SIM8200_for_RPI.7z
7z x SIM8200_for_RPI.7z -r -o./SIM8200_for_RPI
cd SIM8200_for_RPI/Goonline
make clean && make
sudo chmod +x simcom-cm
```

In case of permission issues, run:
```bash
sudo chmod 777 -R SIM8200_for_RPI
```

## 6. Set Up Networking & System Automation


### **Create acropolis folder**

```bash
sudo mkdir -p /home/pi/acropolis/
cd /home/pi/acropolis/
sudo git clone https://github.com/tum-esm/ACROPOLIS-edge.git /home/pi/acropolis/acropolis-edge
sudo git config --system --add safe.directory '*'
cd /home/pi/acropolis/acropolis-edge/setup/RPi-edge-client
sudo cp run_dockerized_gateway.sh /home/pi/acropolis/
sudo chmod a+x /home/pi/acropolis/run_dockerized_gateway.sh
```

### **Update Crontab for Automation**

```bash
sudo crontab -e
```

Paste content of `crontab.txt` file.


# Setup Script for Modem Recovery

## Create sh script
```bash
sudo nano /usr/local/bin/network_lost_reboot_trigger.sh
```

From `/modem/` directory, paste content of `network_lost_reboot_trigger.sh` file.

## Enable executable
```bash
sudo chmod +x /usr/local/bin/network_lost_reboot_trigger.sh
```

# Setup Gateway

```bash
cd /home/pi
sudo mkdir -p /home/pi/acropolis/data
sudo mkdir -p /home/pi/acropolis/logs
```

### **Clone and Build Gateway**

```bash
cd /home/pi/acropolis/acropolis-edge/software/gateway
sudo bash build_gateway_runner_docker_image.sh
cd /home/pi/acropolis
sudo nano run_dockerized_gateway.sh # Update `THINGSBOARD_PROVISION_*` environment parameters (Thingsboard -> Device Profile -> Name -> Device Provisioning)
```

(Optional) Skip if you want to create an template image for multiple systems

```bash
./run_dockerized_gateway.sh #registers device with ThingsBoard and creates tb_access_token
docker logs --tail 50 -f acropolis_edge_gateway
```

## 8. Create & Flash SD Card Image

Remove SD Card and insert into personal computer

### **Create Backup Image**

```bash
diskutil list
diskutil umountDisk /dev/disk[*]
dd status=progress bs=4M  if=/dev/disk[*] | gzip > //Users/.../acropolis-edge-image.gz
```

## 9. Fast Setup for additional systems

Insert fresh SD Card into personal computer

### **Flash Image to SD Card**

```bash
diskutil list
diskutil umountDisk /dev/disk[*]
gzip -dc //Users/.../acropolis-edge-image.gz | sudo dd of=/dev/disk[*] bs=4M status=progress
```

Remove SD Card and insert into RaspberryPi

### **Change Hostname**

```bash
sudo raspi-config
# Navigate to: System Options → Hostname
reboot
```

### **Run Gateway Script**

```bash
cd /home/pi/acropolis/acropolis-edge/software/gateway
# make sure no 'tb_access_token' exists
cd /home/pi/acropolis
./run_dockerized_gateway.sh
docker logs --tail 50 -f acropolis_edge_gateway
```

---

This completes the setup for the Raspberry Pi 4 Edge Client.
