#!/usr/bin/env python3
"""Controlled Bark notification CLI for Sumi skills."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


CONFIG_PATH = Path("~/.sumi/cookie/bark_config.json").expanduser()
ALLOWED_LEVELS = {"active", "timeSensitive", "passive"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a controlled Bark notification")
    parser.add_argument("--title", required=True, help="Notification title")
    parser.add_argument("--body", required=True, help="Notification body")
    parser.add_argument("--level", choices=sorted(ALLOWED_LEVELS), default="")
    parser.add_argument("--source", default="", help="Optional source label for output audit")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without sending")
    args = parser.parse_args()

    endpoint = load_endpoint()
    if not endpoint and not args.dry_run:
        return fail("missing Bark endpoint: set SUMI_BARK_URL or ~/.sumi/cookie/bark_config.json")

    title = clean_text(args.title, "title")
    body = clean_text(args.body, "body")
    source = clean_text(args.source, "source", required=False)

    if args.dry_run:
        print_json({"ok": True, "sent": False, "level": args.level, "source": source})
        return 0

    url = bark_url(endpoint, title, body, args.level)
    try:
        req = Request(url, headers={"User-Agent": "Sumi-BarkNotifySkill/1.0"})
        with urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return fail(f"bark http {exc.code}: {detail}")
    except URLError as exc:
        return fail(f"bark request failed: {exc.reason}")
    except TimeoutError:
        return fail("bark request timed out")

    print_json({
        "ok": True,
        "sent": True,
        "level": args.level,
        "source": source,
        "response": parse_response(raw),
    })
    return 0


def load_endpoint() -> str:
    env = os.environ.get("SUMI_BARK_URL", "").strip()
    if env:
        return env
    if not CONFIG_PATH.exists():
        return ""
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(data.get("url", "")).strip()


def clean_text(value: str, name: str, required: bool = True) -> str:
    value = (value or "").strip()
    if required and not value:
        raise SystemExit(fail(f"{name} is required"))
    return value


def bark_url(endpoint: str, title: str, body: str, level: str) -> str:
    endpoint = endpoint.rstrip("/")
    path = "/".join(quote(part, safe="") for part in (title, body))
    query = urlencode({"level": level}) if level else ""
    return f"{endpoint}/{path}" + (f"?{query}" if query else "")


def parse_response(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def fail(message: str) -> int:
    print(json.dumps({"ok": False, "error": message}, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
