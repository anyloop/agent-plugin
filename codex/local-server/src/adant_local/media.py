"""Local-file media operations backed by the scoped AdAnt HTTP API."""

from __future__ import annotations

import mimetypes
import time
import uuid
from pathlib import Path
from typing import Any

import httpx

from adant_local import api

DEFAULT_REQUEST_TIMEOUT_S = 300.0
DEFAULT_JOB_TIMEOUT_S = 75 * 60.0


def _request_json(
    method: str,
    route: str,
    *,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    timeout_s: float = DEFAULT_REQUEST_TIMEOUT_S,
) -> dict[str, Any]:
    url = f"{api.server_url()}{route}"
    try:
        response = httpx.request(
            method,
            url,
            headers=api._headers(api.load_token()),
            json=payload,
            params=params,
            timeout=timeout_s,
        )
    except httpx.HTTPError as exc:
        raise api.ApiError("unreachable", f"could not reach {url}: {exc}") from exc
    if response.status_code == 401:
        raise api.ApiError(
            "not-authenticated",
            "the local token was rejected",
            "mint a fresh token with the required scope, then call auth_bootstrap",
        )
    if response.status_code == 403:
        raise api.ApiError(
            "not-authenticated",
            f"the local token lacks the required capability: {response.text[:200]}",
            "mint a token that includes the media scope",
        )
    if response.status_code >= 400:
        raise api.ApiError(
            "phase-failed",
            f"AdAnt API request failed: {response.status_code} {response.text[:300]}",
        )
    try:
        result = response.json()
    except ValueError as exc:
        raise api.ApiError("phase-failed", "AdAnt API returned invalid JSON") from exc
    if not isinstance(result, dict):
        raise api.ApiError("phase-failed", "AdAnt API returned an invalid result")
    return result


def _local_file(path: str) -> tuple[Path, str, int]:
    target = Path(path).expanduser().resolve()
    try:
        stat = target.stat()
    except OSError as exc:
        raise api.ApiError("workspace-invalid", f"cannot read {target}: {exc}") from exc
    if not target.is_file() or stat.st_size <= 0:
        raise api.ApiError("workspace-invalid", f"not a non-empty file: {target}")
    content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
    return target, content_type, stat.st_size


def upload_local_file(path: str) -> dict[str, Any]:
    target, content_type, size = _local_file(path)
    slot = _request_json(
        "POST",
        "/v1/files/create-upload",
        payload={
            "filename": target.name,
            "content_type": content_type,
            "size_bytes": size,
        },
    )
    upload_url = slot.get("upload_url")
    upload_id = slot.get("id")
    if not isinstance(upload_url, str) or not isinstance(upload_id, str):
        raise api.ApiError("phase-failed", "upload slot omitted id or upload_url")
    try:
        with target.open("rb") as stream:
            uploaded = httpx.put(
                upload_url,
                headers={
                    "content-type": content_type,
                    "content-length": str(size),
                },
                content=stream,
                timeout=DEFAULT_REQUEST_TIMEOUT_S,
            )
    except (OSError, httpx.HTTPError) as exc:
        raise api.ApiError("unreachable", f"file upload failed: {exc}") from exc
    if uploaded.status_code < 200 or uploaded.status_code >= 300:
        raise api.ApiError(
            "phase-failed", f"file upload failed: HTTP {uploaded.status_code}"
        )
    completed = _request_json(
        "POST",
        "/v1/files/complete",
        payload={
            "id": upload_id,
            "filename": target.name,
            "content_type": content_type,
        },
    )
    content = _request_json("GET", f"/v1/files/{upload_id}/content")
    download_url = content.get("download_url")
    if not isinstance(download_url, str):
        raise api.ApiError("phase-failed", "completed upload has no download_url")
    return {
        "uploadId": upload_id,
        "url": download_url,
        "file": completed,
        "path": str(target),
        "contentType": content_type,
        "kind": "video"
        if content_type.startswith("video/")
        else "audio"
        if content_type.startswith("audio/")
        else "image"
        if content_type.startswith("image/")
        else "file",
    }


def _session_context(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "brainSessionId": str(params.get("brain_session_id") or uuid.uuid4()),
        "brainTurnId": str(params.get("brain_turn_id") or uuid.uuid4()),
        "skillId": params.get("skill_id"),
    }


