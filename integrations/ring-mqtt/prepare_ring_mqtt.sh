#!/bin/zsh
set -euo pipefail

DATA_DIR="${HOME}/.ring-mqtt"

mkdir -p "${DATA_DIR}"

if [[ ! -f "${DATA_DIR}/config.json" ]]; then
  cp "/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/config.example.json" \
    "${DATA_DIR}/config.json"
  echo "Created ${DATA_DIR}/config.json from template."
else
  echo "${DATA_DIR}/config.json already exists."
fi

echo "ring-mqtt data directory ready at ${DATA_DIR}"
echo "Edit config.json before continuing."

