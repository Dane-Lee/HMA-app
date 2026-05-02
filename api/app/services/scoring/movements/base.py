from __future__ import annotations

from abc import ABC, abstractmethod

from ..types import CaptureScore, ExtractionResult


class MovementScorer(ABC):
    key: str

    @abstractmethod
    def score(
        self,
        extraction: ExtractionResult,
        thresholds: dict[str, float],
    ) -> CaptureScore:
        raise NotImplementedError

    def build_score(
        self,
        extraction: ExtractionResult,
        faults: list[str],
        placeholder_faults: list[str] | None = None,
    ) -> CaptureScore:
        placeholder_faults = placeholder_faults or []
        actionable_faults = [fault for fault in faults if fault not in placeholder_faults]
        score = max(0, 3 - len(actionable_faults))
        confidence = 0.82 if extraction.source == "mediapipe" else 0.38
        metrics = {"score": float(score), **extraction.features.debug_metrics}
        return CaptureScore(
            movement_key=self.key,
            side=extraction.context.side,
            score=score,
            detected_faults=faults,
            confidence=round(confidence, 2),
            metrics=metrics,
            source=extraction.source,
            pose_trace=extraction.pose_trace,
            quality=extraction.quality,
        )
