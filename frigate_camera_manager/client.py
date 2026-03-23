"""Frigate API client — handles auth and raw HTTP calls."""

import os
import requests
from typing import Any, Dict, List, Optional


class FrigateApiClient:
    """Low-level wrapper around the Frigate HTTP API."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.base = (base_url or os.environ.get("FRIGATE_API_BASE", "http://localhost:5000")).rstrip("/")
        self.token = token or os.environ.get("FRIGATE_API_TOKEN")
        self.username = username or os.environ.get("FRIGATE_API_USERNAME")
        self.password = password or os.environ.get("FRIGATE_API_PASSWORD")

    # ── Auth ─────────────────────────────────────────────────────────────
    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _auth(self):
        """Return a requests auth object for basic auth, or None."""
        if not self.token and self.username and self.password:
            return requests.auth.HTTPBasicAuth(self.username, self.password)
        return None

    # ── HTTP helpers ─────────────────────────────────────────────────────
    def _get(self, path: str, **kwargs) -> requests.Response:
        url = f"{self.base}{path}"
        headers = {**self._headers()}
        if 'headers' in kwargs:
            headers.update(kwargs.pop('headers'))
        resp = requests.get(url, headers=headers, auth=self._auth(), timeout=30, **kwargs)
        resp.raise_for_status()
        return resp

    def _get_json(self, path: str) -> Any:
        return self._get(path).json()

    def _get_bytes(self, path: str) -> bytes:
        return self._get(path, headers={**self._headers(), "Accept": "image/jpeg"}).content

    # ── Cameras ──────────────────────────────────────────────────────────
    def list_cameras(self) -> Dict[str, Any]:
        """GET /api/config — returns full config, extract cameras section."""
        config = self._get_json("/api/config")
        # Frigate config has a 'cameras' section containing camera definitions
        if isinstance(config, dict) and "cameras" in config:
            return config["cameras"]
        else:
            # Fallback: if config is already the cameras dict
            return config if isinstance(config, dict) else {}

    def get_camera_snapshot(self, camera_id: str) -> bytes:
        """GET /api/cameras/{id}/snapshot.jpg — returns JPEG bytes."""
        return self._get_bytes(f"/api/cameras/{camera_id}/snapshot.jpg")

    # ── Events ───────────────────────────────────────────────────────────
    def get_events(
        self,
        camera: Optional[str] = None,
        limit: int = 50,
        after: Optional[float] = None,
        before: Optional[float] = None,
    ) -> List[dict]:
        """GET /api/events with optional filters."""
        params: Dict[str, Any] = {"limit": limit}
        if camera:
            params["camera"] = camera
        if after is not None:
            params["after"] = after
        if before is not None:
            params["before"] = before
        return self._get("/api/events", params=params).json()

    def get_event_thumbnail(self, event_id: str) -> bytes:
        """GET /api/events/{id}/thumbnail — JPEG bytes."""
        return self._get_bytes(f"/api/events/{event_id}/thumbnail")

    def get_event_clip(self, event_id: str) -> bytes:
        """GET /api/events/{id}/clip — MP4 bytes."""
        resp = self._get(f"/api/events/{event_id}/clip", headers={**self._headers(), "Accept": "video/mp4"})
        return resp.content

    # ── Review ───────────────────────────────────────────────────────────
    def get_review(
        self,
        camera: Optional[str] = None,
        after: Optional[float] = None,
        before: Optional[float] = None,
        limit: int = 50,
    ) -> List[dict]:
        """GET /api/review — review-level summaries."""
        params: Dict[str, Any] = {"limit": limit}
        if camera:
            params["camera"] = camera
        if after is not None:
            params["after"] = after
        if before is not None:
            params["before"] = before
        return self._get("/api/review", params=params).json()

    # ── Logs ─────────────────────────────────────────────────────────────
    def get_logs(self, process: str = "frigate", limit: int = 200) -> str:
        """GET /api/logs/{process} — returns raw log text."""
        resp = self._get(f"/api/logs/{process}")
        try:
            return resp.json()
        except Exception:
            return resp.text

    # ── System / connectivity ────────────────────────────────────────────
    def get_version(self) -> str:
        """GET /api/version — quick connectivity check."""
        resp = self._get("/api/version")
        return resp.text

    def get_stats(self) -> Dict[str, Any]:
        """GET /api/stats — system stats incl. per-camera info."""
        return self._get_json("/api/stats")