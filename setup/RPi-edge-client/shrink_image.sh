#!/usr/bin/env bash
# Shrink a Raspberry Pi OS SD card image to its used space and compress it to <image>.gz.
# Re-enables the Raspberry Pi OS first boot step, which grows the root partition
# to the full SD card again on the first boot.
# Usage: sudo ./shrink_image.sh acropolis-edge-image.img
set -euo pipefail

IMG="$1"
SECTOR_SIZE=512

enable_firstboot() {
  local mountpoint
  mountpoint=$(mktemp -d)
  mount "${LOOP}p1" "$mountpoint"
  grep -q firstboot "$mountpoint/cmdline.txt" ||
    sed -i '1s|$| init=/usr/lib/raspberrypi-sys-mods/firstboot|' "$mountpoint/cmdline.txt"
  umount "$mountpoint"
  rmdir "$mountpoint"
}

shrink_root_filesystem() {
  # e2fsck exit code 1 means errors were fixed
  e2fsck -fy "${LOOP}p2" || [ $? -le 1 ]
  resize2fs -M "${LOOP}p2"
}

root_filesystem_sectors() {
  dumpe2fs -h "${LOOP}p2" 2>/dev/null |
    awk -v sector="$SECTOR_SIZE" '/^Block count/ {count = $3} /^Block size/ {size = $3} END {print count * size / sector}'
}

shrink_root_partition() {
  local start
  start=$(partx -g -o START -n 2 "$IMG" | tr -d ' ')
  echo "$start,$1" | sfdisk -q --no-reread -N 2 "$IMG"
  truncate -s $(( (start + $1) * SECTOR_SIZE )) "$IMG"
}

LOOP=$(losetup -fP --show "$IMG")
enable_firstboot
shrink_root_filesystem
SECTORS=$(root_filesystem_sectors)
losetup -d "$LOOP"

shrink_root_partition "$SECTORS"
$(command -v pigz || echo gzip) -c "$IMG" > "${IMG%.img}.gz"
echo "Created ${IMG%.img}.gz"
