"""api client tests against a stub brain-proxy HTTP server."""

from __future__ import annotations

import asyncio
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastmcp import Client

from adant_local import api
from adant_local.server import mcp

GOOD = "alt_" + "g" * 40
MEDIA_ONLY = "alt_" + "m" * 40


class StubProxy(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        pass

    def _token_ok(self) -> bool:
        return self.headers.get("Authorization") == f"Bearer {GOOD}"

    def do_GET(self):
        if self.path == "/api/app/brain/api/health":
            code = 200 if self._token_ok() else 401
            self.send_response(code)
            self.end_headers()
            self.wfile.write(b"ok" if code == 200 else b"unauthorized")
        elif self.path == "/v1/media.models":
            code = 200 if self.headers.get("Authorization") == f"Bearer {MEDIA_ONLY}" else 401
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"image":[],"video":[],"audio":[]}' if code == 200 else b"{}")
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        body = json.loads(
            self.rfile.read(int(self.headers.get("Content-Length", 0)) or 0) or b"{}"
        )
        if not self._token_ok():
            self.send_response(401)
            self.end_headers()
            return
        if self.path == "/api/app/brain/api/sessions":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(
                json.dumps(
                    {"session": {"id": "sess-42", "agent": body.get("agentKey")}}
                ).encode()
            )
        elif self.path == "/api/app/brain/api/chat":
            assert body["sessionId"] == "sess-42"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            frames = [
                {"type": "thinking_start"},
                {"type": "message", "text": "Hello "},
                {"type": "message", "text": "world"},
                {"type": "done", "data": {"status": "succeeded"}},
            ]
            for frame in frames:
                self.wfile.write(f"data: {json.dumps(frame)}\n\n".encode())
        else:
            self.send_response(404)
            self.end_headers()


@pytest.fixture
def stub_server(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), StubProxy)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv(
        "ADANT_SERVER_URL", f"http://127.0.0.1:{server.server_address[1]}"
    )
    yield server
    server.shutdown()


@pytest.fixture
def plugin_data(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("PLUGIN_DATA", tmp)
        monkeypatch.setenv("ADANT_SOCIAL_DATA_DIR", str(Path(tmp) / "ws"))
        monkeypatch.setenv("HOME", tmp)
        yield Path(tmp)


def store_token(plugin_data: Path, token: str):
    (plugin_data / "local-token.json").write_text(json.dumps({"token": token}))


def test_agent_infer_roundtrip(stub_server, plugin_data):
    store_token(plugin_data, GOOD)
    assert api.agent_infer("say hello") == "Hello world"


def test_missing_token_is_structured(stub_server, plugin_data):
    with pytest.raises(api.ApiError) as caught:
        api.agent_infer("x")
    assert caught.value.code == "not-authenticated"


def test_rejected_token_is_structured(stub_server, plugin_data):
    store_token(plugin_data, MEDIA_ONLY)
    with pytest.raises(api.ApiError) as caught:
        api.create_session()
    assert caught.value.code == "not-authenticated"


def test_auth_bootstrap_verifies_end_to_end(stub_server, plugin_data):
    async def scenario():
        async with Client(mcp) as client:
            good = (
                await client.call_tool("auth_bootstrap", {"minted_token": GOOD})
            ).data
            assert good["ok"] is True and good["verified"] is True
            media = (
                await client.call_tool("auth_bootstrap", {"minted_token": MEDIA_ONLY})
            ).data
            assert media["ok"] is True and media["verified"] is True
            assert (plugin_data / "local-token.json").exists()

    asyncio.run(scenario())
