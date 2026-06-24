# ACROPOLIS thingsboard server useful commands and files

## Important files

- nginx config file:	`/etc/nginx/sites-enabled/thingsboard`
- docker compose config file:	`/root/docker-compose.yml`
- letsencrypt (certbot) renewal config file:	`/etc/letsencrypt/renewal/thingsboard.esm.ei.tum.de.conf`

## Important commands

- start thingsboard:	`docker compose --project-directory /root/ up -d`
- live thingsboard logs:	`docker compose --project-directory /root/ logs -f -n 200`
- stop Thingsboard:	`docker compose --project-directory /root/ down`
- start/restart nginx:	`sudo service nginx restart`
- renew certificate (automatic):	`certbot renew`
- test certificate renewal:	`certbot renew --dry-run`

# Upgrading ThingsBoard

To upgrade the thingsboard server, stop the thingsboard container while keeping remaining containers (postgres) running,
then run the updater with the desired version specified:

1. `docker compose --project-directory /root/ down thingsboard`
2. update `docker-compose.yml` to reflect the new thingsboard version to be deployed
3. `docker compose --project-directory /root/ run --rm -u 0 -e UPGRADE_TB=true --entrypoint /usr/share/thingsboard/bin/install/upgrade.sh thingsboard --fromVersion=4.2.0` 
4. restart thingsboard: `docker compose --project-directory /root/ up -d`

Keep in mind: Upgrades are incremental, and often require a minimum version to already be deployed.

This often means having to perform multiple upgrades in succession. 

For example: To upgrade from v3.8.0 to 3.9.0, one first has to upgrade to Thingsboard v3.8.1

See here for a list of versions and information on the minimum required version for performing an upgrade: https://thingsboard.io/docs/pe/releases/releases-table/
