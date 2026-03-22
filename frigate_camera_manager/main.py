"""Entry point for frigate-camera-manager skill.

Can be run directly as a CLI for testing, or imported by OpenClaw handlers.

Usage:
    python -m frigate_camera_manager.main list-cameras
    python -m frigate_camera_manager.main snapshot front_yard
    python -m frigate_camera_manager.main review --hours 24 --camera front_yard
    python -m frigate_camera_manager.main gif --camera front_yard --hours 1
    python -m frigate_camera_manager.main logs
    python -m frigate_camera_manager.main ping
    python -m frigate_camera_manager.main register-webhook front_yard https://discord.com/api/webhooks/...
"""

import argparse
import os
import sys

from .client import FrigateApiClient
from .handlers import FrigateHandlers


def build_client() -> FrigateApiClient:
    return FrigateApiClient(
        base_url=os.environ.get("FRIGATE_API_BASE"),
        token=os.environ.get("FRIGATE_API_TOKEN"),
        username=os.environ.get("FRIGATE_API_USERNAME"),
        password=os.environ.get("FRIGATE_API_PASSWORD"),
    )


def main():
    parser = argparse.ArgumentParser(
        prog="frigate-camera-manager",
        description="OpenClaw skill — Frigate camera management",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # list-cameras
    sub.add_parser("list-cameras", help="List all cameras with connectivity status")

    # connectivity
    sub.add_parser("connectivity", help="Check per-camera connectivity status")

    # ping
    sub.add_parser("ping", help="Ping Frigate API (connectivity check)")

    # snapshot
    snap = sub.add_parser("snapshot", help="Fetch latest snapshot for a camera")
    snap.add_argument("camera", help="Camera ID")
    snap.add_argument("--discord", action="store_true", help="Post to Discord webhook")
    snap.add_argument("--output", "-o", help="Save snapshot to file (e.g. snap.jpg)")

    # review
    review = sub.add_parser("review", help="Summarize review events")
    review.add_argument("--camera", default=None, help="Camera ID (omit for all cameras)")
    review.add_argument("--hours", type=float, default=24.0, help="Time window in hours (default 24)")
    review.add_argument("--discord", action="store_true", help="Post summary to Discord")

    # gif
    gif = sub.add_parser("gif", help="Create a review GIF from recent events")
    gif.add_argument("--camera", required=True, help="Camera ID")
    gif.add_argument("--hours", type=float, default=1.0, help="Time window in hours (default 1)")
    gif.add_argument("--discord", action="store_true", help="Post GIF to Discord")
    gif.add_argument("--output", "-o", help="Save GIF to file (e.g. review.gif)")

    # logs
    logs = sub.add_parser("logs", help="Fetch and analyze Frigate logs")
    logs.add_argument("--process", default="frigate", help="Process name (default: frigate)")
    logs.add_argument("--discord", action="store_true", help="Post error alerts to Discord")

    # register-webhook
    reg = sub.add_parser("register-webhook", help="Register a Discord webhook for a camera")
    reg.add_argument("camera", help="Camera ID")
    reg.add_argument("url", help="Discord webhook URL")

    args = parser.parse_args()
    client = build_client()
    h = FrigateHandlers(client)

    if args.command == "list-cameras":
        text, _ = h.handle_list_cameras()
        print(text)

    elif args.command == "connectivity":
        text, _ = h.handle_connectivity()
        print(text)

    elif args.command == "ping":
        text, _ = h.handle_ping()
        print(text)

    elif args.command == "snapshot":
        text, media = h.handle_snapshot(args.camera, post_to_discord=args.discord)
        print(text)
        if media and args.output:
            with open(args.output, "wb") as f:
                f.write(media)
            print(f"Saved to {args.output}")

    elif args.command == "review":
        text, _ = h.handle_review_summary(
            camera_id=args.camera,
            hours=args.hours,
            post_to_discord=args.discord,
        )
        print(text)

    elif args.command == "gif":
        text, media = h.handle_create_gif(
            camera_id=args.camera,
            hours=args.hours,
            post_to_discord=args.discord,
        )
        print(text)
        if media and args.output:
            with open(args.output, "wb") as f:
                f.write(media)
            print(f"Saved to {args.output}")

    elif args.command == "logs":
        text, _ = h.handle_logs(process=args.process, post_to_discord=args.discord)
        print(text)

    elif args.command == "register-webhook":
        text, _ = h.handle_register_webhook(args.camera, args.url)
        print(text)


if __name__ == "__main__":
    main()
