"""Direct HTTPS client for api.adant.ai using the minted local token.

The local server authenticates with the `alt_*` token stored by auth_bootstrap
and talks to the server's brain proxy directly. Wire format mirrors the
CLI's BrainClient: create a session at POST {proxy}/api/sessions, then
stream POST {proxy}/api/chat as SSE where `message` events carry assistant
text and `done` ends the turn.
"""

from __future__ import annotations

import json
import os
import platform
import secrets
from pathlib import Path

import httpx

BRAIN_PROXY_PATH = "/api/app/brain"
DEFAULT_SERVER_URL = "https://api.adant.ai"
DEFAULT_TIMEOUT_S = 300.0


class ApiError(RuntimeError):
    def __init__(self, code: str, message: str, fix: str | None = None):
        super().__init__(message)
        self.code = code
        self.fix = fix

    def as_error(self) -> dict:
        payload: dict = {"error": {"code": self.code, "message": str(self)}}
        if self.fix:
            payload["error"]["fix"] = self.fix
        return payload


def server_url() -> str:
    return (
        os.environ.get("ADANT_SERVER_URL", "").strip().rstrip("/") or DEFAULT_SERVER_URL
    )


def data_dir() -> Path:
    root = (
        os.environ.get("PLUGIN_DATA", "").strip()
        or os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    )
    return Path(root) if root else Path.home() / ".adant" / "plugin-data"


def _token_file() -> Path:
    return data_dir() / "local-token.json"


def device_identity() -> dict[str, str]:
    """Return a stable opaque id and recognizable name for this install."""
    identity_file = data_dir() / "device.json"
    try:
        saved = json.loads(identity_file.read_text())
        device_id = saved["device_id"]
        device_name = saved["device_name"]
        if isinstance(device_id, str) and isinstance(device_name, str):
            return {"device_id": device_id, "device_name": device_name}
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        pass

    node = platform.node().strip()
    system = platform.system().strip() or "Local device"
    device_name = f"{system} · {node}" if node else system
    identity = {
        "device_id": secrets.token_urlsafe(32),
        "device_name": device_name[:100],
    }
    identity_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = identity_file.with_suffix(".tmp")
    temp_file.write_text(json.dumps(identity))
    temp_file.chmod(0o600)
    temp_file.replace(identity_file)
    return identity


