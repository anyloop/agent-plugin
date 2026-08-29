"""Report-local MCP seam tests."""

import pytest

from adant_local import api, report


def test_manifest_and_payload_use_in_process_handoff(tmp_path):
    data = tmp_path / "report.json"
    data.write_text('{"platforms":{},"meta_ads":{},"strategies":{"items":[]}}')

    manifest = report.report_manifest({"data": str(data)})
    assert manifest == {"files": [], "entries": [], "missing": []}

    payload = report.report_payload(
        {
            "data": str(data),
            "manifest": manifest,
            "completed": {"files": []},
            "source": "codex",
        }
    )
    assert payload["payload"]["assets"] == []
    assert payload["payload"]["source"] == "codex"


def test_upload_passes_structured_objects_to_handoff(monkeypatch):
    seen = {}

    class Handoff:
        @staticmethod
        def cmd_upload(args):
            seen["manifest"] = args.manifest
            seen["slots"] = args.slots
            return {"uploads": [{"uploadId": "up-1"}], "failed": []}

    monkeypatch.setattr(report, "_handoff_module", lambda: Handoff())
    result = report.report_upload(
        {"manifest": {"entries": []}, "slots": {"uploads": []}}
    )
    assert result["uploads"][0]["uploadId"] == "up-1"
    assert seen["manifest"].endswith("manifest.json")
    assert seen["slots"].endswith("slots.json")


def test_payload_rejects_legacy_cli_source(tmp_path):
    data = tmp_path / "report.json"
    data.write_text("{}")

    with pytest.raises(api.ApiError, match="source must be"):
        report.report_payload(
            {
                "data": str(data),
                "manifest": {},
                "completed": {},
                "source": "cli",
            }
        )
