"""Stdlib-only AdAnt client shared by packaged research phase processes.

The phase runtimes execute in their own ``uv`` environments, so this module
intentionally avoids local-server-only dependencies such as httpx. It accepts
only the short-lived ``alt_*`` token stored by ``auth_bootstrap``; there is no
CLI or second-login fallback.
"""

from __future__ import annotations

import http.client
import json
import mimetypes
import os
import re
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

BRAIN_PROXY_PATH = "/api/app/brain"
DEFAULT_SERVER_URL = "https://api.adant.ai"
USER_AGENT = "adant-plugin/2.0 (+https://adant.ai)"


class AdantInferenceError(RuntimeError):
    """Raised when scoped AdAnt inference cannot complete."""


def _server_url() -> str:
    return (
        os.environ.get("ADANT_SERVER_URL", "").strip().rstrip("/")
        or DEFAULT_SERVER_URL
    )


def _token_file() -> Path:
    root = (
        os.environ.get("PLUGIN_DATA", "").strip()
        or os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    )
    base = Path(root) if root else Path.home() / ".adant" / "plugin-data"
    return base / "local-token.json"


def _load_token() -> str:
    try:
        token = json.loads(_token_file().read_text())["token"]
    except (OSError, KeyError, ValueError) as exc:
        raise AdantInferenceError(
            "AdAnt authentication is required. Mint a scoped token with "
            "adant_mint_local_token, then pass it to auth_bootstrap."
        ) from exc
    if not isinstance(token, str) or not token.startswith("alt_"):
        raise AdantInferenceError("The stored AdAnt local token is invalid.")
    return token


