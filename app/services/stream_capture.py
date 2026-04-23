from __future__ import annotations

import base64
import subprocess
import time
from dataclasses import dataclass
from io import BytesIO

from PIL import Image

from app.config import settings


@dataclass
class StreamFrame:
    image: Image.Image
    preview_data_url: str


class StreamCaptureError(RuntimeError):
    pass


class StreamCaptureService:
    _RETRIES = 3
    _RETRY_DELAY = 2.5

    def capture(self, stream_url: str) -> StreamFrame:
        url = stream_url.strip()
        if not url:
            raise StreamCaptureError("Stream URL is required")

        command = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-rtsp_transport",
            "tcp",
            "-i",
            url,
            "-frames:v",
            "1",
            "-f",
            "image2pipe",
            "-vcodec",
            "mjpeg",
            "-",
        ]

        last_error = ""
        for attempt in range(self._RETRIES):
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    timeout=settings.stream_capture_timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise StreamCaptureError("Timed out while reading the network stream") from exc

            if result.returncode == 0 and result.stdout:
                image_bytes = result.stdout
                image = Image.open(BytesIO(image_bytes)).convert("RGB")
                preview = "data:image/jpeg;base64," + base64.b64encode(image_bytes).decode()
                return StreamFrame(image=image, preview_data_url=preview)

            last_error = result.stderr.decode("utf-8", errors="ignore").strip()
            if attempt < self._RETRIES - 1:
                time.sleep(self._RETRY_DELAY)

        raise StreamCaptureError(last_error or "Could not read a frame from the stream")


stream_capture = StreamCaptureService()
