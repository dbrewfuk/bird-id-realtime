#!/bin/zsh
set -euo pipefail

DATA_DIR="${HOME}/.mosquitto"

if [[ ! -f "${DATA_DIR}/config/mosquitto.conf" ]]; then
  echo "Missing ${DATA_DIR}/config/mosquitto.conf. Run prepare_mosquitto.sh first."
  exit 1
fi

docker rm -f bird-id-mosquitto >/dev/null 2>&1 || true

docker run -d \
  --name bird-id-mosquitto \
  --restart unless-stopped \
  -p 1883:1883 \
  --mount "type=bind,source=${DATA_DIR}/config,target=/mosquitto/config" \
  --mount "type=bind,source=${DATA_DIR}/data,target=/mosquitto/data" \
  --mount "type=bind,source=${DATA_DIR}/log,target=/mosquitto/log" \
  eclipse-mosquitto:2

echo "Mosquitto started on port 1883."

