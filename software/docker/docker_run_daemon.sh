#!/bin/bash

export $(grep -v '^#' .env | xargs)

GLOBAL_ACROPOLIS_DEPLOYMENT_ROOT_PATH=${ACROPOLIS_DEPLOYMENT_ROOT_PATH}
ACROPOLIS_DEPLOYMENT_ROOT_PATH=/root/deployment

# Run the docker image
docker run -d --restart unless-stopped --name ACROPOLIS_edge_$ACROPOLIS_MQTT_IDENTIFIER \
  -e ACROPOLIS_DEPLOYMENT_ROOT_PATH="$ACROPOLIS_DEPLOYMENT_ROOT_PATH" \
  --env-file .env \
  -v "$GLOBAL_ACROPOLIS_DEPLOYMENT_ROOT_PATH":"$ACROPOLIS_DEPLOYMENT_ROOT_PATH" \
  -v "/bin/vcgencmd":"/bin/vcgencmd" \
  -v "/bin/uptime":"/bin/uptime" \
  --network=host \
  --privileged \
  tum-esm/acropolis/edge-node