def _request(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 300,
    accept: str = "application/json",
):
    token = _load_token()
    request = urllib.request.Request(
        f"{_server_url()}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={
            "authorization": f"Bearer {token}",
            "content-type": "application/json",
            "accept": accept,
            "user-agent": USER_AGENT,
        },
    )
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            raise AdantInferenceError(
                "The stored AdAnt local token was rejected. Mint a fresh token "
                "with adant_mint_local_token, then call auth_bootstrap."
            ) from exc
        if exc.code == 403:
            raise AdantInferenceError(
                "The stored AdAnt local token lacks the required research or "
                "media scope. Mint the minimum required scope and retry."
            ) from exc
        try:
            detail = exc.read().decode(errors="replace")[:300]
        except Exception:  # noqa: BLE001 - preserve the primary HTTP failure
            detail = str(exc.reason or "")[:300]
        raise AdantInferenceError(f"AdAnt API {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise AdantInferenceError(f"AdAnt API unreachable: {exc.reason}") from exc


def _request_json(
    method: str,
    path: str,
    *,
    body: dict[str, Any] | None = None,
    timeout: float = 300,
) -> dict[str, Any]:
    with _request(method, path, body=body, timeout=timeout) as response:
        try:
            result = json.loads(response.read())
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AdantInferenceError("AdAnt API returned invalid JSON.") from exc
    if not isinstance(result, dict):
        raise AdantInferenceError("AdAnt API returned an invalid response.")
    return result


def _parse_json(text: str) -> Any:
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        for start, end in (("{", "}"), ("[", "]")):
            first = cleaned.find(start)
            last = cleaned.rfind(end)
            if first >= 0 and last > first:
                return json.loads(cleaned[first : last + 1])
        raise


def _chat(session_id: str, prompt: str, timeout: int) -> str:
    response = _request(
        "POST",
        f"{BRAIN_PROXY_PATH}/api/chat",
        body={"sessionId": session_id, "message": prompt},
        timeout=timeout,
        accept="text/event-stream",
    )
    text_parts: list[str] = []
    error_text: str | None = None
    completed = False
    with response:
        data_lines: list[str] = []
        for raw in response:
            line = raw.decode(errors="replace").rstrip("\r\n")
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
                continue
            if line or not data_lines:
                continue
            try:
                event = json.loads("\n".join(data_lines))
            except json.JSONDecodeError:
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
                    raise AdantInferenceError(
                        f"AdAnt turn ended with status {status}: "
                        f"{data.get('errorText') or error_text or ''}"
                    )
                completed = True
                break
    if not completed:
        raise AdantInferenceError(
            f"AdAnt turn ended before completion: {error_text or 'stream closed'}"
        )
    return "".join(text_parts)


def ask_adant(
    prompt: str,
    *,
    json_output: bool = True,
    title: str = "Plugin research",
    timeout: int = 900,
) -> Any:
    """Run one isolated token-authenticated AdAnt agent turn."""
    created = _request_json(
        "POST",
        f"{BRAIN_PROXY_PATH}/api/sessions",
        body={"agentKey": "adant-agent", "title": title},
        timeout=120,
    )
    try:
        session_id = created["session"]["id"]
    except (KeyError, TypeError) as exc:
        raise AdantInferenceError("AdAnt session response omitted its id.") from exc
    try:
        response = _chat(str(session_id), prompt, timeout)
        return _parse_json(response) if json_output else response
    finally:
        try:
            _request(
                "DELETE",
                f"{BRAIN_PROXY_PATH}/api/sessions/{session_id}",
                timeout=60,
            ).close()
        except AdantInferenceError:
            pass


def _upload_file(upload_url: str, source: Path, content_type: str) -> None:
    parsed = urlsplit(upload_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AdantInferenceError("AdAnt returned an invalid upload URL.")
    connection_type = (
        http.client.HTTPSConnection
        if parsed.scheme == "https"
        else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=300)
    request_path = parsed.path or "/"
    if parsed.query:
        request_path += f"?{parsed.query}"
    try:
        connection.putrequest("PUT", request_path)
        connection.putheader("content-type", content_type)
        connection.putheader("content-length", str(source.stat().st_size))
        connection.endheaders()
        with source.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                connection.send(chunk)
        response = connection.getresponse()
        detail = response.read(300).decode(errors="replace")
        if not 200 <= response.status < 300:
            raise AdantInferenceError(
                f"AdAnt upload failed: HTTP {response.status} {detail}"
            )
    except OSError as exc:
        raise AdantInferenceError(f"AdAnt upload failed: {exc}") from exc
    finally:
        connection.close()


def _upload_video(video: Path) -> str:
    source = video.expanduser().resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise AdantInferenceError(f"Video is not a readable file: {source}")
    content_type = mimetypes.guess_type(source.name)[0] or "video/mp4"
    slot = _request_json(
        "POST",
        "/v1/files/create-upload",
        body={
            "filename": source.name,
            "content_type": content_type,
            "size_bytes": source.stat().st_size,
        },
    )
    upload_id = slot.get("id")
    upload_url = slot.get("upload_url")
    if not isinstance(upload_id, str) or not isinstance(upload_url, str):
        raise AdantInferenceError("AdAnt upload slot omitted id or upload URL.")
    _upload_file(upload_url, source, content_type)
    _request_json(
        "POST",
        "/v1/files/complete",
        body={
            "id": upload_id,
            "filename": source.name,
            "content_type": content_type,
        },
    )
    content = _request_json("GET", f"/v1/files/{upload_id}/content")
    download_url = content.get("download_url")
    if not isinstance(download_url, str):
        raise AdantInferenceError("Completed upload omitted its download URL.")
    return download_url


def analyze_video_file(
    video: Path,
    prompt: str,
    *,
    schema: dict[str, Any] | None = None,
    model: str | None = None,
    timeout: int = 900,
) -> str:
    """Upload and analyze a local video with the scoped media API."""
    if schema:
        prompt = (
            f"{prompt}\n\nReturn ONLY JSON conforming to this schema:\n"
            f"{json.dumps(schema, ensure_ascii=False)}"
        )
    body: dict[str, Any] = {
        "brainSessionId": str(uuid.uuid4()),
        "brainTurnId": str(uuid.uuid4()),
        "skillId": "trend-video-understanding",
        "prompt": prompt,
        "videoUrl": _upload_video(video),
        "responseFormat": "json" if schema else "text",
    }
    if model:
        body["model"] = model
    result = _request_json(
        "POST", "/v1/media.video.analyze", body=body, timeout=timeout
    )
    text = result.get("text")
    if not isinstance(text, str):
        raise AdantInferenceError("AdAnt video analysis returned no text.")
    if schema:
        try:
            return json.dumps(_parse_json(text), indent=2, ensure_ascii=False)
        except (ValueError, json.JSONDecodeError):
            pass
    return text
