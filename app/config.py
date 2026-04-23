from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Bird ID Realtime"
    model_repo: str = "dennisjooo/Birds-Classifier-EfficientNetB2"
    model_filename: str = "model.onnx"
    detector_model_url: str = (
        "https://github.com/dbrewfuk/bird-id-realtime/releases/download/v0.1.0/yolov8n.onnx"
    )
    detector_model_filename: str = "yolov8n.onnx"
    confidence_threshold: float = 0.18
    detection_confidence_threshold: float = 0.35
    detection_padding_ratio: float = 0.18
    frame_min_interval_ms: int = 1200
    smoothing_window_size: int = 6
    smoothing_decay: float = 0.72
    stream_capture_timeout_seconds: int = 12
    model_dir: Path = Path(__file__).resolve().parent / "models"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
