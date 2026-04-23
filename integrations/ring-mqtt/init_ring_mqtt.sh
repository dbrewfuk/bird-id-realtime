#!/bin/zsh
set -euo pipefail

DATA_DIR="${HOME}/.ring-mqtt"

if [[ ! -d "${DATA_DIR}" ]]; then
  echo "Missing ${DATA_DIR}. Run prepare_ring_mqtt.sh first."
  exit 1
fi

docker run -it --rm \
  --mount "type=bind,source=${DATA_DIR},target=/data" \
  --entrypoint /app/ring-mqtt/init-ring-mqtt.js \
  tsightler/ring-mqtt

