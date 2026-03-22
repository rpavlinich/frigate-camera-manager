"""OpenClaw intent handlers — maps natural language intents to operations."""

from typing import Dict, List, Optional, Tuple

from .cache import default_cache
from .client import FrigateApiClient
from .discord_webhook import (
    register_webhook,
    send_gif,
    send_log_alert,
    send_review_summary,
    send_snapshot,
)
from .operations import (
    analyze_logs,
    check_connectivity,
    create_review_gif,
    fetch_snapshot,
    format_camera_list,
    format_log_analysis,
    format_review_summary,
    list_cameras,
    summarize_review,
)


class FrigateHandlers:
    """Wires natural language intents to Frigate operations.

    Each public method returns a (text_response, media_bytes_or_None) tuple.
    - text_response: markdown-formatted string for Discord/chat output
    - media_bytes: raw bytes (JPEG/GIF) to attach, or None
    """

    def __init__(self, client: FrigateApiClient):
        self.client = client

    # ── list cameras ─────────────────────────────────────────────────────
    def handle_list_cameras(self) -> Tuple[str, None]:
        cameras = list_cameras(self.client)
        statuses = check_connectivity(self.client)
        text = format_camera_list(cameras, statuses)
        return text, None

    # ── connectivity check ───────────────────────────────────────────────
    def handle_connectivity(self) -> Tuple[str, None]:
        statuses = check_connectivity(self.client)
        lines = ["**Camera Connectivity**"]
        for s in statuses:
            icon = "🟢" if s.online else "🔴"
            fps = f"{s.fps:.1f} fps" if s.fps is not None else "no signal"
            lines.append(f"{icon} **{s.id}** — {fps}")
        return "\n".join(lines), None

    # ── snapshot ─────────────────────────────────────────────────────────
    def handle_snapshot(
        self,
        camera_id: str,
        post_to_discord: bool = False,
    ) -> Tuple[str, Optional[bytes]]:
        image_bytes = fetch_snapshot(self.client, camera_id, cache=default_cache)

        if post_to_discord:
            try:
                send_snapshot(camera_id, image_bytes)
                discord_note = " _(posted to Discord ✅)_"
            except Exception as e:
                discord_note = f" _(Discord post failed: {e})_"
        else:
            discord_note = ""

        text = f"📸 Snapshot fetched for **{camera_id}**{discord_note}"
        return text, image_bytes

    # ── review summary ───────────────────────────────────────────────────
    def handle_review_summary(
        self,
        camera_id: Optional[str] = None,
        hours: float = 24.0,
        post_to_discord: bool = False,
    ) -> Tuple[str, None]:
        summary = summarize_review(self.client, camera_id=camera_id, hours=hours)
        text = format_review_summary(summary)

        if post_to_discord:
            try:
                send_review_summary(camera_id or "all", text)
                text += "\n_(posted to Discord ✅)_"
            except Exception as e:
                text += f"\n_(Discord post failed: {e})_"

        return text, None

    # ── review GIF ───────────────────────────────────────────────────────
    def handle_create_gif(
        self,
        camera_id: str,
        hours: float = 1.0,
        post_to_discord: bool = False,
    ) -> Tuple[str, Optional[bytes]]:
        summary = summarize_review(self.client, camera_id=camera_id, hours=hours)
        event_ids = [e.id for e in summary.events if e.has_snapshot][:20]

        if not event_ids:
            return f"No events with snapshots found for **{camera_id}** in the last {hours:.0f}h.", None

        try:
            gif_bytes = create_review_gif(self.client, camera_id, event_ids, cache=default_cache)
        except RuntimeError as e:
            return f"⚠️ GIF creation failed: {e}", None

        if post_to_discord:
            try:
                summary_text = format_review_summary(summary)
                send_gif(camera_id, gif_bytes, event_summary=summary_text)
                discord_note = " _(posted to Discord ✅)_"
            except Exception as e:
                discord_note = f" _(Discord post failed: {e})_"
        else:
            discord_note = ""

        text = f"🎞️ GIF created for **{camera_id}** ({len(event_ids)} frames){discord_note}"
        return text, gif_bytes

    # ── log analysis ─────────────────────────────────────────────────────
    def handle_logs(
        self,
        process: str = "frigate",
        post_to_discord: bool = False,
    ) -> Tuple[str, None]:
        analysis = analyze_logs(self.client, process=process)
        text = format_log_analysis(analysis)

        if post_to_discord and analysis.severity in ("error", "critical"):
            try:
                send_log_alert(text)
                text += "\n_(alert posted to Discord ✅)_"
            except Exception as e:
                text += f"\n_(Discord post failed: {e})_"

        return text, None

    # ── register webhook ─────────────────────────────────────────────────
    def handle_register_webhook(
        self,
        camera_id: str,
        webhook_url: str,
    ) -> Tuple[str, None]:
        register_webhook(camera_id, webhook_url)
        return f"✅ Webhook registered for **{camera_id}**.", None

    # ── version / ping ───────────────────────────────────────────────────
    def handle_ping(self) -> Tuple[str, None]:
        try:
            version = self.client.get_version()
            return f"✅ Frigate is reachable. Version: `{version}`", None
        except Exception as e:
            return f"❌ Cannot reach Frigate: {e}", None
