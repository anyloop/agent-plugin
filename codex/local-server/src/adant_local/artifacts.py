"""Workspace-scoped artifact reads shared by MCP and HTTP panel transports."""

from __future__ import annotations

import base64
from pathlib import Path

from adant_local import api, events

MAX_ARTIFACT_BYTES = 3 * 1024 * 1024
TEXT_MIMES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".json": "application/json",
    ".html": "text/html",
    ".csv": "text/csv",
    ".log": "text/plain",
}
BINARY_MIMES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".pdf": "application/pdf",
}


def read(path: str) -> dict:
    target = Path(path).expanduser().resolve()
    root = events.active_progress_dir().resolve().parent.parent
    if root not in target.parents and target != root:
        raise api.ApiError(
            "artifact-denied", f"path outside the research workspace: {target}"
        )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise api.ApiError("artifact-denied", str(exc)) from exc
    if size > MAX_ARTIFACT_BYTES:
        raise api.ApiError(
            "artifact-denied", f"file too large to preview ({size} bytes)"
        )
    suffix = target.suffix.lower()
    if suffix in TEXT_MIMES:
        return {
            "mimeType": TEXT_MIMES[suffix],
            "encoding": "text",
            "data": target.read_text(encoding="utf-8", errors="replace"),
            "name": target.name,
        }
    mime = BINARY_MIMES.get(suffix, "application/octet-stream")
    return {
        "mimeType": mime,
        "encoding": "base64",
        "data": base64.b64encode(target.read_bytes()).decode("ascii"),
        "name": target.name,
    }
