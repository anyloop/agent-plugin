"""Event bus (v1-compatible): append-only JSONL the panel renders live.

Same wire format and locations as plugin v1's sidecar_events, so the panel
and any in-flight workspaces migrate with zero cost.
"""

from __future__ import annotations

import json
import os
import tempfile
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path

VALID_STATUSES = ("start", "progress", "need-user", "done", "warning", "error")


def progress_dir() -> Path:
    root = os.environ.get("ADANT_SOCIAL_DATA_DIR", "").strip()
    base = (
        Path(root).expanduser()
        if root
        else Path(tempfile.gettempdir()) / "adant-sidecar"
    )
    return base / "progress"


def pointer_path() -> Path:
    return Path.home() / ".adant" / "sidecar" / "current.json"


def read_pointer() -> Path | None:
    try:
        data = json.loads(pointer_path().read_text())
        path = Path(data["progress_dir"])
        return path if path.is_dir() else None
    except Exception:  # noqa: BLE001
        return None


def active_progress_dir() -> Path:
    pointed = read_pointer()
    return pointed if pointed is not None else progress_dir()


def write_pointer() -> None:
    try:
        pointer = pointer_path()
        pointer.parent.mkdir(parents=True, exist_ok=True)
        pointer.write_text(
            json.dumps(
                {
                    "progress_dir": str(progress_dir()),
                    "updated": datetime.now(timezone.utc).strftime(
                        "%Y-%m-%dT%H:%M:%SZ"
                    ),
                }
            )
        )
    except Exception:  # noqa: BLE001
        pass


def emit(
    phase: str,
    status: str,
    message: str = "",
    *,
    skill: str | None = None,
    counts: dict | None = None,
    thumb: str | None = None,
    artifact: str | None = None,
    artifact_label: str | None = None,
    subject: str | None = None,
    summary: str | None = None,
    next_step: str | None = None,
    risk: str | None = None,
    eta_minutes: int | str | None = None,
    timeout_seconds: int | None = None,
    extra: dict | None = None,
) -> bool:
    """Append one event line; never raises."""
    try:
        if status not in VALID_STATUSES:
            status = "progress"
        event: dict = {
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
        if subject:
            event["subject"] = str(subject)[:120]
        if summary:
            event["summary"] = str(summary)[:500]
        if next_step:
            event["next"] = str(next_step)[:500]
        if risk:
            event["risk"] = str(risk)[:500]
        if eta_minutes is not None:
            event["eta_minutes"] = eta_minutes
        if timeout_seconds is not None:
            event["timeout_seconds"] = int(timeout_seconds)
        if extra:
            event.update(extra)
        if artifact:
            event["artifact"] = {
                "path": str(Path(artifact).expanduser()),
                "label": str(artifact_label or Path(artifact).name),
            }
        directory = progress_dir()
        directory.mkdir(parents=True, exist_ok=True)
        if status == "start":
            write_pointer()
        fd = os.open(
            directory / "events.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644
        )
        try:
            os.write(fd, (json.dumps(event, ensure_ascii=False) + "\n").encode())
        finally:
            os.close(fd)
        return True
    except Exception:  # noqa: BLE001
        return False


def snapshot(max_events: int = 1500) -> dict:
    progress = active_progress_dir()
    workflow = None
    try:
        workflow = json.loads((progress / "workflow.json").read_text())
    except (OSError, json.JSONDecodeError):
        pass
    events: list[dict] = []
    try:
        lines = (
            (progress / "events.jsonl")
            .read_text(encoding="utf-8", errors="replace")
            .splitlines()
        )
        for line in lines[-max_events:]:
            line = line.strip()
            if line:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        pass
    jobs: list[dict] = []
    jobs_dir = progress / "jobs"
    if jobs_dir.is_dir():
        for path in sorted(jobs_dir.glob("*.json")):
            try:
                jobs.append(json.loads(path.read_text()))
            except (OSError, json.JSONDecodeError):
                continue
    if isinstance(workflow, dict) and isinstance(workflow.get("started"), str):
        started = workflow["started"]
        events = [item for item in events if str(item.get("ts", "")) >= started]
        jobs = [item for item in jobs if str(item.get("started", "")) >= started]
    session_id = (
        str(workflow.get("id"))
        if isinstance(workflow, dict) and workflow.get("id")
        else sha256(str(progress).encode()).hexdigest()[:24]
    )
    return {
        "workspace": str(progress),
        "widgetSessionId": session_id,
        "workflow": workflow,
        "events": events,
        "jobs": jobs,
    }
