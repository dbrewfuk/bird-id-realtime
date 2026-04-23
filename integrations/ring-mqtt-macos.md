# ring-mqtt Setup on Mac with Docker

Best for:

- Users who want a practical RTSP bridge into this app
- Users who are comfortable with Docker and a one-time 2FA setup

References:

- Docker installation: https://github.com/tsightler/ring-mqtt/wiki/Installation-%28Docker%29
- Video streaming: https://github.com/tsightler/ring-mqtt/wiki/Video-Streaming
- Configuration details: https://github.com/tsightler/ring-mqtt/wiki/Configuration-Details

What this gives you:

- An on-demand RTSP stream per Ring camera
- A local RTSP URL shaped like:
  `rtsp://<user>:<pass>@<host>:8554/<camera_id>_live`

Project helper files:

- Config template: [ring-mqtt/config.example.json](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/config.example.json:1)
- Prepare data dir: [prepare_ring_mqtt.sh](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/prepare_ring_mqtt.sh:1)
- Interactive token init: [init_ring_mqtt.sh](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/init_ring_mqtt.sh:1)
- Start service: [start_ring_mqtt.sh](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/start_ring_mqtt.sh:1)
- Stop service: [stop_ring_mqtt.sh](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/stop_ring_mqtt.sh:1)
- Prepare Mosquitto: [prepare_mosquitto.sh](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/prepare_mosquitto.sh:1)
- Start Mosquitto: [start_mosquitto.sh](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/start_mosquitto.sh:1)
- Stop Mosquitto: [stop_mosquitto.sh](/Users/new/Desktop/bird-id-realtime/integrations/ring-mqtt/stop_mosquitto.sh:1)

Recommended flow:

1. Start Docker Desktop on the Mac.
2. Run `prepare_mosquitto.sh`.
3. Run `prepare_ring_mqtt.sh`.
4. Edit `~/.ring-mqtt/config.json` and keep `mqtt_url` pointed at `mqtt://host.docker.internal:1883` unless your broker lives elsewhere.
5. Run `start_mosquitto.sh`.
6. Run `init_ring_mqtt.sh` and complete the Ring login and 2FA prompts.
7. Run `start_ring_mqtt.sh`.
8. Find the generated RTSP live path for your camera from ring-mqtt or your MQTT/Home Assistant view.
9. Paste that RTSP URL into this app under `Ring bridge stream`.

Notes:

- `ring-mqtt` video still streams through Ring’s cloud, even though you access it locally over RTSP.
- Keeping Ring cameras streaming continuously can drain batteries, increase heat, and suppress motion notifications while the live stream is active.
- TCP port `8554` is the documented RTSP default for external clients.

MQTT note:

- `ring-mqtt` expects an MQTT broker. If you do not already have one, the fastest path is to run Mosquitto separately and point `mqtt_url` at it.
