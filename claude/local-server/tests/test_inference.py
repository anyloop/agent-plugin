"""Tests for the stdlib-only client used by isolated phase runtimes."""

from __future__ import annotations

import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from adant_local import inference

TOKEN = "alt_" + "t" * 40


class StubApi(BaseHTTPRequestHandler):
    deleted: list[str] = []
    uploaded = b""

    def log_message(self, *_args):
        pass

    def _authed(self) -> bool:
        return self.headers.get("authorization") == f"Bearer {TOKEN}"

    def _json(self, value: dict, status: int = 200) -> None:
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if not self._authed():
            self._json({}, 401)
            return
        length = int(self.headers.get("content-length", 0) or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/app/brain/api/sessions":
            assert body["agentKey"] == "adant-agent"
            self._json({"session": {"id": "s-1"}})
        elif self.path == "/api/app/brain/api/chat":
            assert body["sessionId"] == "s-1"
            self.send_response(200)
            self.send_header("content-type", "text/event-stream")
            self.end_headers()
            for frame in (
                {"type": "message", "text": '{"keywords": '},
                {"type": "message", "text": '["neck relief"]}'},
                {"type": "done", "data": {"status": "succeeded"}},
            ):
                self.wfile.write(f"data: {json.dumps(frame)}\n\n".encode())
        elif self.path == "/v1/files/create-upload":
            assert body["size_bytes"] > 0
            port = self.server.server_address[1]
            self._json({"id": "u-1", "upload_url": f"http://127.0.0.1:{port}/upload/u-1"})
        elif self.path == "/v1/files/complete":
            assert body["id"] == "u-1" and StubApi.uploaded
            self._json({"id": "u-1"})
        elif self.path == "/v1/media.video.analyze":
            assert body["responseFormat"] == "json"
            assert "Return ONLY JSON conforming" in body["prompt"]
            self._json({"text": '{"hook":"demo"}'})
        else:
            self._json({}, 404)

    def do_GET(self):
        if self.path == "/v1/files/u-1/content" and self._authed():
            self._json({"download_url": "https://files.example/video.mp4"})
        else:
            self._json({}, 404)

    def do_PUT(self):
        if self.path != "/upload/u-1":
            self._json({}, 404)
            return
        StubApi.uploaded = self.rfile.read(
            int(self.headers.get("content-length", 0) or 0)
        )
        self.send_response(200)
        self.end_headers()

    def do_DELETE(self):
        StubApi.deleted.append(self.path)
        self.send_response(204)
        self.end_headers()


@pytest.fixture
def stub_api(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubApi)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv(
        "ADANT_SERVER_URL", f"http://127.0.0.1:{server.server_address[1]}"
    )
    StubApi.deleted = []
    StubApi.uploaded = b""
    yield server
    server.shutdown()


@pytest.fixture
def plugin_data(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("PLUGIN_DATA", tmp)
        yield Path(tmp)


def store_token(plugin_data: Path, token: str = TOKEN) -> None:
    (plugin_data / "local-token.json").write_text(json.dumps({"token": token}))


def test_agent_roundtrip_parses_json_and_cleans_up(stub_api, plugin_data):
    store_token(plugin_data)
    assert inference.ask_adant("give keywords") == {"keywords": ["neck relief"]}
    assert StubApi.deleted == ["/api/app/brain/api/sessions/s-1"]


def test_missing_token_has_no_cli_fallback(stub_api, plugin_data):
    with pytest.raises(inference.AdantInferenceError, match="auth_bootstrap"):
        inference.ask_adant("x")


def test_rejected_token_requests_a_fresh_mint(stub_api, plugin_data):
    store_token(plugin_data, "alt_" + "x" * 40)
    with pytest.raises(inference.AdantInferenceError, match="mint_local_token"):
        inference.ask_adant("x")


def test_video_analysis_uploads_and_uses_scoped_api(stub_api, plugin_data):
    store_token(plugin_data)
    video = plugin_data / "clip.mp4"
    video.write_bytes(b"video-bytes")
    result = inference.analyze_video_file(
        video,
        "analyze",
        schema={"type": "object", "properties": {"hook": {"type": "string"}}},
    )
    assert json.loads(result) == {"hook": "demo"}
    assert StubApi.uploaded == b"video-bytes"
