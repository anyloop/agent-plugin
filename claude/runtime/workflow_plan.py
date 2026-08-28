"""Publish the selected social-research workflow plan to the Sidecar.

The plan is intentionally small and stable: it tells the user which delivery
contract is active, which stages can fan out, and what remains. Research tools
still own their detailed commands and evidence schemas.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from phase_limits import stage_budget_seconds  # noqa: E402
from sidecar_events import emit, progress_dir, write_pointer  # noqa: E402


_PRODUCTION_STAGES = [
    {"id": "setup", "label": "Setup", "phases": ["doctor"], "kind": "gate"},
    {"id": "product", "label": "Product profile", "phases": ["product-profile"], "kind": "sequential"},
    {"id": "competitors", "label": "Competitors", "phases": ["competitors"], "kind": "sequential"},
    {"id": "keywords", "label": "Search plan", "phases": ["keywords"], "kind": "parallel"},
    {
        "id": "discovery",
        "label": "Platform discovery",
        "phases": ["platform-tiktok", "platform-instagram", "platform-meta-ads", "platform-youtube"],
        "kind": "parallel",
    },
    {"id": "curation", "label": "Curation & conditional top-ups", "phases": ["curation"], "kind": "conditional"},
    {"id": "strategy", "label": "Video analysis & strategies", "phases": ["strategy"], "kind": "parallel"},
    {"id": "report", "label": "Report & QA", "phases": ["report"], "kind": "sequential"},
    {"id": "delivery", "label": "Save to AdAnt", "phases": ["delivery"], "kind": "sequential"},
]

_FAST_DRAFT_STAGES = [
    *_PRODUCTION_STAGES[:5],
    {"id": "curation", "label": "Relevance screen", "phases": ["curation"], "kind": "sequential"},
    {"id": "report", "label": "Gap-labeled draft", "phases": ["report"], "kind": "sequential"},
]


def _with_budgets(mode: str, stages: list[dict]) -> list[dict]:
    return [
        {**stage, "budget_seconds": stage_budget_seconds(mode, stage["id"])}
        for stage in stages
    ]


PRODUCTION_STAGES = _with_budgets("production-complete", _PRODUCTION_STAGES)
FAST_DRAFT_STAGES = _with_budgets("fast-draft", _FAST_DRAFT_STAGES)

MODES = {
    "production-complete": {
        "label": "Production-complete research",
        "target_minutes": "30–45",
        "target_seconds": 45 * 60,
        "deliverable": "Validated 20-page report with five analyzed strategies and AdAnt handoff",
        "stages": PRODUCTION_STAGES,
    },
    "fast-draft": {
        "label": "Fast diagnostic draft",
        "target_minutes": "15–25",
        "target_seconds": 25 * 60,
        "deliverable": "Source-labeled findings and an explicitly incomplete gap report",
        "stages": FAST_DRAFT_STAGES,
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def build_plan(mode: str, subject: str = "") -> dict:
    selected = MODES[mode]
    return {
        "version": 1,
        "status": "running",
        "mode": mode,
        "label": selected["label"],
        "subject": subject,
        "target_minutes": selected["target_minutes"],
        "target_seconds": selected["target_seconds"],
        "deliverable": selected["deliverable"],
        "started": _timestamp(),
        "stages": selected["stages"],
    }


def write_plan(plan: dict) -> Path:
    directory = progress_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "workflow.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    temporary.replace(path)
    write_pointer()
    return path


def complete_plan() -> tuple[Path, dict]:
    path = progress_dir() / "workflow.json"
    plan = json.loads(path.read_text())
    plan["status"] = "complete"
    plan["completed"] = _timestamp()
    return write_plan(plan), plan


def update_stage(stage_id: str, action: str) -> tuple[Path, dict, dict]:
    """Start, inspect, or complete one manual workflow stage.

    Browser work cannot be interrupted by ``run_phase.py``, so the workflow
    calls ``check`` between query batches. A non-zero result means no new work
    should start; the current evidence should be curated or delivered instead.
    """
    path = progress_dir() / "workflow.json"
    plan = json.loads(path.read_text())
    stage = next((item for item in plan["stages"] if item["id"] == stage_id), None)
    if stage is None:
        raise KeyError(f"unknown stage: {stage_id}")

    now = _now()
    if action == "start":
        stage.setdefault("started", _timestamp(now))
        stage["status"] = "running"
    elif "started" not in stage:
        raise KeyError(f"stage has not started: {stage_id}")

    stage_elapsed = max(0, int((now - _parse_timestamp(stage["started"])).total_seconds()))
    total_elapsed = max(0, int((now - _parse_timestamp(plan["started"])).total_seconds()))
    stage_remaining = int(stage["budget_seconds"]) - stage_elapsed
    total_remaining = int(plan["target_seconds"]) - total_elapsed
    exhausted_by = []
    if stage_remaining <= 0:
        exhausted_by.append("stage")
    if total_remaining <= 0:
        exhausted_by.append("workflow")

    if action == "complete":
        stage["status"] = "complete"
        stage["completed"] = _timestamp(now)
        stage["elapsed_seconds"] = stage_elapsed

    result = {
        "stage": stage_id,
        "action": action,
        "elapsed_seconds": stage_elapsed,
        "remaining_seconds": max(0, min(stage_remaining, total_remaining)),
        "workflow_elapsed_seconds": total_elapsed,
        "exhausted": bool(exhausted_by),
        "exhausted_by": exhausted_by,
    }
    if action != "check" or exhausted_by:
        path = write_plan(plan)
    return path, plan, result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=tuple(MODES), default="production-complete")
    parser.add_argument("--subject", default="", help="product or brand name, when already known")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--complete", action="store_true", help="mark the active workflow complete")
    actions.add_argument("--stage-start", metavar="ID", help="start a manual/browser stage timer")
    actions.add_argument("--stage-check", metavar="ID", help="check whether a stage may start more work")
    actions.add_argument("--stage-complete", metavar="ID", help="complete a stage and record its elapsed time")
    args = parser.parse_args(argv)

    if args.complete:
        try:
            path, plan = complete_plan()
        except (OSError, json.JSONDecodeError, KeyError) as error:
            parser.error(f"cannot complete active workflow: {error}")
        emit(
            "workflow",
            "done",
            f"{plan.get('label', 'Research')} complete",
            summary=plan.get("deliverable"),
            extra={"workflow": plan},
        )
        print(json.dumps({"workflow": str(path), **plan}, ensure_ascii=False))
        return 0

    stage_id = args.stage_start or args.stage_check or args.stage_complete
    if stage_id:
        action = "start" if args.stage_start else "check" if args.stage_check else "complete"
        try:
            path, plan, result = update_stage(stage_id, action)
        except (OSError, json.JSONDecodeError, KeyError, ValueError) as error:
            parser.error(f"cannot {action} workflow stage: {error}")
        if result["exhausted"]:
            emit(
                "workflow",
                "progress",
                f"{stage_id} time budget reached",
                risk="No new query or analysis batch should start; curate the current evidence or deliver the documented gap.",
                next_step="Close the current stage without another retry loop.",
                extra={"workflow": plan, "budget_gate": result},
            )
        elif action != "check":
            action_label = "started" if action == "start" else "completed"
            emit(
                "workflow",
                "progress",
                f"{stage_id} stage {action_label}",
                extra={"workflow": plan, "budget_gate": result},
            )
        print(json.dumps({"workflow": str(path), **result}, ensure_ascii=False))
        return 124 if action in ("start", "check") and result["exhausted"] else 0

    plan = build_plan(args.mode, args.subject)
    path = write_plan(plan)
    emit(
        "workflow",
        "progress",
        f"{plan['label']} · target {plan['target_minutes']} minutes",
        subject=args.subject or None,
        extra={
            "workflow": plan,
            "mode": plan["mode"],
            "summary": plan["deliverable"],
            "next": plan["stages"][0]["label"],
            "eta_minutes": plan["target_minutes"],
        },
    )
    print(json.dumps({"workflow": str(path), **plan}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
