"""Tests for resilient short-form video acquisition."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RUNTIME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME))

import understand_video  # noqa: E402
from video_acquisition import (  # noqa: E402
    _download_command,
    acquire_video,
    classify_download_error,
)


class DownloadCommandTests(unittest.TestCase):
    def test_command_uses_browser_compatible_features(self) -> None:
        command = _download_command(
            "https://www.youtube.com/shorts/example",
            "/tmp/source.%(ext)s",
            cookies_from_browser="chrome:/tmp/research-profile",
            node_runtime="/opt/node/bin/node",
            impersonate=True,
        )
        self.assertIn("--ignore-config", command)
        self.assertIn("--js-runtimes", command)
        self.assertIn("node:/opt/node/bin/node", command)
        self.assertIn("--impersonate", command)
        self.assertIn("--cookies-from-browser", command)
        self.assertIn("--socket-timeout", command)
        self.assertIn("--extractor-retries", command)

    def test_impersonation_failure_retries_without_impersonation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            calls = []

            def run(command, **_kwargs):
                calls.append(command)
                if len(calls) == 1:
                    return subprocess.CompletedProcess(
                        command,
                        1,
                        "",
                        "No impersonate target is available",
                    )
                (Path(directory) / "source.mp4").write_bytes(b"video")
                return subprocess.CompletedProcess(command, 0, "ok", "")

            with patch("video_acquisition.subprocess.run", side_effect=run):
                result = acquire_video(
                    "https://www.tiktok.com/@creator/video/1",
                    Path(directory),
                    node_runtime="/opt/node",
                )
        self.assertEqual(result.status, "ok")
        self.assertEqual(len(calls), 2)
        self.assertIn("--impersonate", calls[0])
        self.assertNotIn("--impersonate", calls[1])

    def test_download_errors_are_actionable(self) -> None:
        self.assertEqual(classify_download_error("HTTP Error 403: Forbidden"), "forbidden")
        self.assertEqual(
            classify_download_error("No supported JavaScript runtime could be found"),
            "js_runtime_missing",
        )
        self.assertEqual(
            classify_download_error("Sign in to confirm you're not a bot"),
            "auth_required",
        )
        self.assertEqual(
            classify_download_error("Unexpected response from webpage request"),
            "platform_blocked",
        )


class OutputRetryTests(unittest.TestCase):
    def test_only_successful_outputs_are_cached(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            output.write_text(json.dumps({"status": "download_failed"}))
            self.assertFalse(understand_video.successful_output_exists(output))
            output.write_text(json.dumps({"status": "ok"}))
            self.assertTrue(understand_video.successful_output_exists(output))

    def test_missing_local_video_writes_structured_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(RUNTIME / "understand_video.py"),
                    "--video",
                    str(Path(directory) / "missing.mp4"),
                    "-o",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            payload = json.loads(output.read_text())
        self.assertEqual(result.returncode, 2)
        self.assertEqual(payload["status"], "download_failed")
        self.assertEqual(payload["acquisition"]["backend"], "local-file")
        self.assertEqual(payload["acquisition"]["error_code"], "missing_local_file")


if __name__ == "__main__":
    unittest.main()