def load_token() -> str:
    try:
        return json.loads(_token_file().read_text())["token"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        raise ApiError(
            "not-authenticated",
            "no local token is stored",
            "mint one with adant_mint_local_token (remote MCP), then call auth_bootstrap",
        ) from exc


USER_AGENT = "adant-plugin/2.0 (+https://adant.ai)"


def _headers(token: str) -> dict[str, str]:
    # An explicit identity: default client signatures are rejected at the
    # edge (Cloudflare) before the request reaches AdAnt.
    identity = device_identity()
    return {
        "authorization": f"Bearer {token}",
        "content-type": "application/json",
        "user-agent": USER_AGENT,
        "x-adant-device-id": identity["device_id"],
    }


def verify_token(token: str, timeout_s: float = 20.0) -> bool:
    """Prove the token end to end without requiring one particular scope."""
    url = f"{server_url()}{BRAIN_PROXY_PATH}/api/health"
    try:
        response = httpx.get(url, headers=_headers(token), timeout=timeout_s)
    except httpx.HTTPError as exc:
        raise ApiError("unreachable", f"could not reach {url}: {exc}") from exc
    if response.status_code == 401:
        # The health endpoint is deliberately research-scoped. A media- or
        # report-only credential can still prove identity against the static,
        # authenticated model catalog without gaining a media operation.
        fallback_url = f"{server_url()}/v1/media.models"
        try:
            response = httpx.get(
                fallback_url, headers=_headers(token), timeout=timeout_s
            )
        except httpx.HTTPError as exc:
            raise ApiError(
                "unreachable", f"could not reach {fallback_url}: {exc}"
            ) from exc
    if response.status_code == 401:
        raise ApiError(
            "not-authenticated",
            "the token was rejected (expired, revoked, or malformed)",
            "mint a fresh token with adant_mint_local_token",
        )
    if response.status_code == 403:
        # Account-level refusal (unverified email / suspended), not a token
        # problem — reporting it as "verified" would defer the failure to
        # every later inference call with no explanation.
        raise ApiError(
            "not-authenticated",
            f"the account cannot use AdAnt right now: {response.text[:160]}",
            "verify the account email or contact support, then retry",
        )
    return response.status_code < 500


def create_session(
    agent_key: str = "adant-agent", title: str | None = None, timeout_s: float = 60.0
) -> str:
    token = load_token()
    url = f"{server_url()}{BRAIN_PROXY_PATH}/api/sessions"
    response = httpx.post(
        url,
        headers=_headers(token),
        json={"agentKey": agent_key, "title": title},
        timeout=timeout_s,
    )
    if response.status_code == 401:
        raise ApiError(
            "not-authenticated",
            "token rejected while creating a session",
            "mint a fresh token with adant_mint_local_token",
        )
    if response.status_code >= 400:
        raise ApiError(
            "phase-failed",
            f"session create failed: {response.status_code} {response.text[:200]}",
        )
    return response.json()["session"]["id"]


def chat(session_id: str, message: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> str:
    """Send one message and return the assistant's full text for the turn."""
    token = load_token()
    url = f"{server_url()}{BRAIN_PROXY_PATH}/api/chat"
    headers = {**_headers(token), "accept": "text/event-stream"}
    text_parts: list[str] = []
    error_text: str | None = None
    completed = False
    with httpx.stream(
        "POST",
        url,
        headers=headers,
        json={"sessionId": session_id, "message": message},
        timeout=timeout_s,
    ) as response:
        if response.status_code == 401:
            raise ApiError(
                "not-authenticated",
                "token rejected during chat",
                "mint a fresh token with adant_mint_local_token",
            )
        if response.status_code >= 400:
            response.read()
            raise ApiError(
                "phase-failed",
                f"chat failed: {response.status_code} {response.text[:200]}",
            )
        for event in _iter_sse_events(response.iter_lines()):
            kind = event.get("type")
            if kind == "message" and isinstance(event.get("text"), str):
                text_parts.append(event["text"])
            elif kind == "error" and isinstance(event.get("text"), str):
                error_text = event["text"]
            elif kind == "done":
                data = event.get("data") or {}
                status = data.get("status")
                if status and status != "succeeded":
                    raise ApiError(
                        "phase-failed",
                        f"turn ended with status {status}: {data.get('errorText') or error_text or ''}",
                    )
                completed = True
                break
    if not completed:
        # The stream ended without a terminal "done" frame: a mid-turn crash
        # or a dropped connection. Returning the partial text would persist a
        # truncated inference as a successful result.
        raise ApiError(
            "phase-failed",
            f"the turn ended without completing: {error_text or 'stream closed early'}",
            "retry the phase",
        )
    return "".join(text_parts)


def agent_infer(
    prompt: str, agent_key: str = "adant-agent", timeout_s: float = DEFAULT_TIMEOUT_S
) -> str:
    """One-shot inference: fresh session, one turn, assistant text back."""
    session_id = create_session(agent_key=agent_key)
    return chat(session_id, prompt, timeout_s=timeout_s)


def _iter_sse_events(lines) -> "list[dict]":
    """Minimal SSE parser: yields the JSON payload of each data: frame."""

    def generator():
        data_lines: list[str] = []
        for raw in lines:
            line = raw.decode() if isinstance(raw, bytes) else raw
            if line == "":
                if data_lines:
                    try:
                        yield json.loads("\n".join(data_lines))
                    except json.JSONDecodeError:
                        pass
                    data_lines = []
                continue
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        if data_lines:
            try:
                yield json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
                pass

    return generator()
