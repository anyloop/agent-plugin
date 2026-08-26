"""Tests for the local MCP App server (stdio JSON-RPC)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME))

import sidecar_events  # noqa: E402


class McpServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._home = tempfile.TemporaryDirectory()
        self._saved = {k: os.environ.get(k) for k in ("ADANT_SOCIAL_DATA_DIR", "HOME")}
        os.environ["ADANT_SOCIAL_DATA_DIR"] = self._tmp.name
        os.environ["HOME"] = self._home.name  # isolate the pointer file

    def tearDown(self) -> None:
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()
        self._home.cleanup()

    def rpc(self, *messages: dict) -> list[dict]:
        payload = "".join(json.dumps(m) + "\n" for m in messages)
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "sidecar_mcp.py")],
            input=payload,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=30,
        )
        return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]

    def test_initialize_resources_and_tools(self) -> None:
        responses = self.rpc(
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "resources/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 4, "method": "resources/read",
             "params": {"uri": "ui://adant/research-progress.html"}},
        )
        by_id = {r["id"]: r for r in responses}
        self.assertEqual(by_id[1]["result"]["serverInfo"]["name"], "adant-sidecar")
        resource = by_id[2]["result"]["resources"][0]
        self.assertEqual(resource["uri"], "ui://adant/research-progress.html")
        self.assertEqual(resource["mimeType"], "text/html;profile=mcp-app")
        tools = {t["name"]: t for t in by_id[3]["result"]["tools"]}
        self.assertEqual(
            tools["research_progress_open"]["_meta"]["ui"]["resourceUri"],
            "ui://adant/research-progress.html",
        )
        page = by_id[4]["result"]["contents"][0]
        self.assertIn("AdAnt Research", page["text"])
        self.assertIn("ui/initialize", page["text"])  # bridge transport present

    def test_snapshot_follows_the_pointer(self) -> None:
        sidecar_events.emit("platform-tiktok", "start", "browse begins")
        sidecar_events.emit("platform-tiktok", "progress", "query 1/4", counts={"videos": 7})
        # Point a different environment at nothing: the pointer must lead back.
        env_snapshot = os.environ.copy()
        env_snapshot.pop("ADANT_SOCIAL_DATA_DIR")
        payload = "".join(json.dumps(m) + "\n" for m in (
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "research_progress_snapshot", "arguments": {}}},
        ))
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "sidecar_mcp.py")],
            input=payload, capture_output=True, text=True, env=env_snapshot, timeout=30,
        )
        response = json.loads(result.stdout.splitlines()[0])
        snap = response["result"]["structuredContent"]
        self.assertEqual(len(snap["events"]), 2)
        self.assertEqual(snap["events"][1]["counts"], {"videos": 7})
        self.assertIn("2 events", response["result"]["content"][0]["text"])

    def test_artifact_read_inside_workspace(self) -> None:
        target = Path(self._tmp.name) / "progress" / "deck.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"pages": 20}')
        sidecar_events.emit("report", "done", "deck built", artifact=str(target))
        responses = self.rpc(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": "research_artifact_read", "arguments": {"path": str(target)}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
             "params": {"name": "research_artifact_read", "arguments": {"path": "/etc/hosts"}}},
        )
        ok = responses[0]["result"]["structuredContent"]
        self.assertEqual(ok["mimeType"], "application/json")
        self.assertEqual(ok["encoding"], "text")
        self.assertIn('"pages": 20', ok["data"])
        self.assertTrue(responses[1]["result"].get("isError"))

    def test_artifact_event_carries_path_and_label(self) -> None:
        target = Path(self._tmp.name) / "progress" / "cover.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"png")
        sidecar_events.emit("report", "done", "cover ready", artifact=str(target), artifact_label="Deck cover")
        events_file = Path(self._tmp.name) / "progress" / "events.jsonl"
        event = json.loads(events_file.read_text().splitlines()[-1])
        self.assertEqual(event["artifact"]["label"], "Deck cover")
        self.assertEqual(event["artifact"]["path"], str(target))

    def test_unknown_method_and_tool_error_cleanly(self) -> None:
        responses = self.rpc(
            {"jsonrpc": "2.0", "id": 1, "method": "bogus/method"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "nope"}},
        )
        self.assertEqual(responses[0]["error"]["code"], -32601)
        self.assertEqual(responses[1]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
