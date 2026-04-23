# Scrypted Ring Setup on Mac

Best for:

- Users who want a polished UI and Ring plugin support
- Users who may later want broader smart-home integration

Current platform caveat:

- The current Scrypted docs say Docker is not supported on Mac/Windows because Scrypted requires host networking for Docker installs.
- On Mac, the documented path is the Scrypted Desktop App.
- The current Scrypted Desktop App docs also note that the desktop app requires a paid license.

References:

- Scrypted installation overview: https://docs.scrypted.app/installation.html
- Scrypted desktop app: https://docs.scrypted.app/install/desktop-app.html
- Add a camera / Ring plugin: https://docs.scrypted.app/add-camera.html

Recommended flow:

1. Install the Scrypted Desktop App on this Mac, or run Scrypted on a separate Linux/Proxmox box if you do not want the desktop-app route.
2. Open the Scrypted management console.
3. Install the `Ring Plugin`.
4. Sign in to Ring inside the plugin and complete any 2FA prompts.
5. Confirm your Ring camera appears and live view works inside Scrypted.
6. Expose or copy the stream source that Scrypted provides for the camera.
7. Paste that stream URL into this app under `Ring bridge stream`.

What to paste into this app:

- Use the camera stream URL that Scrypted exposes for the Ring device.
- If you proxy or restream it elsewhere, use that final reachable URL instead.

Troubleshooting notes:

- If you are staying on this Mac and do not want the desktop app or license path, `ring-mqtt` is the more practical local setup here.
- If you run Scrypted on another machine, use a reachable LAN URL from this Mac.