def analyze_local_file(path: str, params: dict[str, Any]) -> dict[str, Any]:
    prompt = params.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise api.ApiError("phase-failed", "analyze requires params.prompt")
    upload = upload_local_file(path)
    body = {
        **_session_context(params),
        "prompt": prompt,
        "videoUrl": upload["url"],
    }
    if params.get("response_format") is not None:
        body["responseFormat"] = params["response_format"]
    if params.get("model") is not None:
        body["model"] = params["model"]
    result = _request_json("POST", "/v1/media.video.analyze", payload=body)
    analysis = result.get("text")
    if not isinstance(analysis, str):
        raise api.ApiError("phase-failed", "video analysis returned no text")
    response: dict[str, Any] = {"uploadId": upload["uploadId"], "analysis": analysis}
    output_path = params.get("output_path")
    if output_path:
        target = Path(str(output_path)).expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(analysis, encoding="utf-8")
        response["outputPath"] = str(target)
    return response


def _poll_job(job: dict[str, Any], session_id: str, params: dict[str, Any]) -> dict:
    if job.get("status") != "running":
        return job
    timeout_s = float(params.get("timeout_s", DEFAULT_JOB_TIMEOUT_S))
    interval_s = float(params.get("poll_interval_s", 3.0))
    if timeout_s <= 0 or interval_s <= 0:
        raise api.ApiError("phase-failed", "poll timeouts must be positive")
    deadline = time.monotonic() + min(timeout_s, DEFAULT_JOB_TIMEOUT_S)
    while time.monotonic() < deadline:
        time.sleep(min(interval_s, 30.0))
        job = _request_json(
            "GET",
            "/v1/media.job.get",
            params={"id": job.get("jobId"), "brainSessionId": session_id},
        )
        if job.get("status") != "running":
            return job
    raise api.ApiError(
        "phase-failed",
        f"media job {job.get('jobId', 'unknown')} is still running after timeout",
        "retry with the same job id through the remote media job tool",
    )


def _download_artifact(url: str, output_path: Path) -> None:
    try:
        with httpx.stream("GET", url, timeout=DEFAULT_REQUEST_TIMEOUT_S) as response:
            response.raise_for_status()
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("wb") as output:
                for chunk in response.iter_bytes():
                    output.write(chunk)
    except (OSError, httpx.HTTPError) as exc:
        raise api.ApiError("unreachable", f"artifact download failed: {exc}") from exc


def edit_local_image(path: str, params: dict[str, Any]) -> dict[str, Any]:
    prompt = params.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        raise api.ApiError("phase-failed", "edit requires params.prompt")
    upload = upload_local_file(path)
    context = _session_context(params)
    image_urls = params.get("image_urls", [])
    if not isinstance(image_urls, list) or not all(
        isinstance(item, str) for item in image_urls
    ):
        raise api.ApiError("phase-failed", "image_urls must be a list of URLs")
    body: dict[str, Any] = {
        **context,
        "prompt": prompt,
        "imageUrls": [upload["url"], *image_urls],
    }
    for local_name, wire_name in (
        ("size", "size"),
        ("quality", "quality"),
        ("model", "model"),
        ("title", "title"),
    ):
        if params.get(local_name) is not None:
            body[wire_name] = params[local_name]
    mask_path = params.get("mask_path")
    if mask_path:
        body["maskUrl"] = upload_local_file(str(mask_path))["url"]
    job = _request_json("POST", "/v1/media.image.edit", payload=body)
    if params.get("wait", True):
        job = _poll_job(job, context["brainSessionId"], params)
    if job.get("status") != "completed":
        return {"uploadId": upload["uploadId"], "job": job}
    artifact_url = job.get("artifactUrl")
    if not isinstance(artifact_url, str):
        raise api.ApiError("phase-failed", "completed media job has no artifactUrl")
    source = Path(path).expanduser().resolve()
    output_path = Path(
        str(params.get("output_path") or source.with_name(f"{source.stem}-edited.png"))
    ).expanduser().resolve()
    _download_artifact(artifact_url, output_path)
    return {
        "uploadId": upload["uploadId"],
        "outputPath": str(output_path),
        "job": job,
    }


def run_media_local(action: str, path: str, params: dict[str, Any]) -> dict:
    if action == "upload":
        return upload_local_file(path)
    if action == "analyze":
        return analyze_local_file(path, params)
    if action == "edit":
        return edit_local_image(path, params)
    raise api.ApiError(
        "phase-failed", f"unknown media action: {action}", "use upload, analyze, or edit"
    )


def register_media_tool(mcp, resource_uri: str) -> None:
    @mcp.tool(meta={"ui": {"resourceUri": resource_uri, "visibility": ["model", "app"]}})
    def media_local(action: str, path: str, params: dict[str, Any]) -> dict:
        """Upload, analyze, or edit a local media file with the scoped local
        token. params.prompt is required for analyze/edit; edit accepts
        output_path, mask_path, model, size, quality, wait, and timeout_s."""
        try:
            return run_media_local(action, path, params)
        except api.ApiError as exc:
            return exc.as_error()
        except (OSError, TypeError, ValueError) as exc:
            return api.ApiError("phase-failed", str(exc)).as_error()
