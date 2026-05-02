from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .extractors import HybridFeatureExtractor
from .movements import get_movement_scorers
from .types import CaptureScore

logger = logging.getLogger(__name__)


class ScoringService:
    def __init__(
        self,
        thresholds_path: Path,
        *,
        enable_pose_overlays: bool = True,
        max_pose_trace_frames: int = 48,
    ) -> None:
        self.thresholds = yaml.safe_load(thresholds_path.read_text(encoding="utf-8"))
        self.extractor = HybridFeatureExtractor(
            enable_pose_overlays=enable_pose_overlays,
            max_pose_trace_frames=max_pose_trace_frames,
        )
        self.scorers = get_movement_scorers()

    def analyze_capture(self, movement_key: str, side: str, video_path: Path) -> CaptureScore:
        scorer = self.scorers.get(movement_key)
        if scorer is None:
            raise KeyError(f"Unsupported movement '{movement_key}'.")
        extraction = self.extractor.extract(video_path, movement_key, side)
        thresholds = self.thresholds[movement_key]
        result = scorer.score(extraction, thresholds)
        logger.info(
            "SCORE | movement=%s side=%s source=%s",
            movement_key,
            side,
            extraction.source,
        )
        return result
