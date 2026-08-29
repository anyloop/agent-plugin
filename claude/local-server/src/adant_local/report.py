"""MCP wrapper for report manifest, presigned upload, and save payload work."""

from __future__ import annotations

import importlib.util
import json
import tempfile
from argparse import Namespace
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from adant_local import api, phases


@lru_cache(maxsize=1)
def _handoff_module() -> ModuleType:
    source = (
        phases.skills_root()
        / "social-content-research-report"
        / "runtime"
        / "handoff.py"
    )
    spec = importlib.util.spec_from_file_location("adant_report_handoff", source)
    if spec is None or spec.loader is None:
        raise api.ApiError("missing-prereq", "report handoff module is unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _required_string(params: dict[str, Any], key: str) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value.strip():
        raise api.ApiError("phase-failed", f"report {key} must be a non-empty string")
    return value


def _required_object(params: dict[str, Any], key: str) -> dict[str, Any]:
    value = params.get(key)
    if not isinstance(value, dict):
        raise api.ApiError("phase-failed", f"report {key} must be an object")
    return value


def _optional_string(params: dict[str, Any], key: str) -> str | None:
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise api.ApiError("phase-failed", f"report {key} must be a non-empty string")
    return value


def report_manifest(params: dict[str, Any]) -> dict:
    handoff = _handoff_module()
    return handoff.cmd_manifest(
        Namespace(
            data=_required_string(params, "data"),
            pdf=params.get("pdf"),
            html=params.get("html"),
            audit=params.get("audit"),
        )
    )


def _with_json_files(values: dict[str, dict], operation) -> dict:
    with tempfile.TemporaryDirectory(prefix="adant-report-") as temp:
        root = Path(temp)
        paths: dict[str, str] = {}
        for name, value in values.items():
            path = root / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = str(path)
        return operation(paths)


def report_upload(params: dict[str, Any]) -> dict:
    handoff = _handoff_module()
    values = {
        "manifest": _required_object(params, "manifest"),
        "slots": _required_object(params, "slots"),
    }
    return _with_json_files(
        values,
        lambda paths: handoff.cmd_upload(
            Namespace(manifest=paths["manifest"], slots=paths["slots"])
        ),
    )


def report_payload(params: dict[str, Any]) -> dict:
    handoff = _handoff_module()
    values = {
        "manifest": _required_object(params, "manifest"),
        "completed": _required_object(params, "completed"),
    }
    uploads = params.get("uploads")
    if uploads is not None:
        values["uploads"] = _required_object(params, "uploads")

    source = _optional_string(params, "source")
    if source not in {None, "chatgpt", "codex", "claude"}:
        raise api.ApiError(
            "phase-failed",
            "report source must be chatgpt, codex, or claude",
        )
    report_id = _optional_string(params, "report_id")

    def build(paths: dict[str, str]) -> dict:
        return handoff.cmd_payload(
            Namespace(
                data=_required_string(params, "data"),
                manifest=paths["manifest"],
                completed=paths["completed"],
                uploads=paths.get("uploads"),
                report_id=report_id,
                source=source,
            )
        )

    return _with_json_files(values, build)


def run_report_local(action: str, params: dict[str, Any]) -> dict:
    if action == "manifest":
        return report_manifest(params)
    if action == "upload":
        return report_upload(params)
    if action == "payload":
        return report_payload(params)
    raise api.ApiError(
        "phase-failed",
        f"unknown report action: {action}",
        "use manifest, upload, or payload",
    )


def register_report_tool(mcp) -> None:
    @mcp.tool
    def report_local(action: str, params: dict[str, Any]) -> dict:
        """Prepare a report upload manifest, PUT files into remote presigned
        slots, or assemble the final product-report save payload."""
        try:
            return run_report_local(action, params)
        except api.ApiError as exc:
            return exc.as_error()
        except (OSError, TypeError, ValueError) as exc:
            return api.ApiError("phase-failed", str(exc)).as_error()
