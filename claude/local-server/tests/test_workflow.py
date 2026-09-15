"""Workflow plan, budget gate, and widget-session tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from adant_local import events, workflow


@pytest.fixture
def isolated_workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("ADANT_SOCIAL_DATA_DIR", str(tmp_path / ".runtime"))
    monkeypatch.setenv("HOME", str(tmp_path))
    return tmp_path


def test_workflow_start_persists_plan_and_widget_session(isolated_workspace):
    workspace = isolated_workspace / "research"
    result = workflow.run(
        "start",
        mode="fast-draft",
        subject="Nimbus",
        workspace=str(workspace),
    )
    plan = result["workflow"]
    assert plan["mode"] == "fast-draft"
    assert plan["subject"] == "Nimbus"
    assert plan["target_seconds"] == 25 * 60
    assert "strategy" not in {stage["id"] for stage in plan["stages"]}

    snapshot = events.snapshot()
    assert snapshot["workflow"]["id"] == plan["id"]
    assert snapshot["widgetSessionId"] == plan["id"]
    assert snapshot["events"][-1]["workflow"]["id"] == plan["id"]


def test_stage_gate_blocks_new_batches_after_budget(isolated_workspace):
    workspace = isolated_workspace / "research"
    workflow.run("start", workspace=str(workspace))
    workflow.run("stage_start", stage="discovery")
    plan = workflow.read()
    stage = next(item for item in plan["stages"] if item["id"] == "discovery")
    stage["started"] = (
        datetime.now(timezone.utc) - timedelta(seconds=stage["budget_seconds"] + 5)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    path = events.progress_dir() / "workflow.json"
    path.write_text(json.dumps(plan))

    result = workflow.run("stage_check", stage="discovery")
    assert result["budgetGate"]["exhausted"] is True
    assert "stage" in result["budgetGate"]["exhausted_by"]
    assert events.snapshot()["events"][-1]["risk"].startswith("No new batch")


def test_workflow_complete_freezes_completion(isolated_workspace):
    workspace = isolated_workspace / "research"
    workflow.run("start", workspace=str(workspace))
    completed = workflow.run("complete")["workflow"]
    assert completed["status"] == "complete"
    assert completed["completed"].endswith("Z")


def test_collect_is_its_own_stage_ahead_of_browser_gap_fill(isolated_workspace):
    plan = workflow.run(
        "start",
        mode="production-complete",
        subject="Nimbus",
        workspace=str(isolated_workspace / "research"),
    )["workflow"]
    ids = [stage["id"] for stage in plan["stages"]]
    # Remote collection costs the user nothing to install and answers in
    # seconds; browser gap fill costs a Chrome install, a logged-in account
    # and minutes. Folding them into one stage told every user to expect the
    # expensive one.
    assert ids.index("collect") < ids.index("discovery")
    stages = {stage["id"]: stage for stage in plan["stages"]}
    assert stages["collect"]["kind"] == "remote"
    assert stages["discovery"]["kind"] == "conditional"
    # The budgets partition the mode target rather than adding to it.
    assert sum(stage["budget_seconds"] for stage in plan["stages"]) == plan[
        "target_seconds"
    ]


def test_remote_stage_reports_itself_as_a_phase(isolated_workspace):
    workflow.run(
        "start",
        mode="production-complete",
        subject="Nimbus",
        workspace=str(isolated_workspace / "research"),
    )
    workflow.run("stage_start", stage="collect")
    workflow.run("stage_complete", stage="collect")
    phases = [
        (event["phase"], event["status"])
        for event in events.snapshot()["events"]
        if event["phase"] == "collect"
    ]
    # The progress card derives stage state from phase events, and a remote
    # stage has no local process to emit any — so without this the step that
    # actually found the videos is the one step the card never shows.
    assert ("collect", "start") in phases
    assert ("collect", "done") in phases


def test_a_local_stage_does_not_forge_a_phase_event(isolated_workspace):
    workflow.run(
        "start",
        mode="production-complete",
        subject="Nimbus",
        workspace=str(isolated_workspace / "research"),
    )
    workflow.run("stage_start", stage="discovery")
    assert not [
        event
        for event in events.snapshot()["events"]
        if event["phase"].startswith("platform-")
    ]
