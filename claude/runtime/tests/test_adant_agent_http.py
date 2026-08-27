"""Token-direct transport tests for adant_agent (stdlib stub proxy)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME))

import adant_agent  # noqa: E402

TOKEN = "alt_" + "t" * 40


class StubProxy(BaseHTTPRequestHandler):
    deleted: list = []

    def log_message(self, *_a):
        pass

    def _authed(self) -> bool:
        return self.headers.get("authorization") == f"Bearer {TOKEN}"

    def do_POST(self):
        if not self._authed():
            self.send_response(401)
            self.end_headers()
            return
        length = int(self.headers.get("Content-Length", 0) or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/api/app/brain/api/sessions":
            assert body["agentKey"] == "adant-agent"
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps({"session": {"id": "s-1"}}).encode())
        elif self.path == "/api/app/brain/api/chat":
            assert body["sessionId"] == "s-1"
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for frame in (
                {"type": "tool_result", "text": "noise"},
                {"type": "message", "text": '{"keywords": '},
                {"type": "message", "text": '["neck pain relief"]}'},
                {"type": "done", "data": {"status": "succeeded"}},
            ):
                self.wfile.write(f"data: {json.dumps(frame)}\n\n".encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_DELETE(self):
        StubProxy.deleted.append(self.path)
        self.send_response(200)
        self.end_headers()


class HttpTransportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), StubProxy)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        self._saved = {k: os.environ.get(k) for k in ("PLUGIN_DATA", "ADANT_SERVER_URL")}
        os.environ["PLUGIN_DATA"] = self._tmp.name
        os.environ["ADANT_SERVER_URL"] = f"http://127.0.0.1:{self._server.server_address[1]}"
        StubProxy.deleted = []

    def tearDown(self):
        self._server.shutdown()
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def _store_token(self, token=TOKEN):
        Path(self._tmp.name, "local-token.json").write_text(json.dumps({"token": token}))

    def test_http_roundtrip_parses_json_and_cleans_up(self):
        self._store_token()
        result = adant_agent.ask_adant("give keywords")
        self.assertEqual(result, {"keywords": ["neck pain relief"]})
        self.assertEqual(StubProxy.deleted, ["/api/app/brain/api/sessions/s-1"])

    def test_rejected_token_raises_mint_guidance(self):
        self._store_token("alt_" + "x" * 40)
        with self.assertRaises(adant_agent.AdantAgentError) as caught:
            adant_agent.ask_adant("x")
        self.assertIn("adant_mint_local_token", str(caught.exception))

    def test_no_token_falls_back_to_cli(self):
        called = {}

        def fake_cli(prompt, json_output=True, title="", timeout=900):
            called["prompt"] = prompt
            return {"via": "cli"}

        original = adant_agent._original_cli_ask
        adant_agent._original_cli_ask = fake_cli
        try:
            result = adant_agent.ask_adant("hello")
        finally:
            adant_agent._original_cli_ask = original
        self.assertEqual(result, {"via": "cli"})
        self.assertEqual(called["prompt"], "hello")


if __name__ == "__main__":
    unittest.main()
