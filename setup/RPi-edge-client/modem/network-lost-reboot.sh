#!/usr/bin/env bash
set -euo pipefail

TIMEOUT=3           # seconds per TCP attempt
RETRY_DELAY=10      # wait before a second check
TARGETS=("1.1.1.1:53" "8.8.8.8:53" "9.9.9.9:53")  # TCP DNS targets

TIMEOUT_BIN=/usr/bin/timeout
BASH_BIN=/bin/bash
LOGGER=/usr/bin/logger
REBOOT=/sbin/reboot

tcp_ok_any() {
  # Try TCP to host:port using the system's default routing
  local host port
  IFS=':' read -r host port <<<"$1"
  $TIMEOUT_BIN "$TIMEOUT" $BASH_BIN -c ">/dev/tcp/$host/$port" >/dev/null 2>&1
}

any_interface_online() {
  for t in "${TARGETS[@]}"; do
    tcp_ok_any "$t" && return 0
  done
  return 1
}

# --- main ---
# One check; if it fails, wait briefly and check again (debounce transient blips)
if any_interface_online || ( sleep "$RETRY_DELAY" && any_interface_online ); then
  $LOGGER -t net-reboot "Connectivity OK (no reboot)."
  exit 0
fi

$LOGGER -t net-reboot "Connectivity LOST on all interfaces → rebooting"
$REBOOT