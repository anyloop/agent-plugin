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
