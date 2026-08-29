"""adant-local server tests (frozen R1 contracts)."""

from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from urllib.request import urlopen

import pytest
from fastmcp import Client

from adant_local import events
from adant_local.server import MEDIA_UI_URI, UI_MIME, UI_URI, mcp


@pytest.fixture(autouse=True)
def isolated_workspace(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("ADANT_SOCIAL_DATA_DIR", tmp)
        monkeypatch.setenv("PLUGIN_DATA", str(Path(tmp) / "plugin-data"))
        monkeypatch.setenv("HOME", tmp)  # isolate the pointer file
        yield Path(tmp)


def run(coro):
    return asyncio.run(coro)


def test_tools_and_panel_contract(isolated_workspace):
    async def scenario():
        async with Client(mcp) as client:
            tools = {t.name: t for t in await client.list_tools()}
            assert set(tools) == {
                "auth_bootstrap",
                "device_identity",
                "doctor",
                "media_local",
                "report_local",
                "research_artifact_read",
                "research_progress_fallback",
                "research_progress_open",
                "research_progress_snapshot",
                "research_run",
                "research_status",
                "research_workflow",
                "platform_session",
            }
            assert tools["research_progress_open"].meta["ui"]["resourceUri"] == UI_URI
            assert tools["media_local"].meta["ui"]["resourceUri"] == MEDIA_UI_URI
            assert "PROACTIVELY" in tools["research_progress_open"].description
            resources = {str(item.uri): item for item in await client.list_resources()}
            resource = resources[UI_URI]
            assert resource.mimeType == UI_MIME
            assert resources[MEDIA_UI_URI].mimeType == UI_MIME
            page = (await client.read_resource(UI_URI))[0].text
            assert "ui/initialize" in page and "AdAnt Research" in page
            assert "callServerTool" in page and "bridgeRequest" not in page
            media_page = (await client.read_resource(MEDIA_UI_URI))[0].text
            assert "ui/initialize" in media_page
            assert "callServerTool" in media_page
            assert "window.parent.postMessage" not in media_page
            first_device = (await client.call_tool("device_identity", {})).data
            second_device = (await client.call_tool("device_identity", {})).data
            assert first_device == second_device
            assert len(first_device["device_id"]) >= 20
            assert first_device["device_name"]
            assert (isolated_workspace / "plugin-data" / "device.json").stat().st_mode & 0o777 == 0o600
            opened = (await client.call_tool("research_progress_open", {})).data
            assert opened["widgetSessionId"]
            assert opened["fallbackUrl"].startswith("http://127.0.0.1:")
            with urlopen(opened["fallbackUrl"] + "healthz", timeout=2) as response:
                assert json.loads(response.read()) == {"ok": True}

    run(scenario())


def test_doctor_emits_events_and_shape():
    async def scenario():
        async with Client(mcp) as client:
            result = (await client.call_tool("doctor", {"sessions": False})).data
            names = [c["name"] for c in result["checks"]]
            assert names == ["python", "uv", "chrome", "yt-dlp", "adant-auth"]
            assert "node" not in names  # v2 drops the Node/npx prerequisite
            for check in result["checks"]:
                assert set(check) == {"name", "ok", "detail", "fix", "required"}
        snap = events.snapshot()
        statuses = [e["status"] for e in snap["events"] if e["phase"] == "doctor"]
        assert statuses[0] == "start" and statuses[-1] in ("done", "need-user")

    run(scenario())


def test_artifact_read_guards_workspace(isolated_workspace):
    inside = events.progress_dir() / "report.json"
    inside.parent.mkdir(parents=True, exist_ok=True)
    inside.write_text('{"pages": 20}')
    events.emit("report", "start", "anchor workspace")  # sets the pointer

    async def scenario():
        async with Client(mcp) as client:
            ok = (
                await client.call_tool("research_artifact_read", {"path": str(inside)})
            ).data
            assert ok["mimeType"] == "application/json" and '"pages": 20' in ok["data"]
            denied = (
                await client.call_tool("research_artifact_read", {"path": "/etc/hosts"})
            ).data
            assert denied["error"]["code"] == "artifact-denied"

    run(scenario())


def test_auth_bootstrap_stores_token(isolated_workspace, monkeypatch):
    monkeypatch.setenv(
        "ADANT_SERVER_URL", "http://127.0.0.1:9"
    )  # unreachable: verify stays lazy

    async def scenario():
        async with Client(mcp) as client:
            bad = (await client.call_tool("auth_bootstrap", {"minted_token": "x"})).data
            assert bad["error"]["code"] == "not-authenticated"
            good = (
                await client.call_tool(
                    "auth_bootstrap", {"minted_token": "tok_" + "a" * 40}
                )
            ).data
            assert good["ok"] is True and good["verified"] is None
            stored = json.loads(Path(good["stored"]).read_text())
            assert stored["token"].startswith("tok_")
            doctor = (await client.call_tool("doctor", {})).data
            auth = next(c for c in doctor["checks"] if c["name"] == "adant-auth")
            assert auth["ok"] is True

    run(scenario())


def test_variant_phase_requires_variant(isolated_workspace):
    async def scenario():
        async with Client(mcp) as client:
            result = (
                await client.call_tool(
                    "research_run",
                    {
                        "phase_runs": [{"id": "keywords", "args": {}}],
                        "workspace": str(isolated_workspace),
                    },
                )
            ).data
            assert result["error"]["code"] == "phase-failed"
            assert "variant" in result["error"]["message"]

    run(scenario())
