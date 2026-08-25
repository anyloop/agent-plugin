"""Sidecar event bus: append-only progress events for AdAnt research workflows.

Every long-running research phase reports progress by appending one JSON line
to ``$ADANT_SOCIAL_DATA_DIR/progress/events.jsonl``. The Sidecar dashboard
(and any other observer) tails that file; nothing in the workflow ever depends
on a reader being present. Emission must never break research:
every failure inside this module is swallowed.

Event shape (one JSON object per line):
    {"ts": "2026-08-25T14:02:11Z", "skill": "browse-instagram-reels",
     "phase": "platform-instagram", "status": "progress",
     "message": "query 3/5", "counts": {"videos": 47}, "thumb": null}

``status`` is one of: start | progress | need-user | done | error.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

VALID_STATUSES = ("start", "progress", "need-user", "done", "error")
_EVENTS_FILE = "events.jsonl"


def progress_dir() -> Path:
    """Resolve the progress directory without ever raising.

    Prefers ``$ADANT_SOCIAL_DATA_DIR/progress`` (the documented research
    runtime root). Falls back to a per-user temp location so emission still
    works when the workflow forgot to export the variable.
    """
    root = os.environ.get("ADANT_SOCIAL_DATA_DIR", "").strip()
    if root:
        base = Path(root).expanduser()
    else:
        base = Path(tempfile.gettempdir()) / "adant-sidecar"
    return base / "progress"


def events_path() -> Path:
    return progress_dir() / _EVENTS_FILE


def emit(
    phase: str,
    status: str,
    message: str = "",
    *,
    skill: str | None = None,
    counts: dict | None = None,
    thumb: str | None = None,
    extra: dict | None = None,
) -> bool:
    """Append one event line. Returns True on success, False otherwise.

    Never raises. A single ``os.write`` with O_APPEND keeps concurrent phase
    processes from interleaving partial lines.
    """
    try:
        if status not in VALID_STATUSES:
            status = "progress"
        event = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "phase": str(phase),
            "status": status,
            "message": str(message)[:500],
        }
        if skill:
            event["skill"] = str(skill)
        if counts:
            event["counts"] = {str(k): v for k, v in dict(counts).items()}
        if thumb:
            event["thumb"] = str(thumb)
        if extra:
            event.update({str(k): v for k, v in dict(extra).items()})
        line = json.dumps(event, ensure_ascii=False) + "\n"
        directory = progress_dir()
        directory.mkdir(parents=True, exist_ok=True)
        fd = os.open(
            directory / _EVENTS_FILE,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o644,
        )
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
        return True
    except Exception:  # noqa: BLE001 - emission must never break research
        return False


def _parse_counts(pairs: list[str]) -> dict:
    counts: dict = {}
    for pair in pairs:
        key, _, value = pair.partition("=")
        if not key:
            continue
        try:
            counts[key] = int(value)
        except ValueError:
            counts[key] = value
    return counts


def main(argv: list[str] | None = None) -> int:
    """CLI: ``sidecar_events.py PHASE STATUS [MESSAGE] [--skill S] [--count k=v]``."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("phase")
    parser.add_argument("status", choices=VALID_STATUSES)
    parser.add_argument("message", nargs="?", default="")
    parser.add_argument("--skill")
    parser.add_argument("--thumb")
    parser.add_argument(
        "--count",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="repeatable numeric counter, e.g. --count videos=47",
    )
    args = parser.parse_args(argv)
    ok = emit(
        args.phase,
        args.status,
        args.message,
        skill=args.skill,
        counts=_parse_counts(args.count) or None,
        thumb=args.thumb,
    )
    print(f"sidecar: {'ok' if ok else 'disabled'} ({events_path()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
