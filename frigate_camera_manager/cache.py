"""In-memory media cache with TTL-based expiry (default 1 day)."""

import threading
import time
from typing import Dict, Iterator, List, Optional

from .models import MediaEntry

TTL_SECONDS = 86400  # 1 day


class MediaCache:
    """Thread-safe in-memory cache for snapshots, GIFs, and clips.

    Entries expire after TTL_SECONDS (default 86400 = 1 day).
    Call purge_expired() periodically or rely on lazy eviction on get().
    """

    def __init__(self, ttl_seconds: int = TTL_SECONDS):
        self._ttl = ttl_seconds
        self._store: Dict[str, MediaEntry] = {}
        self._lock = threading.Lock()

    # ── Write ─────────────────────────────────────────────────────────────
    def put(self, entry: MediaEntry) -> None:
        with self._lock:
            self._store[entry.key] = entry

    def put_bytes(
        self,
        key: str,
        data: bytes,
        media_type: str,
        camera_id: Optional[str] = None,
        event_id: Optional[str] = None,
    ) -> MediaEntry:
        entry = MediaEntry(
            key=key,
            data=data,
            media_type=media_type,
            created_at=time.time(),
            camera_id=camera_id,
            event_id=event_id,
        )
        self.put(entry)
        return entry

    # ── Read ──────────────────────────────────────────────────────────────
    def get(self, key: str) -> Optional[MediaEntry]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            if entry.is_expired(self._ttl):
                del self._store[key]
                return None
            return entry

    def list_by_camera(self, camera_id: str) -> List[MediaEntry]:
        with self._lock:
            return [
                e for e in self._store.values()
                if e.camera_id == camera_id and not e.is_expired(self._ttl)
            ]

    # ── Eviction ──────────────────────────────────────────────────────────
    def purge_expired(self) -> int:
        """Remove all expired entries. Returns number removed."""
        with self._lock:
            expired = [k for k, v in self._store.items() if v.is_expired(self._ttl)]
            for k in expired:
                del self._store[k]
            return len(expired)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)

    def __iter__(self) -> Iterator[MediaEntry]:
        with self._lock:
            return iter(list(self._store.values()))


# Module-level singleton shared across the skill
default_cache = MediaCache(ttl_seconds=TTL_SECONDS)
