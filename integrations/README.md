# Ring Integration Paths

This app supports two practical Ring camera paths:

- `Scrypted` with the Ring plugin
- `ring-mqtt` with its RTSP video streaming bridge

Open these guides:

- [Scrypted on Mac](./scrypted-ring-macos.md)
- [ring-mqtt on Mac with Docker](./ring-mqtt-macos.md)

When either path gives you a stream URL:

1. Open the app at `http://127.0.0.1:8001`
2. Set `Source` to `Ring bridge stream`
3. Paste the RTSP or HLS URL
4. Click `Start source`

Important:

- The app will only classify when a bird is actually detected.
- Ring streaming is cloud-backed, not local. Continuous viewing can drain battery cameras and suppress motion notifications while live view is active.

