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

- Download and install **Raspberry Pi OS Lite (64-bit)**. (Raspberry Pi OS Trixie)
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

Verify that python3.13 is installed:

```bash
python3.13 --version
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
sudo nano /usr/local/bin/network-lost-reboot.sh
```

From `/modem/` directory, paste content of `network_lost_reboot_trigger.sh` file.

## Enable executable
```bash
sudo chmod +x /usr/local/bin/network-lost-reboot.sh
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
cd /home/pi/acropolis/
./run_dockerized_gateway.sh #registers device with ThingsBoard and creates tb_access_token
docker logs --tail 50 -f acropolis_edge_gateway
```

### **Setup Thingsboard Shared Attributes**

(1) Create a new shared attribute "FILES" in Thingsboard with content:


```json
{
  "network-lost-reboot-sh": {
    "path": "/usr/local/bin/network-lost-reboot.sh",
    "encoding": "base64"
  },
  "crontab": {
    "path": "/var/spool/cron/crontabs/root",
    "encoding": "base64",
    "write_version": 1
  },
  "controller_config": {
    "path": "$DATA_PATH/config.json",
    "encoding": "json",
    "write_version": 1,
    "restart_controller_on_change": true
  },
  "ssh_keys": {
    "path": "/home/pi/.ssh/authorized_keys",
    "encoding": "text"
  }
}
```

(2) Create a new shared attribute "FILE_CONTENT_controller_config" with content:

```json
{
    "version": "1.0.0",
    "local_time_zone": "Europe/Berlin",
    "active_components": {
        "run_controller": true,
        "run_calibration_procedures": false,
        "send_messages_over_mqtt": true,
        "run_hardware_tests": false,
        "run_sensor_heating_control": false, 
        "perform_sht45_offset_correction": false,
        "perform_co2_calibration_correction": false,
        "log_to_file": true,
        "log_to_console": true,
        "simulation_mode": false
    },
    "calibration": {
        "average_air_inlet_measurements": 15,
        "calibration_frequency_days": 1,
        "calibration_hour_of_day": 3,
        "gas_cylinders": [
            {
                "valve_number": 2,
                "bottle_id": "999"
            },
            {
                "valve_number": 3,
                "bottle_id": "998"
            }
        ],
        "sampling_per_cylinder_seconds": 600,
        "system_flushing_pump_pwm_duty_cycle": 0.5,
        "system_flushing_seconds": 300,
        "sht45_calibration_seconds": 60

    },
    "documentation": {
        "site_name": "...",
        "site_short_name": "...",
        "site_observation_since": "...",
        "inlet_elevation": "...",
        "last_maintenance_date": "...",
        "maintenance_comment": "...",
        "gmp343_sensor_id": "..."
    },
    "hardware": {
        "heat_box_heater_power_pin_out": 18,
        "heat_box_heater_power_pin_frequency": 10000,
        "heat_box_ventilator_power_pin_out": 26,
        "heat_box_temperature_target": 40,
        "heat_box_pid_kp": 1,
        "heat_box_pid_ki": 0.1,
        "heat_box_pid_kd": 0.05,
        "pump_pwm_duty_cycle": 0.13,
        "pump_power_pin_out": 19,
        "pump_power_pin_frequency": 10000,
        "pump_speed_pin_in": 16,
        "gmp343_optics_heating": true,
        "gmp343_linearisation": true,
        "gmp343_temperature_compensation": true,
        "gmp343_relative_humidity_compensation": true,
        "gmp343_pressure_compensation": true,
        "gmp343_oxygen_compensation": true,
        "gmp343_filter_seconds_averaging": 10,
        "gmp343_filter_smoothing_factor": 0,
        "gmp343_filter_median_measurements": 0,
        "gmp343_power_pin_out": 20,
        "gmp343_serial_port": "/dev/ttySC0",
        "wxt532_power_pin_out": 21,
        "wxt532_serial_port": "/dev/ttySC1",
        "valve_power_pin_1_out": 25,
        "valve_power_pin_2_out": 24,
        "valve_power_pin_3_out": 23,
        "valve_power_pin_4_out": 22,
        "ups_battery_charge_pin_in": 5,
        "ups_power_mode_pin_in": 10,
        "ups_alarm_pin_in": 7
    },
    "measurement": {
        "average_air_inlet_measurements": 15,
        "procedure_seconds": 120,
        "valve_number": 1
    }
}
```

(3) Assign software version "1.0.1" in the device details page in Thingsboard.


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
