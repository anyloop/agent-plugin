"""Ensure the Sidecar progress window exists — as a side effect, not a step.

``ensure_sidecar()`` is called at the entry of every research command
(``run_phase.py``, ``doctor.py``), so the window appears the moment research
actually starts, whether or not the agent remembered any instruction. It is
idempotent and cheap when the server is already up, degrades silently to
chat-only research when anything fails, and never raises.

Opt-out: set ``ADANT_NO_SIDECAR=1`` (or ask the agent, which exports it).
Test/browser override: ``ADANT_SIDECAR_BROWSER=/path/to/launcher``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_events import progress_dir  # noqa: E402

LOCK_NAME = "sidecar.json"
WINDOW_SIZE = (420, 900)
SERVER_WAIT_SECONDS = 6.0


def _lock_path() -> Path:
    return progress_dir() / LOCK_NAME


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_lock() -> dict | None:
    try:
        data = json.loads(_lock_path().read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or "port" not in data or "pid" not in data:
        return None
    return data


def _find_browser() -> str | None:
    override = os.environ.get("ADANT_SIDECAR_BROWSER", "").strip()
    if override:
        return override if Path(override).exists() or shutil.which(override) else None
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    return next((c for c in candidates if c and Path(c).exists()), None)


def _window_position() -> tuple[int, int]:
    """Best-effort right-edge placement; a fixed fallback is fine."""
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["osascript", "-e", 'tell application "Finder" to get bounds of window of desktop'],
                capture_output=True,
                text=True,
                timeout=3,
            )
            parts = [int(x.strip()) for x in result.stdout.split(",")]
            if len(parts) == 4:
                return max(parts[2] - WINDOW_SIZE[0] - 24, 0), 60
        except Exception:  # noqa: BLE001
            pass
    return 900, 60


def _spawn_server() -> dict | None:
    server = Path(__file__).resolve().parent / "sidecar_server.py"
    logs = progress_dir() / "logs"
    try:
        logs.mkdir(parents=True, exist_ok=True)
        with open(logs / "sidecar-server.log", "a", encoding="utf-8") as log_file:
            subprocess.Popen(
                [sys.executable, str(server)],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
    except Exception:  # noqa: BLE001
        return None
    deadline = time.monotonic() + SERVER_WAIT_SECONDS
    while time.monotonic() < deadline:
        lock = _read_lock()
        if lock and _pid_alive(int(lock["pid"])):
            return lock
        time.sleep(0.15)
    return None


def _open_window(url: str) -> tuple[bool, str]:
    browser = _find_browser()
    if not browser:
        return False, "no-chrome"
    x, y = _window_position()
    try:
        subprocess.Popen(
            [
                browser,
                f"--app={url}",
                f"--window-size={WINDOW_SIZE[0]},{WINDOW_SIZE[1]}",
                f"--window-position={x},{y}",
                "--no-first-run",
                "--no-default-browser-check",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as error:  # noqa: BLE001
        return False, f"launch-failed: {error.__class__.__name__}"
    return True, "opened"


def ensure_sidecar(open_window: bool = True) -> dict:
    """Idempotently ensure server (and window, once) exist.

    Returns {"status": "ready"|"disabled", "url": str|None, "reason": str}.
    Never raises.
    """
    try:
        if os.environ.get("ADANT_NO_SIDECAR", "").strip() in ("1", "true", "yes"):
            return {"status": "disabled", "url": None, "reason": "opt-out"}
        lock = _read_lock()
        if lock and _pid_alive(int(lock["pid"])):
            return {"status": "ready", "url": lock["url"], "reason": "already-running"}
        lock = _spawn_server()
        if not lock:
            return {"status": "disabled", "url": None, "reason": "server-start-failed"}
        url = lock["url"]
        if open_window:
            opened, detail = _open_window(url)
            if not opened:
                return {"status": "ready", "url": url, "reason": f"window-{detail}"}
        return {"status": "ready", "url": url, "reason": "started"}
    except Exception:  # noqa: BLE001 - the sidecar must never block research
        return {"status": "disabled", "url": None, "reason": "unexpected-error"}


def announce(result: dict) -> None:
    """One stdout line the agent can read and relay."""
    if result["status"] == "ready":
        note = "" if result["reason"] in ("started", "already-running") else f" ({result['reason']}; open manually)"
        print(f"sidecar: ready {result['url']}{note}", flush=True)
    else:
        print(f"sidecar: disabled ({result['reason']}) — research continues chat-only", flush=True)


def main() -> int:
    result = ensure_sidecar()
    announce(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
