"""Data models for frigate-camera-manager."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import time


@dataclass
class Camera:
    id: str
    name: str
    enabled: bool
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, camera_id: str, data: dict) -> "Camera":
        detect = data.get("detect", {})
        return cls(
            id=camera_id,
            name=camera_id,
            enabled=data.get("enabled", True),
            width=detect.get("width"),
            height=detect.get("height"),
            fps=detect.get("fps"),
            raw=data,
        )


@dataclass
class CameraStatus:
    id: str
    online: bool
    fps: Optional[float] = None
    skipped_fps: Optional[float] = None
    detection_enabled: Optional[bool] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_stats(cls, camera_id: str, stats: dict) -> "CameraStatus":
        cam = stats.get("cameras", {}).get(camera_id, {})
        return cls(
            id=camera_id,
            online=cam.get("camera_fps", 0) > 0,
            fps=cam.get("camera_fps"),
            skipped_fps=cam.get("skipped_fps"),
            detection_enabled=cam.get("detection_enabled"),
            raw=cam,
        )


@dataclass
class FrigateEvent:
    id: str
    camera: str
    label: str
    score: float
    start_time: float
    end_time: Optional[float]
    zones: List[str]
    has_snapshot: bool
    has_clip: bool
    raw: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: dict) -> "FrigateEvent":
        return cls(
            id=data.get("id", ""),
            camera=data.get("camera", ""),
            label=data.get("label", "unknown"),
            score=data.get("score", 0.0),
            start_time=data.get("start_time", 0.0),
            end_time=data.get("end_time"),
            zones=data.get("zones", []),
            has_snapshot=data.get("has_snapshot", False),
            has_clip=data.get("has_clip", False),
            raw=data,
        )

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.end_time:
            return self.end_time - self.start_time
        return None


@dataclass
class ReviewSummary:
    camera: str
    window_hours: float
    total_events: int
    by_label: Dict[str, int]
    alerts: int
    detections: int
    events: List[FrigateEvent] = field(default_factory=list)


@dataclass
class LogAnalysis:
    raw_logs: str
    error_lines: List[str]
    suggested_fixes: List[str]
    severity: str  # "ok" | "warning" | "error" | "critical"


@dataclass
class MediaEntry:
    key: str
    data: bytes
    media_type: str  # "jpeg" | "gif" | "mp4"
    created_at: float = field(default_factory=time.time)
    camera_id: Optional[str] = None
    event_id: Optional[str] = None

    def is_expired(self, ttl_seconds: int = 86400) -> bool:
        return (time.time() - self.created_at) > ttl_seconds
