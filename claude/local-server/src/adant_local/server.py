"""adant-local: the AdAnt plugin's local MCP server (plugin v2, R1).

One stdio server owns everything that must run on the user's machine:
preflight (doctor), research phase fan-out, platform sessions, local media,
and the live progress panel (MCP Apps widget). Tool contracts are frozen in
docs/design/plugin-v2-r1-schemas.md; errors follow the shared shape
{code, message, fix?} — never a bare traceback.
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastmcp import FastMCP

from adant_local import (
    api,
    artifacts,
    events,
    fallback,
    media,
    phases,
    report,
    runner,
    workflow,
)

UI_MIME = "text/html;profile=mcp-app"
ASSETS_PATH = Path(__file__).resolve().parent / "assets"
WIDGET_MANIFEST = json.loads((ASSETS_PATH / "widget-manifest.json").read_text())
PANEL_FILE = WIDGET_MANIFEST["researchProgress"]["file"]
PANEL_PATH = ASSETS_PATH / PANEL_FILE
UI_URI = f"ui://adant/{PANEL_FILE}"
MEDIA_PANEL_FILE = WIDGET_MANIFEST["mediaPreview"]["file"]
MEDIA_PANEL_PATH = ASSETS_PATH / MEDIA_PANEL_FILE
MEDIA_UI_URI = f"ui://adant/{MEDIA_PANEL_FILE}"

mcp = FastMCP("adant-local", version="2.0.0-r1")


def error(code: str, message: str, fix: str | None = None) -> dict:
    payload: dict = {"error": {"code": code, "message": message}}
    if fix:
        payload["error"]["fix"] = fix
    return payload


def plugin_data_dir() -> Path:
    return api.data_dir()


# ---------- panel ----------


@mcp.resource(
    UI_URI,
    mime_type=UI_MIME,
    name="AdAnt research progress",
    meta={
        "ui": {
            "prefersBorder": True,
            "csp": {
                "resourceDomains": [
                    "https://fonts.googleapis.com",
                    "https://fonts.gstatic.com",
                ]
            },
        }
    },
)
def panel_resource() -> str:
    return PANEL_PATH.read_text(encoding="utf-8")


@mcp.resource(
    MEDIA_UI_URI,
    mime_type=UI_MIME,
    name="AdAnt media preview",
    meta={
        "ui": {
            "prefersBorder": True,
            "csp": {
                "resourceDomains": [
                    "https://*.r2.cloudflarestorage.com",
                    "https://*.r2.dev",
                    "https://cdn.adant.ai",
                ]
            },
        }
    },
)
def media_panel_resource() -> str:
    return MEDIA_PANEL_PATH.read_text(encoding="utf-8")


def _snapshot_result() -> dict:
    data = events.snapshot()
    running = [j["phase"] for j in data["jobs"] if j.get("status") == "running"]
    failed = [j["phase"] for j in data["jobs"] if j.get("status") == "failed"]
    return {
        "summary": f"{len(data['events'])} events; running: {', '.join(running) or 'none'}; "
        f"failed: {', '.join(failed) or 'none'}",
        "fallbackUrl": fallback.ensure_server(PANEL_PATH),
        **data,
    }


@mcp.tool(meta={"ui": {"resourceUri": UI_URI, "visibility": ["model", "app"]}})
def research_progress_open() -> dict:
    """Open the live AdAnt progress panel in the conversation. Call this
    PROACTIVELY, once, at the start of any AdAnt workflow — init, setup
    checks, or research — without waiting for the user to ask; the panel
    then updates itself."""
    return _snapshot_result()


@mcp.tool(meta={"ui": {"visibility": ["model", "app"]}})
def research_progress_snapshot() -> dict:
    """Current research progress snapshot (recent events and background
    jobs) from the local event bus; polled by the panel."""
    return _snapshot_result()


@mcp.tool(meta={"ui": {"visibility": ["app"]}})
def research_artifact_read(path: str) -> dict:
    """Read a file produced by the research run for panel preview. Only
    paths inside the active research workspace are allowed."""
    try:
        return artifacts.read(path)
    except api.ApiError as exc:
        return exc.as_error()


# ---------- doctor ----------


def _run(command: list[str], timeout: int) -> tuple[int, str]:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, errors="replace", timeout=timeout
        )
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    return result.returncode, (result.stdout + "\n" + result.stderr).strip()


def _check(
    name: str,
    ok: bool | None,
    detail: str,
    fix: str | None = None,
    required: bool = True,
) -> dict:
    return {"name": name, "ok": ok, "detail": detail, "fix": fix, "required": required}


@mcp.tool(meta={"ui": {"resourceUri": UI_URI, "visibility": ["model", "app"]}})
def doctor(sessions: bool = False) -> dict:
    """One-pass local preflight for AdAnt research: Python, uv, Chrome,
    yt-dlp, and local auth. Read-only — never opens windows or starts a
    login flow. Report every missing item to the user in ONE consolidated
    message. sessions=true adds the slow TikTok/Instagram session checks."""
    events.emit("doctor", "start", "preflight checks running", skill="doctor")
    checks = [
        _check(
            "python",
            sys.version_info >= (3, 11),
            platform.python_version(),
            None if sys.version_info >= (3, 11) else "Install Python 3.11+",
        )
    ]
    code, out = _run(["uv", "--version"], 15)
    checks.append(
        _check(
            "uv",
            code == 0,
            out.splitlines()[0] if out else "not found",
            None if code == 0 else "curl -LsSf https://astral.sh/uv/install.sh | sh",
        )
    )
    chrome = next(
        (
            c
            for c in [
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                shutil.which("google-chrome"),
                shutil.which("google-chrome-stable"),
                shutil.which("chromium"),
                shutil.which("chromium-browser"),
            ]
            if c and Path(c).exists()
        ),
        None,
    )
    checks.append(
        _check(
            "chrome",
            chrome is not None,
            chrome or "not found",
            None if chrome else "Install Google Chrome",
        )
    )
    ytdlp = shutil.which("yt-dlp")
    checks.append(
        _check(
            "yt-dlp",
            ytdlp is not None,
            ytdlp or "not found",
            None if ytdlp else "Install yt-dlp (inspiration-video analysis only)",
            required=False,
        )
    )
    token_file = plugin_data_dir() / "local-token.json"
    has_token = token_file.exists()
    checks.append(
        _check(
            "adant-auth",
            has_token or None,
            "local token present" if has_token else "no local token",
            None
            if has_token
            else "run adant_mint_local_token (remote MCP), then auth_bootstrap",
            required=False,
        )
    )
    for check in checks:
        state = {True: "ok", False: "missing", None: "unknown"}[check["ok"]]
        events.emit(
            "doctor",
            "progress",
            f"{check['name']}: {state} ({check['detail']})",
            skill="doctor",
        )
    failures = [c for c in checks if c["required"] and c["ok"] is not True]
    if failures:
        events.emit(
            "doctor",
            "need-user",
            "; ".join(f"{c['name']}: {c['fix'] or c['detail']}" for c in failures),
            skill="doctor",
            counts={"missing": len(failures)},
        )
    else:
        events.emit("doctor", "done", "all required checks passed", skill="doctor")
    return {"ok": not failures, "checks": checks}


# ---------- auth ----------


@mcp.tool
def device_identity() -> dict:
    """Return this local plugin install's stable opaque device identity.
    Pass both fields directly to adant_mint_local_token; the id is not an
    account credential and must not be edited or shared across devices."""
    return api.device_identity()


@mcp.tool
def auth_bootstrap(minted_token: str) -> dict:
    """Store a token minted by the remote adant_mint_local_token tool so this
    server can call api.adant.ai directly, then verify it end to end.
    Single sign-on: the user never logs in twice."""
    if not re.fullmatch(r"[A-Za-z0-9._-]{20,512}", minted_token or ""):
        return error(
            "not-authenticated",
            "token has an unexpected shape",
            "re-run adant_mint_local_token and pass its token verbatim",
        )
    data_dir = plugin_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    token_file = data_dir / "local-token.json"
    token_file.write_text(json.dumps({"token": minted_token}))
    token_file.chmod(0o600)
    verified: bool | None
    try:
        verified = api.verify_token(minted_token)
    except api.ApiError as exc:
        if exc.code == "not-authenticated":
            token_file.unlink(missing_ok=True)
            return exc.as_error()
        verified = None  # network trouble — keep the token, verify lazily
    return {"ok": True, "stored": str(token_file), "verified": verified}


# ---------- research ----------


@mcp.tool(meta={"ui": {"resourceUri": UI_URI, "visibility": ["model", "app"]}})
def research_run(
    phase_runs: list[dict[str, Any]],
    workspace: str,
    subject: str | None = None,
    parallel: bool = True,
    mode: str = "production-complete",
) -> dict:
    """Run research phases with parallel fan-out. Each item is
    {"id": <phase id>, "args": {...}}. Phase ids: product-profile,
    competitors, keywords (variant: tiktok|instagram), platform-tiktok,
    platform-instagram, platform-meta-ads, platform-youtube, curation
    (variant: plan|validate), report (variant: build|pdf), strategy.
    Paths in args are workspace-relative. Each item may set timeout_s and a list
    of documented expected_exit_codes. Long-running: returns running jobs
    immediately; follow with research_status(wait=true).
    Progress streams to the panel. Browser phases are limited to one per call
    and strategy phases to two per call. Inference-backed phases need
    auth_bootstrap first (single sign-on)."""
    root = workflow.activate_workspace(workspace)
    if root is None:
        return error(
            "workspace-invalid",
            f"workspace must be an absolute path with an existing parent: {workspace}",
        )
    if not phase_runs:
        return error("phase-failed", "phase_runs is empty")
    try:
        workflow.start(mode, subject or "")
    except api.ApiError as exc:
        return exc.as_error()
    if any(not isinstance(item, dict) for item in phase_runs):
        return error("phase-failed", "every phase run must be an object")
    phase_ids = [str(item.get("id", "")) for item in phase_runs]
    browser_ids = {
        "platform-tiktok",
        "platform-instagram",
        "platform-meta-ads",
        "platform-youtube",
    }
    if sum(phase_id in browser_ids for phase_id in phase_ids) > 1:
        return error(
            "phase-failed",
            "run one social browser phase at a time to bound memory and guarantee cleanup",
        )
    if phase_ids.count("strategy") > 2:
        return error(
            "phase-failed",
            "run at most two strategy analyses at a time; promote reserves as slots finish",
        )
    plan: list[tuple[str, list[str], str | None, int | None, frozenset[int]]] = []
    for item in phase_runs:
        phase_id = str(item.get("id", ""))
        args = item.get("args") or {}
        if not isinstance(args, dict):
            return error("phase-failed", f"{phase_id}: args must be an object")
        timeout_s = item.get("timeout_s")
        if timeout_s is not None and (
            not isinstance(timeout_s, int)
            or isinstance(timeout_s, bool)
            or timeout_s < 1
            or timeout_s > 3600
        ):
            return error(
                "phase-failed",
                f"{phase_id}: timeout_s must be an integer from 1 to 3600",
            )
        raw_expected = item.get("expected_exit_codes") or []
        if not isinstance(raw_expected, list) or any(
            not isinstance(code, int)
            or isinstance(code, bool)
            or code < 1
            or code > 255
            for code in raw_expected
        ):
            return error(
                "phase-failed",
                f"{phase_id}: expected_exit_codes must contain integers from 1 to 255",
            )
        expected_exit_codes = frozenset(raw_expected)
        variant = (args or {}).get("variant")
        try:
            argv = phases.build_argv(phase_id, dict(args), root)
        except KeyError:
            return error("phase-failed", f"unknown phase id: {phase_id}")
        except phases.PhaseArgError as exc:
            return error("phase-failed", f"{phase_id}: {exc}")
        # Variants of one phase run in parallel, so each needs its own job
        # record and log file; the panel already groups "<phase>-<suffix>".
        job_id = f"{phase_id}-{variant}" if variant else phase_id
        output = args.get("output")
        artifact = (
            phases._workspace_path(root, output) if isinstance(output, str) else None
        )
        plan.append((job_id, argv, artifact, timeout_s, expected_exit_codes))
    if subject:
        events.emit(plan[0][0], "progress", f"researching {subject}", subject=subject)
    progress = root / ".runtime" / "progress"
    jobs: list[dict] = []
    if parallel:
        for phase_id, argv, artifact, timeout_s, expected_exit_codes in plan:
            jobs.append(
                runner.start_job(
                    phase_id,
                    argv,
                    progress_dir=progress,
                    timeout_s=timeout_s,
                    artifact=artifact,
                    expected_exit_codes=expected_exit_codes,
                )
            )
    else:

        def chain(items=tuple(plan), progress=progress):
            for phase_id, argv, artifact, timeout_s, expected_exit_codes in items:
                record = runner.start_job(
                    phase_id,
                    argv,
                    progress_dir=progress,
                    timeout_s=timeout_s,
                    artifact=artifact,
                    expected_exit_codes=expected_exit_codes,
                )
                if record.get("status") == "failed":
                    break
                runner.wait_all(timeout_s=3600, progress_dir=progress)
                # A phase that spawned and then exited non-zero must stop the
                # chain too — downstream phases would run on missing inputs.
                final = runner.job_record(phase_id, progress_dir=progress)
                if not final or final.get("status") != "done":
                    events.emit(
                        phase_id,
                        "error",
                        "sequential chain halted: this phase did not succeed",
                    )
                    break

        import threading

        threading.Thread(target=chain, daemon=True).start()
        jobs = [{"phase": pid, "status": "queued"} for pid, _, _, _, _ in plan]
    return {"jobs": jobs}


@mcp.tool
def research_status(wait: bool = False, timeout_s: int = 600) -> dict:
    """Status of research jobs (running/done/failed, exit codes, logs).
    wait=true blocks until no job is running or timeout_s elapses."""
    jobs = runner.wait_all(timeout_s) if wait else runner.jobs_status()
    return {
        "jobs": jobs,
        "running": sum(1 for j in jobs if j.get("status") == "running"),
        "failed": sum(1 for j in jobs if j.get("status") == "failed"),
    }


@mcp.tool
def platform_session(platform: str, action: str = "check") -> dict:
    """Check or open a TikTok/Instagram research session. action="check" is
    read-only; action="open" opens ONE muted foreground sign-in window (at
    most once per platform per workflow — ask the user first)."""
    skill = phases.LOGIN_PLATFORMS.get(platform)
    if skill is None:
        return error(
            "phase-failed",
            f"unknown platform: {platform}",
            "use 'tiktok' or 'instagram'",
        )
    project = phases.skills_root() / skill / "runtime"
    script = str(project / "browse.py")
    if action == "check":
        code, out = _run(
            ["uv", "run", "--project", str(project), script, "--login-check"], 240
        )
        logged_in: bool | None = None
        for line in reversed(out.splitlines()):
            line = line.strip()
            if line.startswith("{") and "logged_in" in line:
                try:
                    logged_in = json.loads(line).get("logged_in")
                except json.JSONDecodeError:
                    pass
                break
        if code != 0 and logged_in is None:
            return error(
                "platform-login-required", f"{platform} login check failed to run"
            )
        return {"logged_in": logged_in, "opened": False}
    if action == "open":
        try:
            subprocess.Popen(
                ["uv", "run", "--project", str(project), script, "--login"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            return error("missing-prereq", "uv is required to open the sign-in window")
        events.emit(
            "doctor",
            "need-user",
            f"{platform} sign-in window opened — sign in, close it, research resumes",
        )
        return {"logged_in": None, "opened": True}
    return error("phase-failed", f"unknown action: {action}", "use 'check' or 'open'")


media.register_media_tool(mcp, MEDIA_UI_URI)
report.register_report_tool(mcp)
workflow.register_workflow_tool(mcp)
fallback.register_fallback_tool(mcp, PANEL_PATH)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
