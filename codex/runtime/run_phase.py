"""Run one research phase with Sidecar progress events, optionally detached.

This is the single entry point long research phases go through so that
start/progress/done/error events land on the Sidecar event bus without any
per-runtime instrumentation, and so that independent phases (the four platform
browses) can run in parallel as detached background jobs that survive the end
of a single agent tool call.

Foreground:
    python3 run_phase.py run --phase platform-tiktok --skill browse-tiktok-research \
        -- uv run --project .../runtime .../browse.py "query" -o out.json

Background (parallel fan-out), then wait:
    python3 run_phase.py run --bg --phase platform-tiktok  -- <command...>
    python3 run_phase.py run --bg --phase platform-youtube -- <command...>
    python3 run_phase.py status --wait

Every job writes ``$ADANT_SOCIAL_DATA_DIR/progress/jobs/<phase>.json`` and its
full output to ``progress/logs/<phase>.log``. Exit codes: ``run`` mirrors the
wrapped command; ``status --wait`` exits 0 when every job succeeded, 1 when
any failed, 2 on the hard timeout. ``status --wait --max-wait 45`` also exits
0 after one bounded observation slice while jobs continue, giving the agent a
chance to update the user before checking again.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sidecar_bootstrap import announce, ensure_sidecar  # noqa: E402
from sidecar_events import emit, progress_dir  # noqa: E402

PROGRESS_THROTTLE_SECONDS = 2.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _jobs_dir() -> Path:
    return progress_dir() / "jobs"


def _logs_dir() -> Path:
    return progress_dir() / "logs"


def _write_job(phase: str, record: dict) -> None:
    try:
        _jobs_dir().mkdir(parents=True, exist_ok=True)
        path = _jobs_dir() / f"{phase}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        tmp.replace(path)
    except Exception:  # noqa: BLE001 - bookkeeping must not kill the phase
        pass


def _read_job(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def run_foreground(phase: str, skill: str | None, label: str, command: list[str]) -> int:
    log_path = _logs_dir() / f"{phase}.log"
    try:
        _logs_dir().mkdir(parents=True, exist_ok=True)
        log_file = open(log_path, "a", encoding="utf-8")
    except Exception:  # noqa: BLE001
        log_file = None
    record = {
        "phase": phase,
        "skill": skill,
        "label": label,
        "pid": os.getpid(),
        "command": command,
        "status": "running",
        "started": _now(),
        "log": str(log_path),
    }
    _write_job(phase, record)
    emit(phase, "start", label or " ".join(command[:3]), skill=skill)
    started = time.monotonic()
    last_progress = 0.0
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
        )
    except FileNotFoundError:
        message = f"command not found: {command[0]}"
        print(f"run_phase: {message}", file=sys.stderr)
        record.update(status="failed", ended=_now(), exit=127, error=message)
        _write_job(phase, record)
        emit(phase, "error", message, skill=skill)
        if log_file:
            log_file.close()
        return 127
    assert process.stdout is not None
    last_line = ""
    for line in process.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if log_file:
            log_file.write(line)
            log_file.flush()
        stripped = line.strip()
        if stripped:
            last_line = stripped
            now = time.monotonic()
            if now - last_progress >= PROGRESS_THROTTLE_SECONDS:
                last_progress = now
                emit(phase, "progress", stripped[:300], skill=skill)
    exit_code = process.wait()
    duration = int(time.monotonic() - started)
    record.update(status="done" if exit_code == 0 else "failed", ended=_now(), exit=exit_code, duration_seconds=duration)
    _write_job(phase, record)
    if exit_code == 0:
        emit(phase, "done", f"completed in {duration}s", skill=skill, counts={"duration_seconds": duration})
    else:
        emit(phase, "error", f"exit {exit_code}: {last_line[:200]}", skill=skill, counts={"exit": exit_code})
    if log_file:
        log_file.close()
    return exit_code


def run_background(phase: str, skill: str | None, label: str, command: list[str]) -> int:
    """Re-exec this wrapper in foreground mode, fully detached."""
    _logs_dir().mkdir(parents=True, exist_ok=True)
    log_path = _logs_dir() / f"{phase}.log"
    inner = [sys.executable, str(Path(__file__).resolve()), "run", "--phase", phase]
    if skill:
        inner += ["--skill", skill]
    if label:
        inner += ["--label", label]
    inner += ["--", *command]
    with open(log_path, "a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            inner,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    print(f"run_phase: started phase={phase} pid={process.pid} log={log_path}")
    print("run_phase: check with `run_phase.py status` or wait with `run_phase.py status --wait`")
    return 0


def cmd_status(
    wait: bool,
    interval: float,
    timeout: float,
    max_wait: float,
    phases: list[str] | None,
) -> int:
    deadline = time.monotonic() + timeout if timeout else None
    slice_deadline = time.monotonic() + max_wait if max_wait else None
    while True:
        jobs = []
        jobs_dir = _jobs_dir()
        if jobs_dir.is_dir():
            for path in sorted(jobs_dir.glob("*.json")):
                record = _read_job(path)
                if not record:
                    continue
                if phases and record.get("phase") not in phases:
                    continue
                if record.get("status") == "running" and record.get("pid") and not _pid_alive(int(record["pid"])):
                    record.update(status="failed", ended=_now(), exit=-1, error="process disappeared")
                    _write_job(record["phase"], record)
                    emit(record["phase"], "error", "process disappeared", skill=record.get("skill"))
                jobs.append(record)
        running = [j for j in jobs if j.get("status") == "running"]
        failed = [j for j in jobs if j.get("status") == "failed"]
        for job in jobs:
            detail = f"exit={job.get('exit')}" if "exit" in job else f"pid={job.get('pid')}"
            print(f"phase={job.get('phase')} status={job.get('status')} {detail} log={job.get('log', '')}")
        if not jobs:
            print("run_phase: no jobs recorded")
        if not wait or not running:
            if failed:
                return 1
            return 0
        if deadline and time.monotonic() > deadline:
            print(f"run_phase: timeout with {len(running)} job(s) still running", file=sys.stderr)
            return 2
        if slice_deadline and time.monotonic() >= slice_deadline:
            names = ", ".join(str(job.get("phase")) for job in running)
            print(f"run_phase: still running after {max_wait:g}s: {names}")
            return 0
        time.sleep(interval)
        print("---")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="run one phase command with events")
    run_parser.add_argument("--phase", required=True, help="canonical phase id, e.g. platform-tiktok")
    run_parser.add_argument("--skill", help="skill name emitting the events")
    run_parser.add_argument("--label", default="", help="human-readable label for the start event")
    run_parser.add_argument("--bg", action="store_true", help="detach and return immediately")
    run_parser.add_argument("cmd", nargs=argparse.REMAINDER, help="-- command to execute")

    status_parser = sub.add_parser("status", help="report background jobs")
    status_parser.add_argument("--wait", action="store_true", help="block until no job is running")
    status_parser.add_argument("--interval", type=float, default=10.0)
    status_parser.add_argument("--timeout", type=float, default=0.0, help="seconds; 0 = no timeout")
    status_parser.add_argument(
        "--max-wait",
        type=float,
        default=0.0,
        help="return successfully after this observation slice even when jobs are still running",
    )
    status_parser.add_argument("--phases", help="comma-separated phase filter")

    args = parser.parse_args(argv)
    if args.command == "run":
        command = list(args.cmd)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            parser.error("missing command after --")
        announce(ensure_sidecar())
        if args.bg:
            return run_background(args.phase, args.skill, args.label, command)
        return run_foreground(args.phase, args.skill, args.label, command)
    phases = [p.strip() for p in args.phases.split(",") if p.strip()] if args.phases else None
    return cmd_status(args.wait, args.interval, args.timeout, args.max_wait, phases)


if __name__ == "__main__":
    sys.exit(main())
