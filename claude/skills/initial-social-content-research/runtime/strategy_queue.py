#!/usr/bin/env python3
"""Run ranked strategy analyses with bounded concurrency and automatic reserves.

The manifest contains primary picks followed by reserves. The queue keeps at
most the configured concurrency active, launches a reserve as soon as a pick
fails, and stops launching once the target can be satisfied by current work.
Every candidate still runs through the shared phase wrapper, so Sidecar logs,
timeouts, and structured acquisition failures remain visible.

Manifest shape::

  {
    "context": "Product and research context",
    "candidates": [
      {
        "id": "1",
        "label": "Analyze comparison Short",
        "url": "https://...",
        "video": "optional/local.mp4",
        "brand": "optional target brand",
        "output": "video-analysis/strategy/pick-1.json"
      }
    ]
  }
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

RUNTIME_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = RUNTIME_DIR.parent.parent.parent
sys.path.insert(0, str(PLUGIN_ROOT / "runtime"))

from sidecar_events import emit  # noqa: E402

CommandFactory = Callable[[dict, float], list[str]]


def _safe_id(value: object, index: int) -> str:
    candidate_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or index)).strip("-")
    return candidate_id or str(index)


def _resolve_path(value: object, base: Path) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def load_candidates(manifest_path: Path) -> tuple[list[dict], str]:
    """Load and normalize candidates relative to the manifest directory."""
    manifest = json.loads(manifest_path.read_text())
    raw_candidates = manifest.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise ValueError("manifest.candidates must be a non-empty array")
    default_context = str(manifest.get("context") or "")
    candidates: list[dict] = []
    seen_ids: set[str] = set()
    for index, raw in enumerate(raw_candidates, start=1):
        if not isinstance(raw, dict):
            raise ValueError(f"candidate {index} must be an object")
        candidate_id = _safe_id(raw.get("id"), index)
        if candidate_id in seen_ids:
            raise ValueError(f"duplicate candidate id: {candidate_id}")
        seen_ids.add(candidate_id)
        output = _resolve_path(raw.get("output"), manifest_path.parent)
        video = _resolve_path(raw.get("video"), manifest_path.parent)
        work_dir = _resolve_path(raw.get("work_dir"), manifest_path.parent)
        url = str(raw.get("url") or "").strip()
        if output is None:
            raise ValueError(f"candidate {candidate_id} requires output")
        if not url and video is None:
            raise ValueError(f"candidate {candidate_id} requires url or video")
        candidates.append(
            {
                **raw,
                "id": candidate_id,
                "label": str(raw.get("label") or f"Analyze strategy pick {candidate_id}"),
                "url": url,
                "video_path": video,
                "output_path": output,
                "work_dir_path": work_dir,
                "context": str(raw.get("context") or default_context),
            }
        )
    return candidates, default_context


def successful_output(path: Path) -> bool:
    try:
        return json.loads(path.read_text()).get("status") == "ok"
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def output_failure(path: Path) -> tuple[str, str]:
    try:
        result = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return "missing_output", "analysis did not produce structured output"
    return (
        str(result.get("status") or "failed"),
        str(result.get("error") or "analysis did not complete"),
    )


def candidate_command(candidate: dict, timeout_seconds: float) -> list[str]:
    """Build one wrapped analysis command without using a shell."""
    analysis_runtime = PLUGIN_ROOT / "skills" / "trend-video-understanding" / "runtime"
    analysis = analysis_runtime / "understand_video.py"
    command = [
        "uv",
        "run",
        "--project",
        str(analysis_runtime),
        str(analysis),
    ]
    if candidate["url"]:
        command.extend(["--url", candidate["url"]])
    if candidate["video_path"] is not None:
        command.extend(["--video", str(candidate["video_path"])])
    command.extend(["--output", str(candidate["output_path"])])
    for key, flag in (
        ("context", "--context"),
        ("brand", "--brand"),
        ("model", "--model"),
        ("cookies_from_browser", "--cookies-from-browser"),
    ):
        value = candidate.get(key)
        if value:
            command.extend([flag, str(value)])
    if candidate["work_dir_path"] is not None:
        command.extend(["--work-dir", str(candidate["work_dir_path"])])
    if candidate.get("keep_video"):
        command.append("--keep-video")
    if candidate.get("download_timeout") is not None:
        command.extend(["--download-timeout", str(candidate["download_timeout"])])

    return [
        sys.executable,
        str(PLUGIN_ROOT / "runtime" / "run_phase.py"),
        "run",
        "--phase",
        f"strategy-pick-{candidate['id']}",
        "--skill",
        "trend-video-understanding",
        "--label",
        candidate["label"],
        "--timeout-seconds",
        str(timeout_seconds),
        "--",
        *command,
    ]


def run_queue(
    candidates: list[dict],
    *,
    target_successes: int,
    concurrency: int,
    timeout_seconds: float,
    poll_seconds: float = 0.1,
    command_factory: CommandFactory = candidate_command,
    emit_events: bool = True,
) -> tuple[int, dict]:
    """Run candidates in rank order until the requested successes are available."""
    if target_successes < 1:
        raise ValueError("target_successes must be positive")
    if concurrency < 1:
        raise ValueError("concurrency must be positive")
    if target_successes > len(candidates):
        raise ValueError("target_successes cannot exceed candidate count")

    started = time.monotonic()
    rank = {candidate["id"]: index for index, candidate in enumerate(candidates)}
    pending: list[dict] = []
    successes: list[dict] = []
    failures: list[dict] = []
    for candidate in candidates:
        if successful_output(candidate["output_path"]):
            successes.append(
                {
                    "id": candidate["id"],
                    "output": str(candidate["output_path"]),
                    "cached": True,
                }
            )
        else:
            pending.append(candidate)

    if emit_events:
        emit(
            "strategy",
            "start",
            f"Ranked queue: {target_successes} successes from {len(candidates)} candidates",
            counts={
                "target": target_successes,
                "candidates": len(candidates),
                "concurrency": concurrency,
            },
        )

    active: dict[str, tuple[dict, subprocess.Popen, float]] = {}
    try:
        while len(successes) < target_successes and (pending or active):
            while (
                pending
                and len(active) < concurrency
                and len(successes) + len(active) < target_successes
            ):
                candidate = pending.pop(0)
                candidate["output_path"].parent.mkdir(parents=True, exist_ok=True)
                process = subprocess.Popen(command_factory(candidate, timeout_seconds))
                active[candidate["id"]] = (candidate, process, time.monotonic())

            completed_ids = [
                candidate_id
                for candidate_id, (_, process, _) in active.items()
                if process.poll() is not None
            ]
            if not completed_ids:
                time.sleep(poll_seconds)
                continue

            for candidate_id in completed_ids:
                candidate, process, candidate_started = active.pop(candidate_id)
                duration = round(time.monotonic() - candidate_started, 2)
                if process.returncode == 0 and successful_output(candidate["output_path"]):
                    successes.append(
                        {
                            "id": candidate_id,
                            "output": str(candidate["output_path"]),
                            "cached": False,
                            "duration_seconds": duration,
                        }
                    )
                else:
                    status, error = output_failure(candidate["output_path"])
                    failures.append(
                        {
                            "id": candidate_id,
                            "output": str(candidate["output_path"]),
                            "exit": process.returncode,
                            "status": status,
                            "error": error,
                            "duration_seconds": duration,
                        }
                    )
                if emit_events:
                    emit(
                        "strategy",
                        "progress",
                        f"{len(successes)}/{target_successes} analyses ready",
                        counts={
                            "succeeded": len(successes),
                            "failed": len(failures),
                            "active": len(active),
                            "remaining": len(pending),
                        },
                        next_step=(
                            "Promote the next ranked reserve immediately"
                            if failures and pending
                            else None
                        ),
                    )
    except KeyboardInterrupt:
        for _, process, _ in active.values():
            process.terminate()
        raise

    duration = round(time.monotonic() - started, 2)
    complete = len(successes) >= target_successes
    successes.sort(key=lambda item: rank[item["id"]])
    summary = {
        "status": "ok" if complete else "insufficient",
        "target_successes": target_successes,
        "successes": successes[:target_successes],
        "failures": failures,
        "not_started": [candidate["id"] for candidate in pending],
        "duration_seconds": duration,
    }
    if emit_events:
        emit(
            "strategy",
            "done" if complete else "error",
            (
                f"{target_successes} strategy analyses ready in {duration:g}s"
                if complete
                else f"Only {len(successes)}/{target_successes} strategy analyses succeeded"
            ),
            counts={
                "succeeded": len(successes),
                "failed": len(failures),
                "duration_seconds": duration,
            },
        )
    return (0 if complete else 2), summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--target-successes", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("-o", "--output", type=Path, help="optional queue summary JSON")
    args = parser.parse_args(argv)
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")

    try:
        candidates, _ = load_candidates(args.manifest.resolve())
        exit_code, summary = run_queue(
            candidates,
            target_successes=args.target_successes,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        parser.error(str(error))

    rendered = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
