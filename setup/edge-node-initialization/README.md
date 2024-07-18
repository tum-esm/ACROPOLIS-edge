# Table of contents

1. [Clone existing system setup](#paragraph1)
   1. [Copy from SD Card to MacOS](#subparagraph1)
   2. [Copy From MacOS to SD Card](#subparagraph2)
2. [Initial system setup](#paragraph2)
   1. [Raspberry Pi Setup](#subparagraph2)
   2. [How the Raspberry Pi runs this code](#subparagraph2)
3. [Set up LTE Hat](#paragraph3)
   1. [Configure modem](#subparagraph5)
   2. [Install Driver](#subparagraph6)

<br/>

## Clone existing system setup <a name="paragraph1"></a>

### Copy from SD Card to MacOS <a name="subparagraph1"></a>

- Set current_revision to 0

```
/home/pi/Documents/acropolis/%VERSION%/config/state.json
```

- Identify the correct volume

```
diskutil list
```

- Dismount volume

```
diskutil umount /dev/disk*
```

- Start image creation from SD Card

```
sudo dd if=/dev/disk4 of=/.../acropolis-version.img bs=4M status=progress
```

<br/>

### Copy From MacOS to SD Card <a name="subparagraph2"></a>

- Identify the correct volume

```
diskutil list
```

- Dismount volume

```
diskutil umount /dev/disk*
```

- Transfer existing image to SD Card

```
sudo dd of=/dev/disk4 if=/.../acropolis-version.img bs=4M status=progress
```

Insert the SD Card into the new node system. Connect to the RaspberryPi over SSH:

- Set the THINGSBOARD_MQTT_IDENTIFIER for the new node

```
/home/pi/Documents/acropolis/%VERSION%/config/.env
```

- RaspberryPi Hostname

```
sudo raspi-config
1 System Options / S4 Hostname
reboot
```

<br/>

## Initial system setup <a name="paragraph2"></a>

### Inital System Setup <a name="subparagraph3"></a>

#### Raspberry Pi OS Setup

- Download **Raspberry Pi Imager** (https://www.raspberrypi.com/software/)
- Flash the **Raspberry Pi OS 64-Bit** on a SD card
- In settings set hostname, set ssh key access, timezone, wifi (optional)

<br/>

#### Node Setup

- Open `template/.env.template`, fill and rename to `.env`
- Copy everything in `/sensor-node-initialization/` on the SD card (`bootfs`)
- Confirm that the files are present at `/boot/firmware`

```
📁 /boot/firmware/

    📁 templates/
        📄 .env.
        📄 edge-cli.template.sh

    📁 system-setup-files/
        📄 .bashrc
        📄 crontab
        📄 initialize_pi.py
        📄 initialize_root.py
        📄 run_node_tests.py
        📄 utils.py

    📄 config.txt
```

- Insert SD Card into RaspberryPi
- Confirm the SSH access
- Execute via terminal

```bash
# test network connection
ping -c 3 www.google.com

#create user directories
xdg-user-dirs-update

#install python3.12
#acknowledgement to https://stackoverflow.com/questions/64718274/how-to-update-python-in-raspberry-pi
sudo apt-get update
sudo apt-get install -y build-essential tk-dev libncurses5-dev libncursesw5-dev libreadline6-dev libdb5.3-dev libgdbm-dev libsqlite3-dev libssl-dev libbz2-dev libexpat1-dev liblzma-dev zlib1g-dev libffi-dev
wget https://www.python.org/ftp/python/3.12.4/Python-3.12.4.tgz
sudo tar zxf Python-3.12.4.tgz
cd Python-3.12.4
sudo ./configure --enable-optimizations
sudo make -j 4
sudo make altinstall
echo "alias python=/usr/local/bin/python3.12" >> ~/.bashrc

# initialize the node
sudo python3 /boot/firmware/system-setup-files/initialize_root.py
python3 /boot/firmware/system-setup-files/initialize_pi.py

# reboot
sudo reboot
```

<br/>

#### Test Node Setup

```
python3 /boot/firmware/system-setup-files/run_node_tests.py
```

<br/>

### How the Raspberry Pi runs this code <a name="subparagraph4"></a>

- The sensor code is at `~/Documents/acropolis/%VERSION%`
- Note: Only the files from /sensor directory are kept on the RaspberryPi.
- The _crontab_ starts the automation every 2 minutes via the CLI
- Note: `~/Documents/acropolis/edge-cli.sh` always points to the latest version

```bash
#!/bin/bash

set -o errexit

/home/pi/Documents/acropolis/%VERSION%/.venv/bin/python /home/pi/Documents/acropolis/%VERSION%/cli/main.py $*
```

The `~/.bashrc` file contains an alias for the CLI:

```bash
alias edge-cli="bash /home/pi/Documents/acropolis/edge-cli.sh"
```

<br/>

## Set up LTE Hat <a name="paragraph3"></a>

### Configure modem <a name="subparagraph5"></a>

```bash
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

# Wait for a few minutes for the first dial into the mobile network
# Exit modem interface
```

```bash
# check if modem is properly setup for driver installation
sudo minicom -D /dev/ttyUSB2

# commands to check modem status
AT+CSQ # antenna signal strength
AT+CPIN?
AT+COPS?
AT+CGREG?
AT+CPSI? #return IMEI
```

<br/>

### Install Driver <a name="subparagraph6"></a>

```bash
# download and install driver
cd /home/pi
wget https://www.waveshare.net/w/upload/8/89/SIM8200_for_RPI.7z
7z x SIM8200_for_RPI.7z -r -o./SIM8200_for_RPI
sudo chmod 777 -R SIM8200_for_RPI
cd SIM8200_for_RPI/Goonline
make clean
make

# Set DNS
sudo ./simcom-cm &
sudo udhcpc -i wwan0
sudo route add -net 0.0.0.0 wwan0

# test connection
ping -I wwan0 www.google.de
```

Add lines to rc.local

`sudo /home/pi/SIM8200_for_RPI/Goonline/simcom-cm &` <br/>
`sudo udhcpc -i wwan0`

```
sudo nano /etc/rc.local
```

<br/>
