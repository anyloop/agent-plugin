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
from sidecar_events import emit, progress_dir, write_pointer  # noqa: E402


PRODUCTION_STAGES = [
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

FAST_DRAFT_STAGES = [
    *PRODUCTION_STAGES[:5],
    {"id": "curation", "label": "Relevance screen", "phases": ["curation"], "kind": "sequential"},
    {"id": "report", "label": "Gap-labeled draft", "phases": ["report"], "kind": "sequential"},
]

MODES = {
    "production-complete": {
        "label": "Production-complete research",
        "target_minutes": "30–45",
        "deliverable": "Validated 20-page report with five analyzed strategies and AdAnt handoff",
        "stages": PRODUCTION_STAGES,
    },
    "fast-draft": {
        "label": "Fast diagnostic draft",
        "target_minutes": "15–25",
        "deliverable": "Source-labeled findings and an explicitly incomplete gap report",
        "stages": FAST_DRAFT_STAGES,
    },
}


def build_plan(mode: str, subject: str = "") -> dict:
    selected = MODES[mode]
    return {
        "version": 1,
        "status": "running",
        "mode": mode,
        "label": selected["label"],
        "subject": subject,
        "target_minutes": selected["target_minutes"],
        "deliverable": selected["deliverable"],
        "started": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    plan["completed"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return write_plan(plan), plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=tuple(MODES), default="production-complete")
    parser.add_argument("--subject", default="", help="product or brand name, when already known")
    parser.add_argument("--complete", action="store_true", help="mark the active workflow complete")
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
