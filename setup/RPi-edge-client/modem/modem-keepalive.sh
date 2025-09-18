#!/usr/bin/env bash
set -euo pipefail

SIMCM="/home/pi/SIM8200_for_RPI/Goonline/simcom-cm"
IFACE="wwan0"
PING_TARGET="1.1.1.1"        # or your APN's gateway / a stable endpoint
PING_COUNT=2
PING_TIMEOUT=3
SLEEP_OK=600                  # seconds between checks when OK
SLEEP_RETRY=600               # seconds after a repair attempt

log(){ /usr/bin/logger -t modem-keepalive "$*"; }

bring_up() {
  # ensure driver node exists; harmless if already present
  modprobe qmi_wwan 2>/dev/null || true

  # sometimes raw_ip has to be set before DHCP
  if ip link show "$IFACE" >/dev/null 2>&1; then
    ip link set "$IFACE" down || true
    echo Y > "/sys/class/net/$IFACE/qmi/raw_ip" 2>/dev/null || true
  fi


  # run the modem deamon
  log "bring_up: restarting simcom-cm.service"
  /bin/systemctl restart simcom-cm.service || true
}

repair() {
  # clean state and try again
  log "repair: flushing and restarting link"
  ip addr flush dev "$IFACE" 2>/dev/null || true
  ip link set "$IFACE" down 2>/dev/null || true
  bring_up
}


# watchdog loop
while true; do
  if ip link show "$IFACE" >/dev/null 2>&1; then
    if ping -I "$IFACE" -c "$PING_COUNT" -W "$PING_TIMEOUT" "$PING_TARGET" >/dev/null 2>&1; then
      sleep "$SLEEP_OK"
      continue
    fi
  fi

  # no interface or no connectivity → repair
  repair
  sleep "$SLEEP_RETRY"
done