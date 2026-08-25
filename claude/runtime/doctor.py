"""One-shot preflight for AdAnt social research: every prerequisite, one pass.

Checks Python, Node.js/npx, uv, Google Chrome, yt-dlp, AdAnt CLI
authentication, and the TikTok/Instagram platform sessions in a single run so
the agent can report every missing item in ONE consolidated message (with fix
commands) instead of failing serially mid-workflow.

    python3 runtime/doctor.py            # human summary
    python3 runtime/doctor.py --json     # machine-readable
    python3 runtime/doctor.py --skip-sessions   # skip the slow login checks
    python3 runtime/doctor.py --skip-auth       # offline / test runs

Exit code 0 when everything required passed, 1 otherwise. Results are also
emitted to the Sidecar event bus (phase "doctor"). This script only reads
state; it never opens windows and never triggers a login flow.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_bootstrap import announce, ensure_sidecar  # noqa: E402
from sidecar_events import emit  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
ADANT_CLI = ["npx", "--yes", "@anyloop/adant-cli"]
AUTH_ERROR_MARKERS = (
    "http 401",
    "status: 401",
    "not authenticated",
    "authentication required",
    "not logged in",
    "unauthorized",
)
SESSION_SKILLS = {
    "tiktok": "browse-tiktok-research",
    "instagram": "browse-instagram-reels",
}


def _run(command: list[str], timeout: int) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return result.returncode, (result.stdout + "\n" + result.stderr).strip()


def check_python() -> dict:
    ok = sys.version_info >= (3, 11)
    return {
        "name": "python",
        "ok": ok,
        "detail": platform.python_version(),
        "fix": None if ok else "Install Python 3.11+ (https://www.python.org/downloads/)",
    }


def check_node() -> dict:
    code, out = _run(["node", "--version"], 15)
    match = re.match(r"v(\d+)", out)
    ok = code == 0 and match is not None and int(match.group(1)) >= 18
    detail = out.splitlines()[0] if out else "not found"
    if ok and shutil.which("npx") is None:
        ok, detail = False, f"{detail} (npx missing)"
    return {
        "name": "node",
        "ok": ok,
        "detail": detail,
        "fix": None if ok else "Install Node.js 18+ (https://nodejs.org)",
    }


def check_uv() -> dict:
    code, out = _run(["uv", "--version"], 15)
    ok = code == 0
    return {
        "name": "uv",
        "ok": ok,
        "detail": out.splitlines()[0] if out else "not found",
        "fix": None if ok else "curl -LsSf https://astral.sh/uv/install.sh | sh",
    }


def check_chrome() -> dict:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome"),
        shutil.which("google-chrome-stable"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    ]
    found = next((c for c in candidates if c and Path(c).exists()), None)
    return {
        "name": "chrome",
        "ok": found is not None,
        "detail": found or "not found",
        "fix": None if found else "Install Google Chrome (https://www.google.com/chrome/)",
    }


def check_ytdlp() -> dict:
    found = shutil.which("yt-dlp")
    return {
        "name": "yt-dlp",
        "ok": found is not None,
        "detail": found or "not found",
        "fix": None if found else "Install yt-dlp (needed only for inspiration-video analysis)",
        "required": False,
    }


def check_adant_auth() -> dict:
    code, out = _run([*ADANT_CLI, "credit", "balance"], 180)
    lowered = out.lower()
    if code == 127:
        return {
            "name": "adant-auth",
            "ok": False,
            "detail": "npx not available",
            "fix": "Install Node.js 18+ first",
        }
    if code == 124:
        return {
            "name": "adant-auth",
            "ok": False,
            "detail": "adant-cli timed out",
            "fix": "Retry; a first npx run downloads the CLI",
        }
    if code != 0 or any(marker in lowered for marker in AUTH_ERROR_MARKERS):
        return {
            "name": "adant-auth",
            "ok": False,
            "detail": "not authenticated",
            "fix": "npx --yes @anyloop/adant-cli auth login",
        }
    summary = next((line for line in out.splitlines() if line.strip()), "authenticated")
    return {"name": "adant-auth", "ok": True, "detail": summary[:120], "fix": None}


def check_session(platform_name: str) -> dict:
    skill = SESSION_SKILLS[platform_name]
    runtime = PLUGIN_ROOT / "skills" / skill / "runtime"
    name = f"{platform_name}-session"
    if not runtime.is_dir():
        return {
            "name": name,
            "ok": None,
            "detail": f"skill runtime not found under {runtime}",
            "fix": None,
            "required": False,
        }
    code, out = _run(
        ["uv", "run", "--project", str(runtime), str(runtime / "browse.py"), "--login-check"],
        240,
    )
    logged_in: bool | None = None
    for line in reversed(out.splitlines()):
        line = line.strip()
        if line.startswith("{") and "logged_in" in line:
            try:
                logged_in = json.loads(line).get("logged_in")
            except json.JSONDecodeError:
                logged_in = None
            break
    if code != 0 and logged_in is None:
        detail = "login check failed to run"
    elif logged_in is None:
        detail = "logged_in: null (cookie store unreadable)"
    else:
        detail = f"logged_in: {str(logged_in).lower()}"
    return {
        "name": name,
        "ok": logged_in,
        "detail": detail,
        "fix": None
        if logged_in
        else f"one muted sign-in window via the {skill} skill's --login (ask the user first)",
        "required": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print machine-readable results")
    parser.add_argument("--skip-auth", action="store_true", help="skip the AdAnt CLI auth check")
    parser.add_argument("--skip-sessions", action="store_true", help="skip TikTok/Instagram session checks")
    args = parser.parse_args(argv)

    sidecar = ensure_sidecar()
    if not args.json:
        announce(sidecar)
    emit("doctor", "start", "preflight checks running", skill="doctor")
    checks = [check_python(), check_node(), check_uv(), check_chrome(), check_ytdlp()]
    if not args.skip_auth:
        checks.append(check_adant_auth())
    if not args.skip_sessions:
        checks.append(check_session("tiktok"))
        checks.append(check_session("instagram"))

    required_failures = [c for c in checks if c.get("required", True) and c["ok"] is not True]
    advisories = [c for c in checks if not c.get("required", True) and c["ok"] is not True]

    for check in checks:
        state = {True: "ok", False: "missing", None: "unknown"}[check["ok"]]
        emit("doctor", "progress", f"{check['name']}: {state} ({check['detail']})", skill="doctor")
    if required_failures:
        emit(
            "doctor",
            "need-user",
            "; ".join(f"{c['name']}: {c['fix'] or c['detail']}" for c in required_failures),
            skill="doctor",
            counts={"missing": len(required_failures)},
        )
    else:
        emit("doctor", "done", "all required checks passed", skill="doctor")

    if args.json:
        print(
            json.dumps(
                {"checks": checks, "ok": not required_failures, "sidecar": sidecar},
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        for check in checks:
            mark = {True: "PASS", False: "FAIL", None: "WARN"}[check["ok"]]
            print(f"[{mark}] {check['name']}: {check['detail']}")
            if check["ok"] is not True and check["fix"]:
                print(f"       fix: {check['fix']}")
        print()
        if required_failures:
            print(f"doctor: {len(required_failures)} required item(s) missing — "
                  "report them to the user in ONE message with the fix commands above.")
        elif advisories:
            print("doctor: required checks passed; advisories above affect coverage, not viability.")
        else:
            print("doctor: everything ready.")
    return 1 if required_failures else 0


if __name__ == "__main__":
    sys.exit(main())
