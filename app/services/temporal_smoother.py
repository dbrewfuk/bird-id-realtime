from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

from app.config import settings


@dataclass
class PredictionSnapshot:
    label: str
    score: float
    detected: bool
    timestamp: float


class TemporalSmoother:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._history: dict[str, deque[PredictionSnapshot]] = {}

    def update(
        self,
        client_id: str,
        label: str,
        score: float,
        detected: bool,
    ) -> dict:
        with self._lock:
            history = self._history.setdefault(
                client_id,
                deque(maxlen=settings.smoothing_window_size),
            )
            history.appendleft(
                PredictionSnapshot(
                    label=label,
                    score=score,
                    detected=detected,
                    timestamp=time.time(),
                )
            )
            return self._summarize(history)

    def clear(self, client_id: str) -> None:
        with self._lock:
            self._history.pop(client_id, None)

    def _summarize(self, history: deque[PredictionSnapshot]) -> dict:
        label_scores: dict[str, float] = {}
        total_weight = 0.0
        detection_weight = 0.0

        for index, item in enumerate(history):
            weight = settings.smoothing_decay**index
            total_weight += weight
            label_scores[item.label] = label_scores.get(item.label, 0.0) + (
                item.score * weight
            )
            if item.detected:
                detection_weight += weight

        best_label = max(label_scores, key=label_scores.get)
        normalized_score = label_scores[best_label] / total_weight if total_weight else 0.0
        detection_stability = detection_weight / total_weight if total_weight else 0.0
        return {
            "label": best_label,
            "score": round(normalized_score, 4),
            "confidence_percent": round(normalized_score * 100, 1),
            "detection_stability": round(detection_stability, 4),
            "frames_tracked": len(history),
        }


smoother = TemporalSmoother()
