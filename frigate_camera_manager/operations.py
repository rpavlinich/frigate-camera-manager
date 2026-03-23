"""High-level operations: snapshots, GIFs, event summaries, log analysis."""

import io
import re
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from PIL import Image, ImageStat

from .cache import MediaCache, default_cache
from .client import FrigateApiClient
from .models import (
    Camera,
    CameraStatus,
    FrigateEvent,
    LogAnalysis,
    ReviewSummary,
)

# ── Known error patterns → suggested fixes ───────────────────────────────────
LOG_PATTERNS = [
    (re.compile(r"unable to open video source", re.I),
     "Camera stream is unreachable. Check RTSP URL, network connectivity, and camera power."),
    (re.compile(r"connection refused", re.I),
     "Frigate cannot connect to the camera. Verify the stream URL and that the camera is online."),
    (re.compile(r"out of memory|oom", re.I),
     "System is low on memory. Consider reducing detection resolution or limiting active cameras."),
    (re.compile(r"detect process.*died|detector.*crash", re.I),
     "Object detection process crashed. Check GPU/CPU load and detector config."),
    (re.compile(r"ffmpeg.*error|failed to start ffmpeg", re.I),
     "FFmpeg error — check stream URL format and codec compatibility."),
    (re.compile(r"database.*lock|sqlite.*lock", re.I),
     "Database lock contention. Ensure only one Frigate instance is running."),
    (re.compile(r"disk.*full|no space left", re.I),
     "Disk is full. Free space or adjust retention/storage settings in Frigate config."),
    (re.compile(r"permission denied", re.I),
     "Permission error — check file/device permissions for Frigate process."),
    (re.compile(r"invalid.*config|config.*error|yaml.*error", re.I),
     "Configuration error. Validate your frigate.yml with the Frigate config checker."),
    (re.compile(r"timeout", re.I),
     "Timeout communicating with a camera or service. Check network latency and camera health."),
]


# ── Camera listing ────────────────────────────────────────────────────────────
def list_cameras(client: FrigateApiClient) -> List[Camera]:
    raw = client.list_cameras()
    return [Camera.from_api(cam_id, data) for cam_id, data in raw.items()]


# ── Connectivity monitoring ───────────────────────────────────────────────────
def check_connectivity(client: FrigateApiClient) -> List[CameraStatus]:
    try:
        stats = client.get_stats()
    except Exception as e:
        raise RuntimeError(f"Failed to fetch stats: {e}") from e

    cameras_raw = stats.get("cameras", {})
    return [CameraStatus.from_stats(cam_id, stats) for cam_id in cameras_raw]


