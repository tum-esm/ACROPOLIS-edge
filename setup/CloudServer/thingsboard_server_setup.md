# ThingsBoard server setup
This guide provides step-by-step instructions to set up the ThingsBoard server for the Acropolis project.

## Prerequisites
 - A server running Ubuntu 22.04 LTS
   - using a cloud hosting provider (e.g., DigitalOcean, AWS, Azure, GCP)
   - minimum specifications 1 vCPU, 1GB RAM (min. 2GB recommended)
 - [Optional] A domain name pointing to the server's IP address
   - e.g., `thingsboard.acropolis.example.com`
   - choose from a paid domain name provider (e.g. namecheap.com ) or use a subdomain of an existing domain (e.g. from within your institution)
   - point the domain's DNS A record to the server's IP address (`A <domain> <IP>`)
   - after setting up the thingsboard server, optionally create a trusted certificate for the domain using Let's Encrypt (e.g. using `certbot certonly -d <domain>`)
     - add an automatic renewal cron job to the server (e.g. `0 0 * * * certbot renew --quiet`)
 - [Optional] Familiarize with ThingsBoard documentation: https://thingsboard.io/docs/
   
## Installation
1. [Optional] Update system packages and reboot
    ```bash
    sudo apt update
    sudo apt upgrade -y
    sudo apt auto-remove -y
    sudo reboot
    ```
   
2. [Optional] Set up a swapfile if your server has less than 2GB of RAM
    ```bash
    sudo fallocate -l 4G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    ```

3. Install dependencies (`docker`, `git`, `jq`, `curl`, `ca-certificates`, `nginx-full`, `ufw`)
    ```bash
    > sudo apt install docker.io git jq curl ca-certificates nginx-full ufw
    ```

4. Install `docker-compose`
    ```bash
    # Add Docker's official GPG key:
    sudo apt update
    sudo apt install ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    # Add the repository to Apt sources:
    echo   "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
       $(. /etc/os-release && echo "$VERSION_CODENAME") stable" |   sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    # Install docker-compose
    sudo apt update
    sudo apt install docker-compose-plugin
    ```

5. Add user to `docker` group
    ```bash
    sudo groupadd docker
    sudo usermod -aG docker $USER
    ```

6. Create data folder for ThingsBoard
    ```bash
    mkdir -p ~/data/thingsboard_data/data
    mkdir -p ~/data/thingsboard_data/logs
    mkdir -p ~/data/kafka
    sudo chmod -R a+rw ~/data/
    ```

7. Generate a self-signed certificate for ThingsBoard SSL (skip if using a trusted certificate):
    - run `gen_certs.sh` in a temporary directory on your local machine

8. Copy files
    - `docker-compose.yml` -> `~/docker-compose.yml`
    - `self_signed_cert.crt` -> `/etc/ssl/certs/self_signed_cert.crt`
    - `self_signed_cert.key` -> `/etc/ssl/certs/self_signed_cert.key`
    - `nginx_thingsboard.conf` -> `/etc/nginx/sites-available/thingsboard.conf`
    - `nginx.conf` -> `/etc/nginx/nginx.conf` (overwrite existing file)

9. Remove default nginx configuration
    ```bash
    sudo rm /etc/nginx/sites-enabled/default
    ```

10. Set up firewall using ufw
   ```bash
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow ssh
   sudo ufw allow http
   sudo ufw allow https
   sudo ufw allow 8843
   sudo ufw enable
   ```

10. Reload nginx and start docker containers
     ```bash
     sudo service nginx reload
     cd ~
     docker compose -f docker-compose.yml up -d
     ```
   
11. Watch live logs of ThingsBoard (initial startup takes several minutes)
     ```bash
    docker logs -f thingsboard
     ```
    - wait until the following message appears:
      > [main] INFO  o.t.s.ThingsboardServerApplication - Started ThingsBoard in x seconds
      
12. Open thingsboard web-platform and login with default credentials
    - open `<your-domain>` in a web browser
    - login with
      - username: `sysadmin@thingsboard.org`
      - password: `sysadmin`

13. Connect MQTT-devices to ThingsBoard
    - use the following MQTT broker settings:
      - host: `<your-domain>`
      - port: `8843` (SSL)
      - username: `<access-token>` (see below)
    - see [ThingsBoard documentation](https://thingsboard.io/docs/reference/mqtt-api/) for more details