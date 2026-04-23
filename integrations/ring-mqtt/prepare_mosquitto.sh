#!/bin/zsh
set -euo pipefail

DATA_DIR="${HOME}/.mosquitto"

mkdir -p "${DATA_DIR}/config" "${DATA_DIR}/data" "${DATA_DIR}/log"

cp "/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/mosquitto.conf" \
  "${DATA_DIR}/config/mosquitto.conf"

echo "Mosquitto data directory ready at ${DATA_DIR}"

