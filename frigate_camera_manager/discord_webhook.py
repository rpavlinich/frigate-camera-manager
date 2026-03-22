"""Discord webhook integration for camera event notifications."""

import io
import os
import time
from typing import Dict, List, Optional

import requests

# ── Config ────────────────────────────────────────────────────────────────────
# Set DISCORD_DEFAULT_WEBHOOK_URL as a fallback for all cameras.
# Per-camera overrides can be passed at runtime or stored in CAMERA_WEBHOOKS.
DEFAULT_WEBHOOK_URL = os.environ.get("DISCORD_DEFAULT_WEBHOOK_URL", "")

# Optional: dict of camera_id -> webhook URL, loaded from env or set at runtime
CAMERA_WEBHOOKS: Dict[str, str] = {}


def register_webhook(camera_id: str, webhook_url: str) -> None:
    """Register a Discord webhook URL for a specific camera."""
    CAMERA_WEBHOOKS[camera_id] = webhook_url


def get_webhook_url(camera_id: Optional[str] = None) -> Optional[str]:
    """Resolve the webhook URL for a camera (falls back to default)."""
    if camera_id and camera_id in CAMERA_WEBHOOKS:
        return CAMERA_WEBHOOKS[camera_id]
    return DEFAULT_WEBHOOK_URL or None


# ── Senders ───────────────────────────────────────────────────────────────────

def send_snapshot(
    camera_id: str,
    image_bytes: bytes,
    label: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """Post a JPEG snapshot to a Discord channel via webhook.

    Returns True on success, False on failure.
    """
    url = webhook_url or get_webhook_url(camera_id)
    if not url:
        raise ValueError(f"No Discord webhook URL configured for camera '{camera_id}'.")

    caption = f"📸 **{camera_id}** snapshot"
    if label:
        caption += f" — {label}"

    files = {"file": (f"{camera_id}_snapshot.jpg", io.BytesIO(image_bytes), "image/jpeg")}
    payload = {"content": caption}

    resp = requests.post(url, data=payload, files=files, timeout=15)
    resp.raise_for_status()
    return True


def send_gif(
    camera_id: str,
    gif_bytes: bytes,
    event_summary: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """Post a review GIF to Discord via webhook."""
    url = webhook_url or get_webhook_url(camera_id)
    if not url:
        raise ValueError(f"No Discord webhook URL configured for camera '{camera_id}'.")

    caption = f"🎞️ **{camera_id}** review clip"
    if event_summary:
        caption += f"\n{event_summary}"

    files = {"file": (f"{camera_id}_review.gif", io.BytesIO(gif_bytes), "image/gif")}
    payload = {"content": caption}

    resp = requests.post(url, data=payload, files=files, timeout=30)
    resp.raise_for_status()
    return True


def send_text_alert(
    camera_id: str,
    message: str,
    webhook_url: Optional[str] = None,
) -> bool:
    """Post a plain text alert (e.g. log analysis, connectivity warning) to Discord."""
    url = webhook_url or get_webhook_url(camera_id)
    if not url:
        raise ValueError(f"No Discord webhook URL configured for camera '{camera_id}'.")

    payload = {"content": message[:2000]}  # Discord message limit
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    return True


def send_review_summary(
    camera_id: str,
    summary_text: str,
    gif_bytes: Optional[bytes] = None,
    webhook_url: Optional[str] = None,
) -> bool:
    """Post a review summary (with optional GIF) to Discord."""
    url = webhook_url or get_webhook_url(camera_id)
    if not url:
        raise ValueError(f"No Discord webhook URL configured for camera '{camera_id}'.")

    if gif_bytes:
        files = {"file": (f"{camera_id}_review.gif", io.BytesIO(gif_bytes), "image/gif")}
        payload = {"content": summary_text[:2000]}
        resp = requests.post(url, data=payload, files=files, timeout=30)
    else:
        payload = {"content": summary_text[:2000]}
        resp = requests.post(url, json=payload, timeout=15)

    resp.raise_for_status()
    return True


def send_log_alert(
    analysis_text: str,
    camera_id: str = "frigate",
    webhook_url: Optional[str] = None,
) -> bool:
    """Post a log analysis alert to Discord."""
    return send_text_alert(camera_id, analysis_text, webhook_url=webhook_url)


# ── Batch helpers ─────────────────────────────────────────────────────────────

def notify_all_cameras(
    message: str,
    camera_ids: Optional[List[str]] = None,
) -> Dict[str, bool]:
    """Send the same message to all registered camera webhooks.

    Returns a dict of camera_id -> success status.
    """
    results: Dict[str, bool] = {}
    targets = camera_ids or list(CAMERA_WEBHOOKS.keys())
    for cam_id in targets:
        try:
            results[cam_id] = send_text_alert(cam_id, message)
        except Exception as e:
            results[cam_id] = False
    return results
