"""Tests for the Sidecar progress server and window bootstrap."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RUNTIME))

import sidecar_bootstrap  # noqa: E402
import sidecar_events  # noqa: E402


class WindowEnvironment(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = {
            key: os.environ.get(key)
            for key in ("ADANT_SOCIAL_DATA_DIR", "ADANT_NO_SIDECAR", "ADANT_SIDECAR_BROWSER", "ADANT_SIDECAR_WINDOW")
        }
        os.environ["ADANT_SOCIAL_DATA_DIR"] = self._tmp.name
        os.environ.pop("ADANT_NO_SIDECAR", None)
        os.environ.pop("ADANT_SIDECAR_BROWSER", None)
        os.environ.pop("ADANT_SIDECAR_WINDOW", None)

    def tearDown(self) -> None:
        lock = Path(self._tmp.name) / "progress" / "sidecar.json"
        if lock.exists():
            try:
                pid = json.loads(lock.read_text())["pid"]
                os.kill(pid, signal.SIGTERM)
            except (OSError, KeyError, json.JSONDecodeError):
                pass
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmp.cleanup()

    def lock(self) -> dict:
        path = Path(self._tmp.name) / "progress" / "sidecar.json"
        return json.loads(path.read_text())

    def get(self, url: str, timeout: float = 5) -> bytes:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read()


class ServerTests(WindowEnvironment):
    def start_server(self, *extra: str) -> dict:
        self._server_proc = subprocess.Popen(
            [sys.executable, str(RUNTIME / "sidecar_server.py"), *extra],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=os.environ.copy(),
        )
        self.addCleanup(self._reap_server)
        deadline = time.monotonic() + 8
        path = Path(self._tmp.name) / "progress" / "sidecar.json"
        while time.monotonic() < deadline:
            if path.exists():
                try:
                    return self.lock()
                except json.JSONDecodeError:
                    pass
            time.sleep(0.1)
        raise AssertionError("server did not write its lock file")

    def test_serves_page_health_and_jobs(self) -> None:
        lock = self.start_server()
        page = self.get(lock["url"]).decode()
        self.assertIn("AdAnt Research", page)
        self.assertIn("flowbar", page)
        self.assertIn('id="timebar"', page)
        self.assertIn("data-phase-clock", page)
        self.assertIn("target_seconds", page)
        self.assertEqual(json.loads(self.get(lock["url"] + "healthz")), {"ok": True})
        self.assertEqual(json.loads(self.get(lock["url"] + "jobs")), [])

    def test_sse_replays_existing_events(self) -> None:
        sidecar_events.emit("keywords", "start", "hello sse")
        lock = self.start_server()
        request = urllib.request.urlopen(lock["url"] + "events", timeout=5)
        deadline = time.monotonic() + 5
        seen = b""
        while time.monotonic() < deadline and b"hello sse" not in seen:
            seen += request.readline()
        request.close()
        self.assertIn(b"hello sse", seen)
        self.assertIn(b"data: {", seen)

    def _reap_server(self) -> None:
        proc = getattr(self, "_server_proc", None)
        if proc is None:
            return
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    def test_artifact_endpoint_serves_workspace_files_only(self) -> None:
        workspace_root = Path(self._tmp.name).parent  # data dir parent
        report = Path(self._tmp.name) / "progress" / "report.md"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text("# Findings\nhello artifact")
        lock = self.start_server()
        body = self.get(lock["url"] + "artifact?path=" + str(report)).decode()
        self.assertIn("hello artifact", body)
        import urllib.error

        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.get(lock["url"] + "artifact?path=/etc/hosts")
        self.assertEqual(caught.exception.code, 403)

    def test_watchdog_exits_when_lock_removed(self) -> None:
        self.start_server("--idle-timeout", "0")
        (Path(self._tmp.name) / "progress" / "sidecar.json").unlink()
        try:
            self.assertEqual(self._server_proc.wait(timeout=15), 0)
        except subprocess.TimeoutExpired:
            self.fail("server did not exit after its lock was removed")


class BootstrapTests(WindowEnvironment):
    def test_opt_out(self) -> None:
        os.environ["ADANT_NO_SIDECAR"] = "1"
        result = sidecar_bootstrap.ensure_sidecar()
        self.assertEqual(result, {"status": "disabled", "url": None, "reason": "opt-out"})

    def test_starts_server_and_is_idempotent(self) -> None:
        capture = Path(self._tmp.name) / "browser-args.txt"
        launcher = Path(self._tmp.name) / "fake-browser.sh"
        launcher.write_text(f"#!/bin/sh\necho \"$@\" >> {capture}\n")
        launcher.chmod(0o755)
        os.environ["ADANT_SIDECAR_BROWSER"] = str(launcher)
        os.environ["ADANT_SIDECAR_WINDOW"] = "1"

        first = sidecar_bootstrap.ensure_sidecar()
        self.assertEqual(first["status"], "ready", first)
        self.assertEqual(first["reason"], "started")
        self.assertTrue(first["url"].startswith("http://127.0.0.1:"))
        self.assertIn("AdAnt Research", self.get(first["url"]).decode())

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not capture.exists():
            time.sleep(0.05)
        args = capture.read_text()
        self.assertIn(f"--app={first['url']}", args)
        self.assertIn("--window-size=420,900", args)

        second = sidecar_bootstrap.ensure_sidecar()
        self.assertEqual(second["status"], "ready")
        self.assertEqual(second["reason"], "already-running")
        self.assertEqual(second["url"], first["url"])
        self.assertEqual(len(capture.read_text().splitlines()), 1, "window must open once")

    def test_window_is_opt_in(self) -> None:
        capture = Path(self._tmp.name) / "browser-args.txt"
        launcher = Path(self._tmp.name) / "fake-browser.sh"
        launcher.write_text(f"#!/bin/sh\necho \"$@\" >> {capture}\n")
        launcher.chmod(0o755)
        os.environ["ADANT_SIDECAR_BROWSER"] = str(launcher)
        result = sidecar_bootstrap.ensure_sidecar()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["reason"], "started")
        time.sleep(0.5)
        self.assertFalse(capture.exists(), "no window may open without ADANT_SIDECAR_WINDOW=1")

    def test_missing_browser_still_ready(self) -> None:
        os.environ["ADANT_SIDECAR_WINDOW"] = "1"
        os.environ["ADANT_SIDECAR_BROWSER"] = str(Path(self._tmp.name) / "nope")
        result = sidecar_bootstrap.ensure_sidecar()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["reason"], "window-no-chrome")

    def test_run_phase_announces_sidecar(self) -> None:
        os.environ["ADANT_NO_SIDECAR"] = "1"
        result = subprocess.run(
            [sys.executable, str(RUNTIME / "run_phase.py"), "run", "--phase", "keywords",
             "--", sys.executable, "-c", "print('ok')"],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("sidecar: disabled (opt-out)", result.stdout)


if __name__ == "__main__":
    unittest.main()
