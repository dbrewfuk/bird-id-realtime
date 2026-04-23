from __future__ import annotations

import base64
import json
import threading
import urllib.request
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

from app.config import settings


@dataclass
class Prediction:
    label: str
    score: float


class BirdClassifier:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = False
        self._session: ort.InferenceSession | None = None
        self._input_name: str | None = None
        self._labels: dict[str, str] = {}
        self._image_mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self._image_std = np.array(
            [0.47853944, 0.4732864, 0.47434163],
            dtype=np.float32,
        )
        self._target_size = (260, 260)
        self._crop_size = (289, 289)

    def warmup(self) -> None:
        with self._lock:
            if self._ready:
                return

            settings.model_dir.mkdir(parents=True, exist_ok=True)
            self._download_if_missing("config.json")
            self._download_if_missing("preprocessor_config.json")
            self._download_if_missing(settings.model_filename)

            self._load_config(settings.model_dir / "config.json")
            self._load_preprocessor(settings.model_dir / "preprocessor_config.json")

            session_options = ort.SessionOptions()
            session_options.intra_op_num_threads = 1
            session_options.inter_op_num_threads = 1
            self._session = ort.InferenceSession(
                str(settings.model_dir / settings.model_filename),
                providers=["CPUExecutionProvider"],
                sess_options=session_options,
            )
            self._input_name = self._session.get_inputs()[0].name
            self._ready = True

    def decode_data_url(self, data_url: str) -> Image.Image:
        return self._decode_data_url(data_url)

    def predict_image(self, image: Image.Image, top_k: int = 3) -> dict:
        self.warmup()
        if self._session is None or self._input_name is None:
            raise RuntimeError("Model session failed to initialize")

        input_tensor = self._preprocess(image)
        logits = self._session.run(
            None,
            {self._input_name: input_tensor},
        )[0][0]
        probs = self._softmax(logits)
        top_indices = np.argsort(probs)[::-1][:top_k]
        predictions = [
            Prediction(
                label=self._labels.get(str(index), f"Bird {index}"),
                score=float(probs[index]),
            )
            for index in top_indices
        ]
        best = predictions[0]

        confident = best.score >= settings.confidence_threshold
        return {
            "best_match": self._format_prediction(best),
            "predictions": [self._format_prediction(item) for item in predictions],
            "confident": confident,
            "guidance": self._guidance_for(best.score, confident),
        }

    def predict_from_base64(self, data_url: str, top_k: int = 3) -> dict:
        image = self._decode_data_url(data_url)
        return self.predict_image(image, top_k=top_k)

    def _download_if_missing(self, filename: str) -> None:
        target = settings.model_dir / filename
        if target.exists():
            return

        url = (
            f"https://huggingface.co/{settings.model_repo}/resolve/main/{filename}"
        )
        urllib.request.urlretrieve(url, target)

    def _load_config(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        self._labels = config.get("id2label", {})

    def _load_preprocessor(self, path: Path) -> None:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
        size = config.get("size", {})
        crop_size = config.get("crop_size", {})
        self._target_size = (
            int(size.get("width", 260)),
            int(size.get("height", 260)),
        )
        self._crop_size = (
            int(crop_size.get("width", 289)),
            int(crop_size.get("height", 289)),
        )
        self._image_mean = np.array(
            config.get("image_mean", [0.485, 0.456, 0.406]),
            dtype=np.float32,
        )
        self._image_std = np.array(
            config.get("image_std", [0.229, 0.224, 0.225]),
            dtype=np.float32,
        )

    def _decode_data_url(self, data_url: str) -> Image.Image:
        if "," not in data_url:
            raise ValueError("Invalid frame payload")
        raw = data_url.split(",", 1)[1]
        image_bytes = BytesIO(base64.b64decode(raw))
        return Image.open(image_bytes).convert("RGB")

    def _preprocess(self, image: Image.Image) -> np.ndarray:
        image = ImageOps.exif_transpose(image)
        image = ImageOps.fit(
            image,
            self._crop_size,
            method=Image.Resampling.BILINEAR,
            centering=(0.5, 0.5),
        )
        image = image.resize(self._target_size, Image.Resampling.BILINEAR)

        array = np.asarray(image, dtype=np.float32) / 255.0
        array = (array - self._image_mean) / self._image_std
        array = np.transpose(array, (2, 0, 1))
        return np.expand_dims(array, axis=0).astype(np.float32)

    def _softmax(self, logits: np.ndarray) -> np.ndarray:
        shifted = logits - np.max(logits)
        exp_values = np.exp(shifted)
        return exp_values / np.sum(exp_values)

    def _format_prediction(self, prediction: Prediction) -> dict:
        return {
            "label": self._prettify_label(prediction.label),
            "score": round(prediction.score, 4),
            "confidence_percent": round(prediction.score * 100, 1),
        }

    def _prettify_label(self, label: str) -> str:
        words = label.replace("_", " ").split()
        if not words:
            return "Unknown bird"
        return " ".join(word.capitalize() for word in words)

    def _guidance_for(self, score: float, confident: bool) -> str:
        if confident:
            return "Tracking looks strong. Keep the bird centered for steadier results."
        if score >= settings.confidence_threshold * 0.75:
            return "Close, but not fully confident yet. Move closer or reduce background clutter."
        return "Low confidence. Try better light, a steadier frame, or a tighter crop on the bird."


classifier = BirdClassifier()
