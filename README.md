# Bird ID Realtime

A lightweight bird-identification MVP that samples frames from a live browser video feed, detects bird regions, and classifies the detected crop with a bird-species ONNX model.

## What it does

- Captures a live webcam feed in the browser
- Lets you choose among available browser camera devices, including external webcams
- Samples live frames every few moments
- Sends frames to a FastAPI backend
- Detects `bird` objects with a COCO SSD-MobileNet ONNX detector
- Crops the detected bird region before classification
- Runs bird-species classification with an ONNX model from Hugging Face
- Applies backend temporal smoothing per browser session
- Can also sample a network stream URL for Ring restream setups
- Returns top predictions plus detection, stability, and guidance signals

## Notes

- Detection uses a general COCO bird detector, so it can find bird regions without a custom training step.
- If no bird is detected, the app now skips species classification entirely.
- First startup downloads the model files into `app/models/`.
- Best results come from steady footage, good light, and a tighter crop on the bird.
- Ring setup assets live in [integrations/README.md](/Users/new/Desktop/bird-id-realtime/integrations/README.md:1).

## Ring Camera

Ring does not expose a simple direct local RTSP feed to this app, so the practical path is to bridge Ring into a local stream first, then paste that stream URL into the app.

Working options:

- Scrypted with the Ring plugin and WebRTC stack
- `ring-mqtt` with its documented local RTSP/go2rtc video streaming setup

Once you have a local or reachable `rtsp://...` or `http(s)://...m3u8` URL:

1. Open the app.
2. Switch `Source` to `Ring bridge stream`.
3. Paste the stream URL.
4. Click `Start source`.

If your external camera shows up as a normal webcam in the browser, you can also pick it directly under `Camera device`.

## Run it

1. Create a virtual environment:
   `python3 -m venv .venv`
2. Activate it:
   `source .venv/bin/activate`
3. Install dependencies:
   `pip install -e .`
4. Start the app:
   `uvicorn app.main:app --reload`
5. Open:
   `http://127.0.0.1:8000`

## Next upgrades

- Add bird-species smoothing that blends the full top-k history, not only the leading label
- Swap in a regional or custom-trained species model
- Persist sightings with timestamps, GPS, and thumbnails
