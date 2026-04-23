#!/bin/zsh
set -euo pipefail

DATA_DIR="${HOME}/.ring-mqtt"

if [[ ! -f "${DATA_DIR}/config.json" ]]; then
  echo "Missing ${DATA_DIR}/config.json. Run prepare_ring_mqtt.sh first."
  exit 1
fi

docker rm -f ring-mqtt >/dev/null 2>&1 || true

docker run -d \
  --name ring-mqtt \
  --restart unless-stopped \
  -p 8554:8554 \
  --mount "type=bind,source=${DATA_DIR},target=/data" \
  tsightler/ring-mqtt

echo "ring-mqtt started."
echo "RTSP should be reachable on port 8554 once your camera stream is requested."