# ── Snapshots ─────────────────────────────────────────────────────────────────
def _is_near_black_placeholder(image_bytes: bytes, threshold: float = 5.0) -> bool:
    """Detect Frigate's bogus near-black placeholder snapshots.

    In this setup, bad snapshots are tiny JPEGs with almost every pixel near 1/255.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
        stat = ImageStat.Stat(image)
        return stat.mean[0] <= threshold and stat.extrema[0][1] <= threshold
    except Exception:
        return False


def fetch_snapshot(
    client: FrigateApiClient,
    camera_id: str,
    cache: MediaCache = default_cache,
) -> bytes:
    """Fetch and cache the latest snapshot for a camera, and save to media directory."""
    cache_key = f"snapshot:{camera_id}"
    existing = cache.get(cache_key)
    if existing and not _is_near_black_placeholder(existing.data):
        return existing.data
    if existing and _is_near_black_placeholder(existing.data):
        cache.clear()

    data = client.get_camera_snapshot(camera_id)
    if _is_near_black_placeholder(data):
        raise RuntimeError(
            f"Snapshot for {camera_id} looks like Frigate's black placeholder frame; refusing to cache it."
        )

    cache.put_bytes(cache_key, data, media_type="jpeg", camera_id=camera_id)

    # Also save to media directory with timestamp
    try:
        from pathlib import Path
        import time

        media_dir = Path("/root/.openclaw/workspace/skills/frigate-camera-manager/media/snapshots") / camera_id
        media_dir.mkdir(parents=True, exist_ok=True)

        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        file_path = media_dir / f"{timestamp}.jpg"

        with open(file_path, "wb") as f:
            f.write(data)
    except Exception:
        # Don't let media saving errors break the main functionality
        pass

    return data


# ── GIF creation ─────────────────────────────────────────────────────────────
def create_review_gif(
    client: FrigateApiClient,
    camera_id: str,
    event_ids: List[str],
    cache: MediaCache = default_cache,
    fps: int = 5,
) -> bytes:
    """Build a GIF from thumbnails of a list of event IDs."""
    try:
        import imageio.v3 as iio
        import numpy as np
    except ImportError:
        raise RuntimeError(
            "imageio is required for GIF generation. Install with: pip install imageio pillow"
        )

    cache_key = f"gif:{camera_id}:{'-'.join(event_ids[:5])}"
    existing = cache.get(cache_key)
    if existing:
        return existing.data

    frames = []
    for eid in event_ids:
        try:
            thumb_bytes = client.get_event_thumbnail(eid)
            frame = iio.imread(io.BytesIO(thumb_bytes))
            frames.append(frame)
        except Exception:
            continue  # skip frames that fail

    if not frames:
        raise ValueError("No frames could be loaded for the selected events.")

    buf = io.BytesIO()
    iio.imwrite(buf, frames, format_hint=".gif", fps=fps)
    gif_bytes = buf.getvalue()

    cache.put_bytes(cache_key, gif_bytes, media_type="gif", camera_id=camera_id)
    return gif_bytes


# ── Review event summary ──────────────────────────────────────────────────────
def summarize_review(
    client: FrigateApiClient,
    camera_id: Optional[str] = None,
    hours: float = 24.0,
) -> ReviewSummary:
    """Fetch and summarize review events over the last N hours."""
    after = time.time() - (hours * 3600)
    raw_events = client.get_events(camera=camera_id, after=after, limit=200)
    events = [FrigateEvent.from_api(e) for e in raw_events]

    by_label: Dict[str, int] = {}
    for ev in events:
        by_label[ev.label] = by_label.get(ev.label, 0) + 1

    # Frigate distinguishes alerts (motion + object) from detections
    raw_review = client.get_review(camera=camera_id, after=after, limit=200)
    alerts = sum(1 for r in raw_review if r.get("severity") == "alert")
    detections = sum(1 for r in raw_review if r.get("severity") == "detection")

    return ReviewSummary(
        camera=camera_id or "all",
        window_hours=hours,
        total_events=len(events),
        by_label=by_label,
        alerts=alerts,
        detections=detections,
        events=events,
    )


# ── Log analysis ─────────────────────────────────────────────────────────────
def analyze_logs(
    client: FrigateApiClient,
    process: str = "frigate",
) -> LogAnalysis:
    """Fetch logs, extract errors, and propose fixes."""
    raw = client.get_logs(process=process)

    if isinstance(raw, list):
        # Some Frigate versions return a list of log line dicts
        lines = [entry.get("message", str(entry)) for entry in raw]
        raw_text = "\n".join(lines)
    else:
        raw_text = str(raw)
        lines = raw_text.splitlines()

    error_lines = [
        line for line in lines
        if any(kw in line.lower() for kw in ("error", "critical", "exception", "fatal", "failed"))
    ]

    suggested_fixes = []
    matched_patterns = set()
    for line in error_lines:
        for pattern, fix in LOG_PATTERNS:
            if pattern.search(line) and fix not in matched_patterns:
                suggested_fixes.append(fix)
                matched_patterns.add(fix)

    if not error_lines:
        severity = "ok"
    elif any("critical" in l.lower() or "fatal" in l.lower() for l in error_lines):
        severity = "critical"
    elif any("error" in l.lower() for l in error_lines):
        severity = "error"
    else:
        severity = "warning"

    return LogAnalysis(
        raw_logs=raw_text,
        error_lines=error_lines,
        suggested_fixes=suggested_fixes,
        severity=severity,
    )


# ── Formatting helpers (for chat surfaces) ───────────────────────────────────
def format_camera_list(cameras: List[Camera], statuses: Optional[List[CameraStatus]] = None) -> str:
    status_map = {s.id: s for s in statuses} if statuses else {}
    lines = ["**Cameras**"]
    for cam in cameras:
        st = status_map.get(cam.id)
        if st:
            icon = "🟢" if st.online else "🔴"
            fps_str = f" | {st.fps:.1f} fps" if st.fps is not None else ""
            lines.append(f"{icon} **{cam.id}**{fps_str} ({'enabled' if cam.enabled else 'disabled'})")
        else:
            lines.append(f"⚪ **{cam.id}** ({'enabled' if cam.enabled else 'disabled'})")
    return "\n".join(lines)


def format_review_summary(summary: ReviewSummary) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"**Review Summary — {summary.camera} | last {summary.window_hours:.0f}h** _{ts}_",
        f"Total events: **{summary.total_events}** | Alerts: **{summary.alerts}** | Detections: **{summary.detections}**",
        "",
        "**By label:**",
    ]
    for label, count in sorted(summary.by_label.items(), key=lambda x: -x[1]):
        lines.append(f"  • {label}: {count}")
    return "\n".join(lines)


def format_log_analysis(analysis: LogAnalysis) -> str:
    icons = {"ok": "✅", "warning": "⚠️", "error": "❌", "critical": "🚨"}
    icon = icons.get(analysis.severity, "❓")
    lines = [f"{icon} **Log Analysis — severity: {analysis.severity.upper()}**", ""]

    if not analysis.error_lines:
        lines.append("No errors found in logs.")
    else:
        lines.append(f"**{len(analysis.error_lines)} error line(s) found:**")
        for l in analysis.error_lines[:10]:  # cap at 10 in chat
            lines.append(f"  `{l.strip()[:120]}`")
        if len(analysis.error_lines) > 10:
            lines.append(f"  _...and {len(analysis.error_lines) - 10} more_")

    if analysis.suggested_fixes:
        lines.append("")
        lines.append("**Suggested fixes:**")
        for i, fix in enumerate(analysis.suggested_fixes, 1):
            lines.append(f"  {i}. {fix}")

    return "\n".join(lines)
