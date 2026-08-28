"""Acquire short-form source media without coupling it to AdAnt analysis."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AcquisitionResult:
    path: Path | None
    backend: str
    status: str
    error_code: str | None = None
    error: str | None = None

    def metadata(self) -> dict:
        result = {"backend": self.backend, "status": self.status}
        if self.error_code:
            result["error_code"] = self.error_code
        if self.error:
            result["error"] = self.error
        return result


def classify_download_error(stderr: str) -> str:
    text = stderr.casefold()
    if "impersonat" in text and ("unavailable" in text or "no impersonate" in text):
        return "impersonation_unavailable"
    if "cookies" in text and any(word in text for word in ("failed", "unable", "could not")):
        return "cookie_unavailable"
    if "javascript runtime" in text or "js runtime" in text or "yt-dlp-ejs" in text:
        return "js_runtime_missing"
    if "http error 403" in text or "forbidden" in text:
        return "forbidden"
    if "unexpected response from webpage request" in text:
        return "platform_blocked"
    if "login" in text or "sign in" in text or "authentication" in text:
        return "auth_required"
    if "timed out" in text or "timeout" in text:
        return "timeout"
    if "private" in text:
        return "private"
    if "not available" in text or "unavailable" in text:
        return "unavailable"
    return "download_failed"


def _download_command(
    url: str,
    output_template: str,
    *,
    cookies_from_browser: str | None,
    node_runtime: str | None,
    impersonate: bool,
) -> list[str]:
    command = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize",
        "200M",
        "--socket-timeout",
        "20",
        "--retries",
        "1",
        "--fragment-retries",
        "1",
        "--extractor-retries",
        "1",
    ]
    if node_runtime:
        command += ["--js-runtimes", f"node:{node_runtime}"]
    if impersonate:
        command += ["--impersonate", "chrome"]
    if cookies_from_browser:
        command += ["--cookies-from-browser", cookies_from_browser]
    return [
        *command,
        "-f",
        "best[ext=mp4]/best",
        "-o",
        output_template,
        url,
    ]


def _downloaded_file(work_dir: Path) -> Path | None:
    for path in work_dir.glob("source.*"):
        if path.suffix not in (".part", ".ytdl") and path.is_file() and path.stat().st_size:
            return path
    return None


def acquire_video(
    url: str,
    work_dir: Path,
    *,
    cookies_from_browser: str | None = None,
    node_runtime: str | None = None,
    timeout_seconds: float = 120,
) -> AcquisitionResult:
    """Download one public video, using browser-compatible yt-dlp features."""
    output_template = str(work_dir / "source.%(ext)s")
    node_runtime = node_runtime or shutil.which("node")
    command = _download_command(
        url,
        output_template,
        cookies_from_browser=cookies_from_browser,
        node_runtime=node_runtime,
        impersonate=True,
    )
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return AcquisitionResult(None, "yt-dlp", "failed", "timeout", "download timed out")
    error = (result.stderr or result.stdout).strip()
    error_code = classify_download_error(error)
    if result.returncode != 0 and error_code in {
        "cookie_unavailable",
        "impersonation_unavailable",
    }:
        retry = _download_command(
            url,
            output_template,
            cookies_from_browser=None if error_code == "cookie_unavailable" else cookies_from_browser,
            node_runtime=node_runtime,
            impersonate=False if error_code == "impersonation_unavailable" else True,
        )
        try:
            result = subprocess.run(
                retry,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return AcquisitionResult(None, "yt-dlp", "failed", "timeout", "download timed out")
        error = (result.stderr or result.stdout).strip()
        error_code = classify_download_error(error)
    path = _downloaded_file(work_dir) if result.returncode == 0 else None
    if path:
        return AcquisitionResult(path, "yt-dlp", "ok")
    return AcquisitionResult(None, "yt-dlp", "failed", error_code, error[-800:] or None)
