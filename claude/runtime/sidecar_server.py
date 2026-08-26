"""Sidecar progress server: serve the local dashboard and stream events.

A tiny stdlib-only HTTP server bound to 127.0.0.1 that serves the Sidecar
dashboard page and tails ``progress/events.jsonl`` over Server-Sent Events.
It is started (detached) by ``sidecar_bootstrap.ensure_sidecar`` and owns its
own shutdown: it exits when the event file goes quiet past the idle timeout,
or when its lock file is removed. It never binds a public interface.

    python3 sidecar_server.py [--port 0] [--idle-timeout 3600]

Writes ``progress/sidecar.json`` (`{"port": ..., "pid": ..., "url": ...}`)
once listening so the bootstrap and the agent can find the URL.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sidecar_mcp  # noqa: E402  (artifact read + workspace guard)
from sidecar_events import events_path, progress_dir  # noqa: E402

PAGE_PATH = Path(__file__).resolve().parent / "sidecar_page.html"
LOCK_NAME = "sidecar.json"
SSE_POLL_SECONDS = 0.5


def lock_path() -> Path:
    return progress_dir() / LOCK_NAME


class SidecarHandler(BaseHTTPRequestHandler):
    server_version = "AdAntSidecar/1"

    def log_message(self, *_args) -> None:  # quiet by default
        pass

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path in ("/", "/index.html"):
            try:
                body = PAGE_PATH.read_bytes()
            except OSError:
                self._send(500, "text/plain", b"sidecar page missing")
                return
            self._send(200, "text/html; charset=utf-8", body)
        elif self.path == "/healthz":
            self._send(200, "application/json", b'{"ok": true}')
        elif self.path == "/jobs":
            jobs = []
            jobs_dir = progress_dir() / "jobs"
            if jobs_dir.is_dir():
                for path in sorted(jobs_dir.glob("*.json")):
                    try:
                        jobs.append(json.loads(path.read_text()))
                    except (OSError, json.JSONDecodeError):
                        continue
            self._send(200, "application/json", json.dumps(jobs).encode())
        elif self.path.startswith("/artifact?"):
            self._serve_artifact()
        elif self.path == "/events":
            self._stream_events()
        else:
            self._send(404, "text/plain", b"not found")

    def _serve_artifact(self) -> None:
        from urllib.parse import parse_qs, urlsplit

        query = parse_qs(urlsplit(self.path).query)
        path_text = (query.get("path") or [""])[0]
        try:
            payload = sidecar_mcp.read_artifact(path_text)
        except (OSError, PermissionError) as error:
            self._send(403, "text/plain", f"cannot read artifact: {error}".encode())
            return
        if payload["encoding"] == "text":
            self._send(200, payload["mimeType"] + "; charset=utf-8", payload["data"].encode())
        else:
            import base64

            self._send(200, payload["mimeType"], base64.b64decode(payload["data"]))

    def _stream_events(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        path = events_path()
        offset = 0
        try:
            while not self.server.stopping:  # type: ignore[attr-defined]
                if path.exists():
                    with open(path, "r", encoding="utf-8", errors="replace") as handle:
                        handle.seek(offset)
                        for line in handle:
                            if not line.endswith("\n"):
                                break  # partial write; retry next poll
                            offset += len(line.encode("utf-8"))
                            payload = line.strip()
                            if payload:
                                self.wfile.write(f"data: {payload}\n\n".encode())
                        self.wfile.flush()
                self.wfile.write(b": keepalive\n\n")
                self.wfile.flush()
                time.sleep(SSE_POLL_SECONDS)
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


class SidecarServer(ThreadingHTTPServer):
    daemon_threads = True
    stopping = False


def _write_lock(port: int) -> None:
    progress_dir().mkdir(parents=True, exist_ok=True)
    lock_path().write_text(
        json.dumps(
            {
                "port": port,
                "pid": os.getpid(),
                "url": f"http://127.0.0.1:{port}/",
                "started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
            indent=2,
        )
    )


def _watchdog(server: SidecarServer, idle_timeout: float) -> None:
    """Exit when events go quiet past the timeout or the lock disappears."""
    path = events_path()
    while True:
        time.sleep(5)
        if not lock_path().exists():
            break
        try:
            quiet = time.time() - path.stat().st_mtime if path.exists() else idle_timeout + 1
        except OSError:
            quiet = 0
        if idle_timeout and quiet > idle_timeout:
            break
    server.stopping = True
    try:
        lock_path().unlink(missing_ok=True)
    except OSError:
        pass
    server.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=0, help="0 picks a free port")
    parser.add_argument(
        "--idle-timeout",
        type=float,
        default=3600.0,
        help="exit after this many seconds without new events (0 = never)",
    )
    args = parser.parse_args(argv)

    server = SidecarServer(("127.0.0.1", args.port), SidecarHandler)
    port = server.server_address[1]
    _write_lock(port)
    print(f"sidecar-server: listening on http://127.0.0.1:{port}/", flush=True)
    threading.Thread(target=_watchdog, args=(server, args.idle_timeout), daemon=True).start()
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            lock_path().unlink(missing_ok=True)
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
