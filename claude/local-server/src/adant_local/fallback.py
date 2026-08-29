"""Tokenized loopback HTTP fallback for hosts that cannot render MCP Apps."""

from __future__ import annotations

import base64
import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from adant_local import api, artifacts, events

POLL_SECONDS = 0.5
TOKEN = secrets.token_urlsafe(24)
_lock = threading.Lock()
_server: ThreadingHTTPServer | None = None
_url: str | None = None
_panel: bytes = b""


class Handler(BaseHTTPRequestHandler):
    server_version = "AdAntProgress/2"

    def log_message(self, *_args) -> None:
        pass

    def _headers(self, status: int, content_type: str, length: int | None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; frame-src data: blob:",
        )
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self._headers(status, content_type, len(body))
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        parsed = urlsplit(self.path)
        prefix = f"/{TOKEN}/"
        if not parsed.path.startswith(prefix):
            self._send(404, "text/plain", b"not found")
            return
        route = parsed.path[len(prefix) :]
        if route in ("", "index.html"):
            self._send(200, "text/html; charset=utf-8", _panel)
        elif route == "healthz":
            self._send(200, "application/json", b'{"ok":true}')
        elif route == "events":
            self._stream_events()
        elif route == "artifact":
            self._serve_artifact(parsed.query)
        else:
            self._send(404, "text/plain", b"not found")

    def _serve_artifact(self, query: str) -> None:
        path = (parse_qs(query).get("path") or [""])[0]
        try:
            payload = artifacts.read(path)
        except api.ApiError as exc:
            self._send(403, "text/plain", exc.message.encode())
            return
        if payload["encoding"] == "text":
            body = payload["data"].encode()
        else:
            body = base64.b64decode(payload["data"])
        self._send(200, payload["mimeType"], body)

    def _stream_events(self) -> None:
        self._headers(200, "text/event-stream", None)
        current_path: Path | None = None
        offset = 0
        try:
            while True:
                path = events.active_progress_dir() / "events.jsonl"
                if path != current_path:
                    current_path = path
                    snapshot = json.dumps(
                        {"snapshot": events.snapshot()}, ensure_ascii=False
                    )
                    self.wfile.write(f"data: {snapshot}\n\n".encode())
                    offset = path.stat().st_size if path.exists() else 0
                if path.exists():
                    with path.open("r", encoding="utf-8", errors="replace") as handle:
                        handle.seek(offset)
                        for line in handle:
                            if not line.endswith("\n"):
                                break
                            offset += len(line.encode("utf-8"))
                            if line.strip():
                                self.wfile.write(f"data: {line.strip()}\n\n".encode())
                        self.wfile.flush()
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                time.sleep(POLL_SECONDS)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def ensure_server(panel_path: Path) -> str:
    global _panel, _server, _url
    with _lock:
        if _url is not None:
            return _url
        _panel = panel_path.read_bytes()
        _server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        _server.daemon_threads = True
        port = int(_server.server_address[1])
        _url = f"http://127.0.0.1:{port}/{TOKEN}/"
        threading.Thread(target=_server.serve_forever, daemon=True).start()
        return _url


def status() -> dict:
    return {"running": _url is not None, "url": _url}


def register_fallback_tool(mcp, panel_path: Path) -> None:
    @mcp.tool
    def research_progress_fallback() -> dict:
        """Return a tokenized 127.0.0.1 progress URL for hosts that cannot
        render the inline MCP App. The URL lives only for this server process."""
        return {"url": ensure_server(panel_path), "loopbackOnly": True}
