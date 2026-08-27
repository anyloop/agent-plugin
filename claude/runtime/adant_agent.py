"""Authenticated AdAnt agent inference for packaged research skills.

This adapter deliberately shells out without a shell so prompts and user input are
passed as literal arguments. AdAnt owns the model credentials and usage accounting;
plugin users only authenticate with AdAnt.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any


ADANT_CLI = ["npx", "--yes", "@anyloop/adant-cli"]
AUTH_ERROR_MARKERS = (
    "http 401",
    "status: 401",
    "not authenticated",
    "authentication required",
    "not logged in",
    "unauthorized",
)


class AdantAgentError(RuntimeError):
    """Raised when the authenticated AdAnt CLI cannot complete a request."""


def _run(args: list[str], timeout: int) -> str:
    try:
        result = subprocess.run(
            [*ADANT_CLI, *args],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise AdantAgentError("Node.js/npx is required to run AdAnt research.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        if any(marker in detail.lower() for marker in AUTH_ERROR_MARKERS):
            detail = (
                "AdAnt authentication is required. Run "
                "`npx @anyloop/adant-cli auth login` in your system terminal, then "
                "retry. No Gemini API key is needed."
            )
        raise AdantAgentError(detail) from exc
    except subprocess.TimeoutExpired as exc:
        raise AdantAgentError("AdAnt research timed out; retry the step.") from exc
    return result.stdout.strip()


def _parse_json(text: str) -> Any:
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        first_object = cleaned.find("{")
        last_object = cleaned.rfind("}")
        if first_object >= 0 and last_object > first_object:
            return json.loads(cleaned[first_object : last_object + 1])
        first_array = cleaned.find("[")
        last_array = cleaned.rfind("]")
        if first_array >= 0 and last_array > first_array:
            return json.loads(cleaned[first_array : last_array + 1])
        raise


def ask_adant(
    prompt: str,
    *,
    json_output: bool = True,
    title: str = "Plugin research",
    timeout: int = 900,
) -> Any:
    """Run one isolated AdAnt agent turn and return JSON or response text."""

    created = _run(
        [
            "session",
            "create",
            "--agent",
            "adant-agent",
            "--title",
            title,
            "--json",
        ],
        timeout=120,
    )
    session_id = json.loads(created)["id"]
    try:
        response = _run(
            ["session", "chat", prompt, "--session_id", session_id],
            timeout=timeout,
        )
        return _parse_json(response) if json_output else response
    finally:
        try:
            _run(["session", "delete", "--session_id", session_id], timeout=60)
        except AdantAgentError:
            pass


# ---------------------------------------------------------------------------
# Token-direct transport (plugin v2 single sign-on).
#
# When auth_bootstrap has stored a minted alt_* token, research inference
# talks to the server's brain proxy directly over HTTPS — no Node/npx and no
# second login. Without a token the legacy CLI path above keeps working.
# Wire format mirrors the CLI client: POST {proxy}/api/sessions, then
# POST {proxy}/api/chat consumed as SSE ("message" events carry text,
# "done" ends the turn). Stdlib-only so the v1 runtime stays dependency-free.
# ---------------------------------------------------------------------------

import os
import urllib.error
import urllib.request
from pathlib import Path

_BRAIN_PROXY_PATH = "/api/app/brain"
_DEFAULT_SERVER_URL = "https://api.adant.ai"


def _server_url() -> str:
    return (
        os.environ.get("ADANT_SERVER_URL", "").strip().rstrip("/")
        or _DEFAULT_SERVER_URL
    )


def _token_file() -> Path:
    root = (
        os.environ.get("PLUGIN_DATA", "").strip()
        or os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    )
    base = Path(root) if root else Path.home() / ".adant" / "plugin-data"
    return base / "local-token.json"


def _load_local_token() -> "str | None":
    try:
        return json.loads(_token_file().read_text())["token"]
    except (OSError, KeyError, ValueError):
        return None


def _http_json(method: str, path: str, token: str, body: "dict | None",
               timeout: int, accept: str = "application/json"):
    request = urllib.request.Request(
        f"{_server_url()}{_BRAIN_PROXY_PATH}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "accept": accept,
        },
    )
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:200]
        if exc.code == 401:
            raise AdantAgentError(
                "The stored AdAnt local token was rejected (expired or revoked). "
                "Mint a fresh one with adant_mint_local_token, then auth_bootstrap."
            ) from exc
        raise AdantAgentError(f"AdAnt API {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AdantAgentError(f"AdAnt API unreachable: {exc.reason}") from exc


def _http_ask(prompt: str, title: str, timeout: int) -> str:
    token = _load_local_token()
    assert token is not None
    with _http_json("POST", "/api/sessions", token,
                    {"agentKey": "adant-agent", "title": title}, 120) as res:
        session_id = json.loads(res.read())["session"]["id"]
    text_parts = []
    error_text = None
    try:
        response = _http_json(
            "POST", "/api/chat", token,
            {"sessionId": session_id, "message": prompt},
            timeout, accept="text/event-stream",
        )
        with response:
            data_lines = []
            for raw in response:
                line = raw.decode(errors="replace").rstrip("\n").rstrip("\r")
                if line == "":
                    if data_lines:
                        try:
                            event = json.loads("\n".join(data_lines))
                        except ValueError:
                            event = {}
                        data_lines = []
                        kind = event.get("type")
                        if kind == "message" and isinstance(event.get("text"), str):
                            text_parts.append(event["text"])
                        elif kind == "error" and isinstance(event.get("text"), str):
                            error_text = event["text"]
                        elif kind == "done":
                            data = event.get("data") or {}
                            status = data.get("status")
                            if status and status != "succeeded":
                                raise AdantAgentError(
                                    f"AdAnt turn ended with status {status}: "
                                    f"{data.get('errorText') or error_text or ''}"
                                )
                            break
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[5:].lstrip())
    finally:
        try:
            _http_json("DELETE", f"/api/sessions/{session_id}", token, None, 60).close()
        except AdantAgentError:
            pass
    return "".join(text_parts)


_original_cli_ask = ask_adant


def ask_adant(  # noqa: F811 - deliberate transport-selecting override
    prompt: str,
    *,
    json_output: bool = True,
    title: str = "Plugin research",
    timeout: int = 900,
) -> Any:
    """Run one isolated AdAnt agent turn and return JSON or response text.

    Prefers the token-direct HTTP transport when a minted local token is
    stored; otherwise falls back to the authenticated CLI.
    """
    if _load_local_token() is not None:
        response = _http_ask(prompt, title, timeout)
        return _parse_json(response) if json_output else response
    return _original_cli_ask(prompt, json_output=json_output, title=title, timeout=timeout)
