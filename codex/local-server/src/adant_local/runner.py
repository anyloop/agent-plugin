"""In-server research job supervision (v1 run_phase semantics, no wrapper).

Jobs are child processes supervised by threads inside adant-local: stdout is
pumped to a per-phase log and throttled onto the event bus, job records live
in progress/jobs/<phase>.json (v1 format, so the panel and research_status
share one source of truth), and a dead pid is flagged as failed.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from adant_local import events

PROGRESS_THROTTLE_SECONDS = 2.0
DEFAULT_TIMEOUT_SECONDS = 600
PHASE_TIMEOUTS = (
    ("platform-meta-ads", 480),
    ("platform-instagram", 720),
    ("platform-tiktok", 720),
    ("platform-youtube", 480),
    ("product-profile", 180),
    ("competitors", 300),
    ("keywords", 120),
    ("curation", 360),
    ("strategy", 300),
    ("report", 300),
)
_active_jobs: set[tuple[str, str]] = set()
_active_jobs_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_progress(progress_dir: Path | None) -> Path:
    """A job binds its progress directory once, at start.

    Resolving lazily from the environment would let a later research_run
    against another workspace redirect this job's terminal record.
    """
    return progress_dir if progress_dir is not None else events.progress_dir()


def _jobs_dir(progress_dir: Path | None = None) -> Path:
    return _resolve_progress(progress_dir) / "jobs"


def _job_key(phase: str, progress_dir: Path | None) -> tuple[str, str]:
    return (str(_resolve_progress(progress_dir).resolve()), phase)


def _write_job(phase: str, record: dict, progress_dir: Path | None = None) -> None:
    try:
        jobs = _jobs_dir(progress_dir)
        jobs.mkdir(parents=True, exist_ok=True)
        path = jobs / f"{phase}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        tmp.replace(path)
    except Exception:  # noqa: BLE001 - bookkeeping must not kill the job
        pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _phase_timeout(phase: str) -> int:
    for prefix, seconds in PHASE_TIMEOUTS:
        if phase == prefix or phase.startswith(prefix + "-"):
            return seconds
    return DEFAULT_TIMEOUT_SECONDS


def _stop_after_timeout(
    process: subprocess.Popen, record: dict, timeout_s: int
) -> None:
    try:
        process.wait(timeout=timeout_s)
        return
    except subprocess.TimeoutExpired:
        record["timed_out"] = True
        record["timeout_seconds"] = timeout_s
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass


def _supervise(
    phase: str,
    process: subprocess.Popen,
    record: dict,
    log_path: Path,
    progress_dir: Path | None = None,
    artifact: str | None = None,
    expected_exit_codes: frozenset[int] = frozenset(),
) -> None:
    started = time.monotonic()
    last_emit = 0.0
    last_line = ""
    try:
        log_file = open(log_path, "a", encoding="utf-8")
    except OSError:
        log_file = None
    assert process.stdout is not None
    for line in process.stdout:
        if log_file:
            log_file.write(line)
            log_file.flush()
        stripped = line.strip()
        if stripped:
            last_line = stripped
            now = time.monotonic()
            if now - last_emit >= PROGRESS_THROTTLE_SECONDS:
                last_emit = now
                events.emit(phase, "progress", stripped[:300])
    exit_code = process.wait()
    duration = int(time.monotonic() - started)
    timed_out = record.get("timed_out") is True
    normalized_exit = 124 if timed_out else exit_code
    expected_exit = not timed_out and normalized_exit in expected_exit_codes
    record.update(
        status="done"
        if normalized_exit == 0
        else "warning"
        if expected_exit
        else "failed",
        ended=_now(),
        exit=normalized_exit,
        duration_seconds=duration,
    )
    if expected_exit:
        record["expected_exit"] = True
    _write_job(phase, record, progress_dir)
    if normalized_exit == 0:
        events.emit(
            phase,
            "done",
            f"completed in {duration}s",
            counts={"duration_seconds": duration},
            artifact=artifact,
            artifact_label=Path(artifact).name if artifact else None,
        )
    elif timed_out:
        events.emit(
            phase,
            "error",
            f"timed out after {record['timeout_seconds']}s",
            counts={"exit": 124, "timeout_seconds": record["timeout_seconds"]},
        )
    elif expected_exit:
        events.emit(
            phase,
            "warning",
            f"fallback exhausted (exit {normalized_exit}): {last_line[:200]}",
            counts={"exit": normalized_exit, "duration_seconds": duration},
        )
    else:
        events.emit(
            phase,
            "error",
            f"exit {normalized_exit}: {last_line[:200]}",
            counts={"exit": normalized_exit},
        )
    if log_file:
        log_file.close()
    with _active_jobs_lock:
        _active_jobs.discard(_job_key(phase, progress_dir))


def start_job(
    phase: str,
    argv: list[str],
    label: str = "",
    progress_dir: Path | None = None,
    timeout_s: int | None = None,
    artifact: str | None = None,
    expected_exit_codes: frozenset[int] = frozenset(),
) -> dict:
    logs_dir = _resolve_progress(progress_dir) / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / f"{phase}.log"
    events.emit(phase, "start", label or phase)
    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
            start_new_session=True,
        )
    except FileNotFoundError:
        record = {
            "phase": phase,
            "status": "failed",
            "exit": 127,
            "started": _now(),
            "ended": _now(),
            "log": str(log_path),
            "error": f"command not found: {argv[0]}",
        }
        _write_job(phase, record, progress_dir)
        events.emit(phase, "error", record["error"])
        return record
    record = {
        "phase": phase,
        "status": "running",
        "pid": process.pid,
        "started": _now(),
        "log": str(log_path),
        "timeout_seconds": timeout_s or _phase_timeout(phase),
    }
    if artifact:
        record["artifact"] = artifact
    if expected_exit_codes:
        record["expected_exit_codes"] = sorted(expected_exit_codes)
    _write_job(phase, record, progress_dir)
    with _active_jobs_lock:
        _active_jobs.add(_job_key(phase, progress_dir))
    threading.Thread(
        target=_stop_after_timeout,
        args=(process, record, record["timeout_seconds"]),
        daemon=True,
    ).start()
    threading.Thread(
        target=_supervise,
        args=(
            phase,
            process,
            record,
            log_path,
            progress_dir,
            artifact,
            expected_exit_codes,
        ),
        daemon=True,
    ).start()
    return record


def job_record(phase: str, progress_dir: Path | None = None) -> dict | None:
    """Read one job's current record (used by the sequential chain)."""
    try:
        return json.loads((_jobs_dir(progress_dir) / f"{phase}.json").read_text())
    except (OSError, json.JSONDecodeError):
        return None


def jobs_status(progress_dir: Path | None = None) -> list[dict]:
    jobs: list[dict] = []
    jobs_dir = _jobs_dir(progress_dir)
    if not jobs_dir.is_dir():
        return jobs
    for path in sorted(jobs_dir.glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        if (
            record.get("status") == "running"
            and record.get("pid")
            and not _pid_alive(int(record["pid"]))
        ):
            with _active_jobs_lock:
                supervised = _job_key(record["phase"], progress_dir) in _active_jobs
            if supervised:
                jobs.append(record)
                continue
            record.update(
                status="failed", ended=_now(), exit=-1, error="process disappeared"
            )
            _write_job(record["phase"], record, progress_dir)
            events.emit(record["phase"], "error", "process disappeared")
        jobs.append(record)
    return jobs


def wait_all(
    timeout_s: int, poll_s: float = 1.0, progress_dir: Path | None = None
) -> list[dict]:
    deadline = time.monotonic() + timeout_s
    while True:
        jobs = jobs_status(progress_dir)
        if (
            not any(j.get("status") == "running" for j in jobs)
            or time.monotonic() > deadline
        ):
            return jobs
        time.sleep(poll_s)
