# ACROPOLIS nginx reverse-proxy setup


We use nginx as a reverse proxy to handle all SSL encryption for traffic to/from Thingsboard, both for the Thingsboard GUI as well as for the ThingsBoard MQTT broker.

The reverse proxy consists of 

1. the site-file (located at `/etc/nginx/sites-enabled/thingsboard`  ):

[https://github.com/tum-esm/ACROPOLIS-edge/blob/main/setup/ThingsBoard/nginx_thingsboard.conf](https://github.com/tum-esm/ACROPOLIS-edge/blob/main/setup/ThingsBoard/nginx_thingsboard.conf)

1. the nginx-wide global config file located at `/etc/nginx/nginx.conf` :

[https://github.com/tum-esm/ACROPOLIS-edge/blob/main/setup/ThingsBoard/nginx.conf](https://github.com/tum-esm/ACROPOLIS-edge/blob/main/setup/ThingsBoard/nginx.conf)

The site-file handles reverse-proxying the Thingsboard web-UI while the global nginx config contains the stream-forwarding for the MQTT broker.

Both rely on a cert and pem file used for encryption and to authenticate traffic as part of a certain domain. In our case, we use letsencrypt to automatically issue and renew certificates. Authentication with letsencrypt is handled via exposure of a .well-known folder-path defined in the site-config file.

To make thingsboard connet to this reverse-proxy setup, the following environment variables should be set for the `thingsboard` container in `docker-compose.yml`:

```scheme
environment:
      HTTP_BIND_PORT: 8088
      TB_QUEUE_TYPE: kafka
      TB_KAFKA_SERVERS: 127.0.0.1:9094
      LISTENER_TCP_BIND_PORT: 1883
      SSL_ENABLED: false
```

Link to the full docker-compose.yml: [https://github.com/tum-esm/ACROPOLIS-edge/blob/main/setup/ThingsBoard/docker-compose.yml](https://github.com/tum-esm/ACROPOLIS-edge/blob/main/setup/ThingsBoard/docker-compose.yml)

For further info on letsencrypt, see [https://letsencrypt.org/](https://letsencrypt.org/) and [https://certbot.eff.org/](https://certbot.eff.org/)