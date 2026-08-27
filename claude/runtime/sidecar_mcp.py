"""Local MCP server exposing the AdAnt research progress panel as an MCP App.

Runs on the user's machine (stdio, newline-delimited JSON-RPC), so unlike the
remote AdAnt MCP it can read the local Sidecar event bus. It registers one
``ui://`` HTML resource (the dashboard, MCP Apps profile) and two tools:

- ``research_progress_open``  — model-visible; carries ``_meta.ui.resourceUri``
  so the host renders the panel inline. Returns the current snapshot.
- ``research_progress_snapshot`` — polled by the panel over the MCP Apps
  postMessage bridge to refresh itself.

The active workspace is resolved through the pointer file that
``sidecar_events.write_pointer`` maintains (the host starts this server with a
different environment than the research shell commands).

Stdlib only. Protocol: MCP 2025-06-18 core + MCP Apps extension (SEP-1865).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sidecar_events  # noqa: E402

UI_URI = "ui://adant/research-progress.html"
UI_MIME = "text/html;profile=mcp-app"
PAGE_PATH = Path(__file__).resolve().parent / "sidecar_page.html"
PROTOCOL_VERSION = "2025-06-18"
MAX_EVENTS = 1500
MAX_ARTIFACT_BYTES = 3 * 1024 * 1024
TEXT_MIMES = {
    ".txt": "text/plain", ".md": "text/markdown", ".json": "application/json",
    ".html": "text/html", ".csv": "text/csv", ".log": "text/plain",
}
BINARY_MIMES = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".webp": "image/webp", ".gif": "image/gif", ".pdf": "application/pdf",
}

SERVER_INFO = {"name": "adant-sidecar", "version": "0.7.0"}
UI_RESOURCE = {
    "uri": UI_URI,
    "name": "AdAnt research progress",
    "description": "Live research progress panel (phases, counts, event feed).",
    "mimeType": UI_MIME,
    "_meta": {
        "ui": {
            "prefersBorder": True,
            "csp": {
                "resourceDomains": [
                    "https://fonts.googleapis.com",
                    "https://fonts.gstatic.com",
                ]
            },
        }
    },
}
TOOLS = [
    {
        "name": "research_progress_open",
        "description": (
            "Open the live AdAnt progress panel in the conversation. Call this "
            "PROACTIVELY, once, at the start of any AdAnt workflow — init, "
            "setup checks, or research — without waiting for the user to ask; "
            "the panel then updates itself. Shows preflight checks, phase "
            "timeline, counts, results, and the live event feed."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "_meta": {"ui": {"resourceUri": UI_URI, "visibility": ["model", "app"]}},
    },
    {
        "name": "research_artifact_read",
        "description": (
            "Read a file produced by the research run (thumbnail, report, data "
            "file) for preview in the progress panel. Only paths inside the "
            "active research workspace are allowed."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "_meta": {"ui": {"visibility": ["app"]}},
    },
    {
        "name": "research_progress_snapshot",
        "description": (
            "Return the current research progress snapshot (recent events and "
            "background jobs) from the local event bus. Used by the progress "
            "panel to refresh; also safe for the model to inspect."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        "_meta": {"ui": {"visibility": ["model", "app"]}},
    },
]


def _active_progress_dir() -> Path:
    pointed = sidecar_events.read_pointer()
    return pointed if pointed is not None else sidecar_events.progress_dir()


def snapshot() -> dict:
    progress = _active_progress_dir()
    workflow = None
    try:
        workflow = json.loads((progress / "workflow.json").read_text())
    except (OSError, json.JSONDecodeError):
        pass
    events: list[dict] = []
    events_file = progress / "events.jsonl"
    try:
        lines = events_file.read_text(encoding="utf-8", errors="replace").splitlines()
        for line in lines[-MAX_EVENTS:]:
            line = line.strip()
            if not line:
                continue
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
    return {"workspace": str(progress), "workflow": workflow, "events": events, "jobs": jobs}


def allowed_root() -> Path:
    """Files may be read from the workspace that owns the progress dir.

    progress_dir = $ADANT_SOCIAL_DATA_DIR/progress and the data dir sits inside
    the user's chosen workspace root, so the workspace root is two levels up.
    """
    return _active_progress_dir().resolve().parent.parent


def read_artifact(path_text: str) -> dict:
    path = Path(path_text).expanduser().resolve()
    root = allowed_root()
    if root not in path.parents and path != root:
        raise PermissionError(f"path outside the research workspace: {path}")
    size = path.stat().st_size
    if size > MAX_ARTIFACT_BYTES:
        raise PermissionError(f"file too large to preview ({size} bytes)")
    suffix = path.suffix.lower()
    if suffix in TEXT_MIMES:
        return {
            "mimeType": TEXT_MIMES[suffix],
            "encoding": "text",
            "data": path.read_text(encoding="utf-8", errors="replace"),
            "name": path.name,
        }
    import base64

    mime = BINARY_MIMES.get(suffix, "application/octet-stream")
    return {
        "mimeType": mime,
        "encoding": "base64",
        "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        "name": path.name,
    }


def _snapshot_result() -> dict:
    data = snapshot()
    running = [j["phase"] for j in data["jobs"] if j.get("status") == "running"]
    failed = [j["phase"] for j in data["jobs"] if j.get("status") == "failed"]
    summary = (
        f"{len(data['events'])} events; running: {', '.join(running) or 'none'}; "
        f"failed: {', '.join(failed) or 'none'}"
    )
    return {
        "content": [{"type": "text", "text": summary}],
        "structuredContent": data,
    }


def handle(message: dict) -> dict | None:
    method = message.get("method", "")
    params = message.get("params") or {}
    if method == "initialize":
        return {
            "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
            "capabilities": {"resources": {}, "tools": {}},
            "serverInfo": SERVER_INFO,
        }
    if method == "resources/list":
        return {"resources": [UI_RESOURCE]}
    if method == "resources/read":
        if params.get("uri") != UI_URI:
            raise LookupError(f"unknown resource: {params.get('uri')}")
        return {
            "contents": [
                {"uri": UI_URI, "mimeType": UI_MIME, "text": PAGE_PATH.read_text(encoding="utf-8")}
            ]
        }
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        name = params.get("name")
        if name in ("research_progress_open", "research_progress_snapshot"):
            return _snapshot_result()
        if name == "research_artifact_read":
            arguments = params.get("arguments") or {}
            try:
                payload = read_artifact(str(arguments.get("path", "")))
            except (OSError, PermissionError) as error:
                return {
                    "content": [{"type": "text", "text": f"cannot read artifact: {error}"}],
                    "isError": True,
                }
            return {
                "content": [{"type": "text", "text": f"artifact {payload['name']} ({payload['mimeType']})"}],
                "structuredContent": payload,
            }
        raise LookupError(f"unknown tool: {name}")
    if method == "ping":
        return {}
    if method.startswith("notifications/"):
        return None  # notifications get no response
    raise LookupError(f"method not found: {method}")


def main() -> int:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if "id" not in message:  # notification
            try:
                handle(message)
            except Exception:  # noqa: BLE001
                pass
            continue
        response: dict = {"jsonrpc": "2.0", "id": message["id"]}
        try:
            result = handle(message)
            response["result"] = result if result is not None else {}
        except LookupError as error:
            response["error"] = {"code": -32601, "message": str(error)}
        except Exception as error:  # noqa: BLE001
            response["error"] = {"code": -32603, "message": f"{error.__class__.__name__}: {error}"}
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
