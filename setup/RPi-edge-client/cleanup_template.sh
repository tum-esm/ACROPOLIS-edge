#!/usr/bin/env bash
# Remove everything that belongs to one system before an SD card image is taken from it.
# Keeps the Docker images: they are the build cache for controller updates.
set -euo pipefail

ACROPOLIS_DIR=/home/pi/acropolis

docker rm -f acropolis_edge_gateway acropolis_edge_controller 2>/dev/null || true
rm -f "$ACROPOLIS_DIR/acropolis-edge/software/gateway/tb_access_token"
find "$ACROPOLIS_DIR/data" -mindepth 1 ! -name config.json -delete
find "$ACROPOLIS_DIR/logs" -mindepth 1 -delete
systemctl stop tailscaled
rm -rf /var/lib/tailscale
journalctl --rotate
journalctl --vacuum-time=1s
