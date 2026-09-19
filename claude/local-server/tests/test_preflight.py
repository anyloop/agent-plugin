"""Authentication checks must not turn file presence or service errors into success."""

import asyncio
import json

import httpx
import pytest
from fastmcp import Client

from adant_local import api, preflight
from adant_local.server import mcp


@pytest.fixture
def credential(tmp_path, monkeypatch):
    monkeypatch.setenv("PLUGIN_DATA", str(tmp_path))
    monkeypatch.setenv("ADANT_SOCIAL_DATA_DIR", str(tmp_path / "ws"))
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / "local-token.json"
    path.write_text(json.dumps({"token": "alt_" + "x" * 40}))
    return path


@pytest.mark.parametrize(
    ("status", "ok", "code"),
    [(200, True, None), (401, False, "not-authenticated"),
     (403, False, "access-denied"), (404, None, "verification-failed"),
     (429, None, "verification-failed"), (503, None, "verification-failed")],
)
def test_live_local_auth_status(credential, monkeypatch, status, ok, code):
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return httpx.Response(status, text="account restriction" if status == 403 else "")

    monkeypatch.setattr(api.httpx, "get", get)
    check = preflight.local_auth_check()
    assert check["ok"] is ok
    assert check["required"] is True
    assert len(calls) == (2 if status == 401 else 1)
    if code:
        assert code in check["detail"]
        assert check["fix"]
    else:
        assert "remote MCP OAuth not checked" in check["detail"]
    assert "alt_" not in json.dumps(check)


def test_network_failure_is_unknown_not_bad_credentials(credential, monkeypatch):
    def offline(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(api.httpx, "get", offline)
    check = preflight.local_auth_check()
    assert check["ok"] is None
    assert "unreachable" in check["detail"]
    assert credential.exists()


@pytest.mark.parametrize("data", [None, [], {}, {"token": None}, {"token": ""}])
def test_invalid_stored_credentials_do_not_pass(credential, data):
    credential.write_text(json.dumps(data))
    assert preflight.local_auth_check()["ok"] is False


def test_local_success_does_not_claim_remote_auth(credential, monkeypatch):
    monkeypatch.setattr(api.httpx, "get", lambda *a, **kw: httpx.Response(200))

    async def scenario():
        async with Client(mcp) as client:
            result = (await client.call_tool("doctor", {"sessions": False})).data
            assert result["ok"] is True
            assert result["remote_auth"]["status"] == "not-checked"
            assert "adant_get_credit_balance" in result["remote_auth"]["next_step"]

    asyncio.run(scenario())


@pytest.mark.parametrize("status,code", [(403, "access-denied"), (503, "verification-failed")])
def test_bootstrap_reports_verification_failure(credential, monkeypatch, status, code):
    monkeypatch.setattr(api.httpx, "get", lambda *a, **kw: httpx.Response(status))

    async def scenario():
        async with Client(mcp) as client:
            result = (await client.call_tool("auth_bootstrap", {"minted_token": "alt_" + "y" * 40})).data
            assert result["error"]["code"] == code
            assert "ok" not in result
            assert credential.exists()

    asyncio.run(scenario())
