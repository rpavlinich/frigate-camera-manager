# frigate-camera-manager

## Overview
Python-based OpenClaw skill for managing Frigate NVR cameras. Supports listing cameras, monitoring connectivity, fetching snapshots, generating review GIFs, summarizing events, analyzing logs with suggested fixes, and posting media/alerts to Discord via webhooks.

**All state-changing actions require explicit user approval before execution.**

---

## API Reference Policy

1. Read the `FRIGATE_API_BASE` environment variable using `os.environ['FRIGATE_API_BASE']`
2. Before executing an unfamiliar Frigate API call, fetch `{FRIGATE_API_BASE}/api/docs` to confirm the correct endpoint. Skip this step for endpoints already confirmed in this session.
3. Only then construct and execute the API call

This ensures all API calls are aligned with the exact Frigate version in use, rather than relying on potentially outdated assumptions.

---

## File Structure

```
frigate_camera_manager/
  __init__.py         — package metadata
  client.py           — FrigateApiClient: low-level API wrapper (auth, HTTP)
  models.py           — dataclasses: Camera, CameraStatus, FrigateEvent, ReviewSummary, LogAnalysis, MediaEntry
  cache.py            — MediaCache: thread-safe in-memory store (default TTL = 1 day)
  operations.py       — high-level logic: list, snapshot, GIF, review summary, log analysis
  discord_webhook.py  — Discord webhook integration (per-camera or default webhook URL)
  handlers.py         — OpenClaw intent handlers mapping commands → operations
  main.py             — CLI entry point for local testing
  ornaments.py        — deprecated, kept for compat
tests/
  test_client.py
  test_operations.py
requirements.txt
example.env
SKILL.md
README.md
```

## Development Guidelines
- Always read a file's full contents before attempting any edits
- Never assume file contents based on this document — always verify first

---

## Core Capabilities

| Intent | Command (CLI) | Handler method |
|--------|--------------|----------------|
| List cameras | `list-cameras` | `handle_list_cameras()` |
| Connectivity status | `connectivity` | `handle_connectivity()` |
| Ping Frigate | `ping` | `handle_ping()` |
| Fetch snapshot | `snapshot {camera}` | `handle_snapshot(camera_id)` |
| Review summary | `review --camera {id} --hours 24` | `handle_review_summary()` |
| Create review GIF | `gif --camera {id} --hours 1` | `handle_create_gif()` |
| Analyze logs | `logs --process frigate` | `handle_logs()` |
| Register Discord webhook | `register-webhook {camera} {url}` | `handle_register_webhook()` |

---

## API Endpoints Used

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/` | Health check |
| GET | `/api/version` | Version / ping |
| GET | `/api/stats` | System stats + per-camera FPS |
| GET | `/api/config` | Full running config (includes camera list) |
| GET | `/api/logs/{service}` | Raw logs (e.g. `frigate`, `go2rtc`) |
| GET | `/api/events` | Event list with filters |
| GET | `/api/events/{event_id}/snapshot.jpg` | Event snapshot (JPEG) |
| GET | `/api/events/{event_id}/thumbnail.{extension}` | Event thumbnail |
| GET | `/api/events/{event_id}/clip.mp4` | Event clip (MP4) |
| GET | `/api/review` | Review-level summaries |
| GET | `/{camera_name}` | MJPEG live feed |
| GET | `/{camera_name}/latest.{extension}` | Latest frame snapshot |
| GET | `/{camera_name}/recordings` | Recordings list |
| GET | `/{camera_name}/recordings/summary` | Recordings summary |

---

## Security & Credentials

Credentials are read exclusively from environment variables. Never logged or echoed in chat.

| Env var | Purpose |
|---------|---------|
| `FRIGATE_API_BASE` | Base URL, e.g. `http://frigate.home:5000` |
| `FRIGATE_API_TOKEN` | Bearer token (preferred) |
| `FRIGATE_API_USERNAME` | Basic auth username (fallback) |
| `FRIGATE_API_PASSWORD` | Basic auth password (fallback) |
| `DISCORD_DEFAULT_WEBHOOK_URL` | Default Discord webhook for alerts |

Copy `example.env` to `.env` and populate before running.

---

## Media Storage

- All media (snapshots, GIFs) is stored in `MediaCache` — a thread-safe in-memory dict.
- Default TTL: **86400 seconds (1 day)**. Entries are lazily evicted on access or via `purge_expired()`.
- No disk writes unless explicitly saved with `--output`.

---

## Discord Webhooks

- Set `DISCORD_DEFAULT_WEBHOOK_URL` for a catch-all webhook.
- Register per-camera webhooks at runtime:
  ```
  python -m frigate_camera_manager.main register-webhook front_yard https://discord.com/api/webhooks/...
  ```
- Snapshots, GIFs, review summaries, and log alerts can all be posted to Discord.
- Log alerts only post automatically when severity is `error` or `critical`.

---

## Approval Gate

The following actions are **read-only and safe to run without approval:**
- list-cameras, connectivity, ping, snapshot, review, logs (fetch + analyze only)

The following actions **require explicit user approval before executing:**
- Any action that modifies Frigate config or state
- Posting to Discord (`--discord` flag)
- register-webhook (stores a new webhook mapping)

---

## Running Locally

```bash
# Install dependencies
uv pip install -r requirements.txt

# Copy and fill in credentials
cp example.env .env
# edit .env with your values

# Run with dotenv
python -m dotenv -f .env run python -m frigate_camera_manager.main ping
python -m dotenv -f .env run python -m frigate_camera_manager.main list-cameras
python -m dotenv -f .env run python -m frigate_camera_manager.main snapshot front_yard --output snap.jpg

# Run tests
pytest tests/
```

---

## Non-Goals (current version)

- Does not modify Frigate configuration
- Does not control PTZ cameras
- Does not stream live video
- Does not retain media beyond 1 day in memory (no persistence layer yet)
