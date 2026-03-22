"""Lightweight conversation compaction utility.

Monitors conversation length and writes bullet-point summaries to
memory/CONVERSATION_SUMMARIES.md when the threshold is exceeded.

Config (env vars or pass directly):
  COMPACT_ENABLED        true|false  (default: true)
  COMPACT_THRESHOLD      int chars   (default: 5000)
  COMPACT_MEMORY_PATH    file path   (default: memory/CONVERSATION_SUMMARIES.md)
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
from typing import List, Optional

# ── Config ────────────────────────────────────────────────────────────────────
COMPACT_ENABLED: bool = os.environ.get("COMPACT_ENABLED", "true").lower() != "false"
COMPACT_THRESHOLD: int = int(os.environ.get("COMPACT_THRESHOLD", "5000"))
COMPACT_MEMORY_PATH: Path = Path(
    os.environ.get("COMPACT_MEMORY_PATH", "/root/.openclaw/workspace/memory/CONVERSATION_SUMMARIES.md")
)


# ── Summarizer ────────────────────────────────────────────────────────────────
def summarize_to_bullets(text: str, max_bullets: int = 10) -> List[str]:
    """Extract meaningful bullet points from a conversation or memory text."""
    bullets: List[str] = []
    lines = text.splitlines()

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Capture existing bullet points
        if stripped.startswith("- ") and len(stripped) > 4:
            bullets.append(stripped[2:].strip())
        # Capture bold key-value style lines
        elif ":" in stripped and not stripped.startswith("```"):
            bullets.append(stripped)

        if len(bullets) >= max_bullets:
            break

    if not bullets:
        # Fallback: use first meaningful sentence up to 300 chars
        flat = " ".join(l.strip() for l in lines if l.strip())
        bullets.append(flat[:300] + ("..." if len(flat) > 300 else ""))

    return bullets


def format_summary(bullets: List[str], source_label: str = "session") -> str:
    timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    header = f"## Compact — {source_label} — {timestamp}"
    body = "\n".join(f"- {b}" for b in bullets)
    return f"{header}\n{body}\n"


# ── Storage ───────────────────────────────────────────────────────────────────
def store_summary(summary: str, path: Optional[Path] = None) -> None:
    target = path or COMPACT_MEMORY_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write("\n" + summary)


# ── Main entry point ──────────────────────────────────────────────────────────
def maybe_compact(
    text: str,
    source_label: str = "session",
    threshold: Optional[int] = None,
    enabled: Optional[bool] = None,
    memory_path: Optional[Path] = None,
) -> Optional[str]:
    """Run compaction if enabled and text exceeds threshold.

    Returns the summary string if compaction ran, None otherwise.
    """
    _enabled = enabled if enabled is not None else COMPACT_ENABLED
    _threshold = threshold if threshold is not None else COMPACT_THRESHOLD

    if not _enabled:
        return None
    if len(text) < _threshold:
        return None

    bullets = summarize_to_bullets(text)
    summary = format_summary(bullets, source_label=source_label)
    store_summary(summary, path=memory_path)
    return summary
