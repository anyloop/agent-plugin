"""Durable research workflow plans and user-facing time-budget gates."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from adant_local import api, events

STAGE_SPECS = [
    ("setup", "Setup", ["doctor"], "gate"),
    ("product", "Product profile", ["product-profile"], "sequential"),
    ("competitors", "Competitors", ["competitors"], "sequential"),
    ("keywords", "Search plan", ["keywords"], "parallel"),
    (
        "discovery",
        "Platform discovery",
        [
            "platform-tiktok",
            "platform-instagram",
            "platform-meta-ads",
            "platform-youtube",
        ],
        "parallel",
    ),
    (
        "curation",
        "Curation & conditional top-ups",
        ["curation"],
        "conditional",
    ),
    ("strategy", "Video analysis & strategies", ["strategy"], "parallel"),
    ("report", "Report & QA", ["report"], "sequential"),
    ("delivery", "Save to AdAnt", ["delivery"], "sequential"),
]
STAGE_BUDGETS = {
    "production-complete": {
        "setup": 60,
        "product": 180,
        "competitors": 300,
        "keywords": 120,
        "discovery": 720,
        "curation": 360,
        "strategy": 480,
        "report": 300,
        "delivery": 180,
    },
    "fast-draft": {
        "setup": 60,
        "product": 150,
        "competitors": 210,
        "keywords": 120,
        "discovery": 540,
        "curation": 180,
        "report": 180,
    },
}
MODES = {
    "production-complete": {
        "label": "Production-complete research",
        "target_minutes": "30–45",
        "target_seconds": 45 * 60,
        "deliverable": "Validated research report with five primary strategies and AdAnt handoff",
    },
    "fast-draft": {
        "label": "Fast diagnostic draft",
        "target_minutes": "15–25",
        "target_seconds": 25 * 60,
        "deliverable": "Source-labeled findings and an explicitly incomplete gap report",
    },
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _path() -> Path:
    return events.active_progress_dir() / "workflow.json"


def activate_workspace(workspace: str) -> Path | None:
    root = Path(workspace).expanduser()
    if not root.is_absolute() or not root.parent.exists():
        return None
    root.mkdir(parents=True, exist_ok=True)
    os.environ["ADANT_SOCIAL_DATA_DIR"] = str(root / ".runtime")
    events.write_pointer()
    return root


def _write(plan: dict) -> Path:
    directory = events.progress_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "workflow.json"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    temporary.replace(path)
    events.write_pointer()
    return path


def read() -> dict | None:
    try:
        value = json.loads(_path().read_text())
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def build(mode: str, subject: str = "") -> dict:
    selected = MODES.get(mode)
    if selected is None:
        raise api.ApiError("phase-failed", f"unknown workflow mode: {mode}")
    budgets = STAGE_BUDGETS[mode]
    stages = [
        {
            "id": stage_id,
            "label": "Relevance screen"
            if mode == "fast-draft" and stage_id == "curation"
            else "Gap-labeled draft"
            if mode == "fast-draft" and stage_id == "report"
            else label,
            "phases": phases,
            "kind": kind,
            "budget_seconds": budgets[stage_id],
        }
        for stage_id, label, phases, kind in STAGE_SPECS
        if stage_id in budgets
    ]
    return {
        "version": 2,
        "id": uuid4().hex,
        "status": "running",
        "mode": mode,
        "subject": subject,
        "started": _timestamp(),
        "stages": stages,
        **selected,
    }


def start(mode: str, subject: str = "") -> dict:
    current = read()
    if current and current.get("status") == "running" and current.get("mode") == mode:
        return current
    plan = build(mode, subject)
    _write(plan)
    events.emit(
        "workflow",
        "progress",
        f"{plan['label']} · target {plan['target_minutes']} minutes",
        subject=subject or None,
        summary=plan["deliverable"],
        next_step=plan["stages"][0]["label"],
        eta_minutes=plan["target_minutes"],
        extra={"workflow": plan},
    )
    return plan


def update_stage(stage_id: str, action: str) -> dict:
    plan = read()
    if plan is None:
        raise api.ApiError("phase-failed", "no active research workflow")
    stage = next((item for item in plan["stages"] if item["id"] == stage_id), None)
    if stage is None:
        raise api.ApiError("phase-failed", f"unknown workflow stage: {stage_id}")
    now = _now()
    if action == "start":
        stage.setdefault("started", _timestamp(now))
        stage["status"] = "running"
    elif "started" not in stage:
        raise api.ApiError("phase-failed", f"workflow stage has not started: {stage_id}")
    stage_elapsed = max(0, int((now - _parse_timestamp(stage["started"])).total_seconds()))
    total_elapsed = max(0, int((now - _parse_timestamp(plan["started"])).total_seconds()))
    stage_remaining = int(stage["budget_seconds"]) - stage_elapsed
    total_remaining = int(plan["target_seconds"]) - total_elapsed
    exhausted_by = [
        name
        for name, remaining in (("stage", stage_remaining), ("workflow", total_remaining))
        if remaining <= 0
    ]
    if action == "complete":
        stage.update(
            status="complete",
            completed=_timestamp(now),
            elapsed_seconds=stage_elapsed,
        )
    _write(plan)
    result = {
        "stage": stage_id,
        "action": action,
        "elapsed_seconds": stage_elapsed,
        "remaining_seconds": max(0, min(stage_remaining, total_remaining)),
        "workflow_elapsed_seconds": total_elapsed,
        "exhausted": bool(exhausted_by),
        "exhausted_by": exhausted_by,
    }
    events.emit(
        "workflow",
        "progress",
        f"{stage_id} time budget reached"
        if exhausted_by
        else f"{stage_id} stage {action}",
        risk="No new batch should start; curate current evidence or deliver the documented gap."
        if exhausted_by
        else None,
        next_step="Close this stage without another retry loop." if exhausted_by else None,
        extra={"workflow": plan, "budget_gate": result},
    )
    return result


def complete() -> dict:
    plan = read()
    if plan is None:
        raise api.ApiError("phase-failed", "no active research workflow")
    plan.update(status="complete", completed=_timestamp())
    _write(plan)
    events.emit(
        "workflow",
        "done",
        f"{plan['label']} complete",
        summary=plan["deliverable"],
        extra={"workflow": plan},
    )
    return plan


def run(
    action: str,
    mode: str = "production-complete",
    subject: str = "",
    workspace: str | None = None,
    stage: str | None = None,
) -> dict:
    if action == "start":
        if workspace is None or activate_workspace(workspace) is None:
            raise api.ApiError(
                "workspace-invalid",
                "workflow start requires an absolute workspace with an existing parent",
            )
        return {"workflow": start(mode, subject)}
    if action == "complete":
        return {"workflow": complete()}
    if action in {"stage_start", "stage_check", "stage_complete"}:
        if not stage:
            raise api.ApiError("phase-failed", f"{action} requires stage")
        return {
            "workflow": read(),
            "budgetGate": update_stage(stage, action.removeprefix("stage_")),
        }
    raise api.ApiError(
        "phase-failed",
        f"unknown workflow action: {action}",
        "use start, stage_start, stage_check, stage_complete, or complete",
    )


def register_workflow_tool(mcp) -> None:
    @mcp.tool
    def research_workflow(
        action: str,
        mode: str = "production-complete",
        subject: str = "",
        workspace: str | None = None,
        stage: str | None = None,
    ) -> dict:
        """Start or complete a research workflow and enforce stage budgets.
        Use stage_check before starting another discovery or analysis batch."""
        try:
            return run(action, mode, subject, workspace, stage)
        except api.ApiError as exc:
            return exc.as_error()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return api.ApiError("phase-failed", str(exc)).as_error()
