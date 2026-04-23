from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageOps

from app.config import settings


# YOLOv8 COCO class indices (0-indexed)
YOLO_BIRD_CLASS_ID   = 14
YOLO_PERSON_CLASS_ID = 0
YOLO_INPUT_SIZE      = 640
YOLO_NMS_IOU_THRESHOLD = 0.45


@dataclass
class BirdDetection:
    score: float
    bbox: tuple[int, int, int, int]
    normalized_bbox: dict[str, float]


@dataclass
class DetectionContext:
    birds: list[BirdDetection]
    person_score: float | None

    @property
    def bird(self) -> BirdDetection | None:
        """Backward-compat: the highest-scoring bird, or None."""
        return self.birds[0] if self.birds else None


class BirdDetector:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ready = False
        self._session: ort.InferenceSession | None = None
        self._input_name: str | None = None
        self._output_name: str | None = None

    def warmup(self) -> None:
        with self._lock:
            if self._ready:
                return

            settings.model_dir.mkdir(parents=True, exist_ok=True)
            model_path = settings.model_dir / settings.detector_model_filename

            if not model_path.exists() or self._looks_like_lfs_pointer(model_path):
                self._export_yolov8(model_path)

            self._session = ort.InferenceSession(
                str(model_path),
                providers=["CPUExecutionProvider"],
            )
            self._input_name  = self._session.get_inputs()[0].name
            self._output_name = self._session.get_outputs()[0].name
            self._ready = True

    def inspect(self, image: Image.Image) -> DetectionContext:
        self.warmup()
        if self._session is None:
            raise RuntimeError("Bird detector failed to initialize")

        image = ImageOps.exif_transpose(image).convert("RGB")
        orig_w, orig_h = image.size

        letterboxed, scale, pad_x, pad_y = self._letterbox(image)

        arr = np.asarray(letterboxed, dtype=np.float32) / 255.0   # HWC
        arr = np.transpose(arr, (2, 0, 1))[None]                  # BCHW

        raw = self._session.run(
            [self._output_name], {self._input_name: arr}
        )[0]  # (1, 84, 8400)

        birds, person_score = self._parse(raw, orig_w, orig_h, scale, pad_x, pad_y)

        # Highest-confidence first; cap at 4 to keep inference time sane
        birds.sort(key=lambda d: d.score, reverse=True)
        return DetectionContext(birds=birds[:4], person_score=person_score)

    def detect(self, image: Image.Image) -> BirdDetection | None:
        return self.inspect(image).bird

    def crop_detected_bird(
        self, image: Image.Image, detection: BirdDetection
    ) -> Image.Image:
        w, h = image.size
        x1, y1, x2, y2 = detection.bbox
        bw, bh = x2 - x1, y2 - y1
        px = int(round(bw * settings.detection_padding_ratio))
        py = int(round(bh * settings.detection_padding_ratio))
        crop = (
            max(0, x1 - px), max(0, y1 - py),
            min(w, x2 + px), min(h, y2 + py),
        )
        return image.crop(crop)

    # ── Private ──────────────────────────────────────────────────

    def _letterbox(
        self, image: Image.Image, size: int = YOLO_INPUT_SIZE
    ) -> tuple[Image.Image, float, int, int]:
        w, h = image.size
        scale   = min(size / w, size / h)
        new_w   = int(round(w * scale))
        new_h   = int(round(h * scale))
        resized = image.resize((new_w, new_h), Image.Resampling.BILINEAR)
        pad_x   = (size - new_w) // 2
        pad_y   = (size - new_h) // 2
        padded  = Image.new("RGB", (size, size), (114, 114, 114))
        padded.paste(resized, (pad_x, pad_y))
        return padded, scale, pad_x, pad_y

    def _parse(
        self,
        raw: np.ndarray,
        orig_w: int,
        orig_h: int,
        scale: float,
        pad_x: int,
        pad_y: int,
    ) -> tuple[list[BirdDetection], float | None]:
        # raw: (1, 84, 8400) → (8400, 84)
        preds = raw[0].T

        bird_scores   = preds[:, 4 + YOLO_BIRD_CLASS_ID]
        person_scores = preds[:, 4 + YOLO_PERSON_CLASS_ID]

        # Best person score (for skip-classification warning)
        max_person = float(person_scores.max()) if len(person_scores) else 0.0
        person_score = (
            max_person
            if max_person >= settings.detection_confidence_threshold
            else None
        )

        # Filter to birds above threshold
        mask = bird_scores >= settings.detection_confidence_threshold
        if not np.any(mask):
            return [], person_score

        filtered       = preds[mask]
        scores_filtered = bird_scores[mask]

        cx, cy = filtered[:, 0], filtered[:, 1]
        bw, bh = filtered[:, 2], filtered[:, 3]

        # cx/cy/bw/bh are in letterboxed 640-px space
        x1 = cx - bw / 2
        y1 = cy - bh / 2
        x2 = cx + bw / 2
        y2 = cy + bh / 2
        boxes_lb = np.stack([x1, y1, x2, y2], axis=1)

        keep = self._nms(boxes_lb, scores_filtered)

        birds: list[BirdDetection] = []
        for i in keep:
            # Map back to original image coordinates
            ox1 = max(0.0,    (boxes_lb[i, 0] - pad_x) / scale)
            oy1 = max(0.0,    (boxes_lb[i, 1] - pad_y) / scale)
            ox2 = min(orig_w, (boxes_lb[i, 2] - pad_x) / scale)
            oy2 = min(orig_h, (boxes_lb[i, 3] - pad_y) / scale)

            if ox2 <= ox1 or oy2 <= oy1:
                continue

            birds.append(BirdDetection(
                score=float(scores_filtered[i]),
                bbox=(int(round(ox1)), int(round(oy1)),
                      int(round(ox2)), int(round(oy2))),
                normalized_bbox={
                    "x":      round(ox1 / orig_w, 4),
                    "y":      round(oy1 / orig_h, 4),
                    "width":  round((ox2 - ox1) / orig_w, 4),
                    "height": round((oy2 - oy1) / orig_h, 4),
                },
            ))

        return birds, person_score

    def _nms(
        self,
        boxes: np.ndarray,
        scores: np.ndarray,
        iou_threshold: float = YOLO_NMS_IOU_THRESHOLD,
    ) -> list[int]:
        x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
        areas = (x2 - x1) * (y2 - y1)
        order = scores.argsort()[::-1]

        keep: list[int] = []
        while order.size > 0:
            i = int(order[0])
            keep.append(i)

            ix1 = np.maximum(x1[i], x1[order[1:]])
            iy1 = np.maximum(y1[i], y1[order[1:]])
            ix2 = np.minimum(x2[i], x2[order[1:]])
            iy2 = np.minimum(y2[i], y2[order[1:]])

            inter = (np.maximum(0.0, ix2 - ix1) *
                     np.maximum(0.0, iy2 - iy1))
            iou   = inter / (areas[i] + areas[order[1:]] - inter + 1e-6)
            order = order[1:][iou <= iou_threshold]

        return keep

    def _export_yolov8(self, output_path: Path) -> None:
        """Generate yolov8n.onnx via ultralytics if the model is missing."""
        try:
            import shutil
            from ultralytics import YOLO

            model = YOLO("yolov8n.pt")
            model.export(
                format="onnx",
                imgsz=YOLO_INPUT_SIZE,
                opset=12,
                simplify=True,
            )
            src = Path("yolov8n.onnx")
            if src.exists():
                shutil.move(str(src), str(output_path))
        except ImportError as exc:
            raise RuntimeError(
                f"{settings.detector_model_filename} not found. "
                "Run: pip install ultralytics && "
                "python -c \"from ultralytics import YOLO; "
                "YOLO('yolov8n.pt').export(format='onnx')\""
            ) from exc

    def _looks_like_lfs_pointer(self, path: Path) -> bool:
        try:
            with open(path, "rb") as f:
                return f.read(64).startswith(
                    b"version https://git-lfs.github.com/spec/v1"
                )
        except OSError:
            return False


detector = BirdDetector()
