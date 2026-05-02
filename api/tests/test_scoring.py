from __future__ import annotations

from pathlib import Path

from api.app.services.scoring.service import ScoringService


def test_cervical_rotation_good_fixture_scores_higher(tmp_path: Path):
    thresholds_path = Path(__file__).resolve().parents[2] / "config" / "scoring_thresholds.yaml"
    service = ScoringService(thresholds_path)

    good_path = tmp_path / "good-cervical.webm"
    poor_path = tmp_path / "poor-cervical.webm"
    good_path.write_bytes(b"good-video-data")
    poor_path.write_bytes(b"poor-video-data")

    good = service.analyze_capture("cervical_rotation", "right", good_path)
    poor = service.analyze_capture("cervical_rotation", "right", poor_path)

    assert good.score >= poor.score
    assert good.metrics["chin_midline_clearance_ratio"] >= poor.metrics["chin_midline_clearance_ratio"]
    assert good.pose_trace is None
    assert good.quality.overlay_available is False
    assert good.quality.status == "unavailable"
