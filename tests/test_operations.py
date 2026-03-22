"""Unit tests for operations.py — mocked client."""

from unittest.mock import MagicMock

from frigate_camera_manager.cache import MediaCache
from frigate_camera_manager.models import FrigateEvent
from frigate_camera_manager.operations import (
    analyze_logs,
    format_camera_list,
    format_log_analysis,
    format_review_summary,
    list_cameras,
    summarize_review,
)


def make_client(cameras=None, stats=None, events=None, review=None, logs=None):
    c = MagicMock()
    c.list_cameras.return_value = cameras or {
        "front_yard": {"enabled": True, "detect": {"width": 1920, "height": 1080, "fps": 10}},
        "back_yard": {"enabled": True, "detect": {}},
    }
    c.get_stats.return_value = stats or {
        "cameras": {
            "front_yard": {"camera_fps": 10.0, "skipped_fps": 0.0, "detection_enabled": True},
            "back_yard": {"camera_fps": 0.0, "detection_enabled": False},
        }
    }
    c.get_events.return_value = events or [
        {
            "id": "abc1", "camera": "front_yard", "label": "person", "score": 0.9,
            "start_time": 1000.0, "end_time": 1010.0, "zones": [],
            "has_snapshot": True, "has_clip": True,
        },
        {
            "id": "abc2", "camera": "front_yard", "label": "car", "score": 0.8,
            "start_time": 1020.0, "end_time": 1030.0, "zones": [],
            "has_snapshot": True, "has_clip": False,
        },
    ]
    c.get_review.return_value = review or [
        {"severity": "alert"},
        {"severity": "detection"},
        {"severity": "detection"},
    ]
    c.get_logs.return_value = logs or "Everything is fine."
    return c


class TestListCameras:
    def test_returns_camera_objects(self):
        client = make_client()
        cameras = list_cameras(client)
        ids = [c.id for c in cameras]
        assert "front_yard" in ids
        assert "back_yard" in ids

    def test_camera_fields(self):
        client = make_client()
        cameras = list_cameras(client)
        fy = next(c for c in cameras if c.id == "front_yard")
        assert fy.enabled is True
        assert fy.width == 1920


class TestReviewSummary:
    def test_summary_totals(self):
        client = make_client()
        s = summarize_review(client, hours=24.0)
        assert s.total_events == 2
        assert s.alerts == 1
        assert s.detections == 2
        assert s.by_label["person"] == 1
        assert s.by_label["car"] == 1

    def test_format_output(self):
        client = make_client()
        s = summarize_review(client, hours=24.0)
        text = format_review_summary(s)
        assert "person" in text
        assert "car" in text


class TestLogAnalysis:
    def test_no_errors(self):
        client = make_client(logs="INFO: System running normally.")
        analysis = analyze_logs(client)
        assert analysis.severity == "ok"
        assert len(analysis.error_lines) == 0

    def test_detects_error_lines(self):
        client = make_client(logs="ERROR: unable to open video source for front_yard")
        analysis = analyze_logs(client)
        assert analysis.severity == "error"
        assert len(analysis.error_lines) >= 1

    def test_suggests_fix(self):
        client = make_client(logs="ERROR: unable to open video source for front_yard")
        analysis = analyze_logs(client)
        assert len(analysis.suggested_fixes) >= 1
        assert "RTSP" in analysis.suggested_fixes[0] or "stream" in analysis.suggested_fixes[0].lower()

    def test_critical_severity(self):
        client = make_client(logs="CRITICAL: detect process died unexpectedly")
        analysis = analyze_logs(client)
        assert analysis.severity == "critical"

    def test_format_output(self):
        client = make_client(logs="ERROR: ffmpeg failed to start for back_yard")
        analysis = analyze_logs(client)
        text = format_log_analysis(analysis)
        assert "ffmpeg" in text.lower() or "error" in text.lower()
