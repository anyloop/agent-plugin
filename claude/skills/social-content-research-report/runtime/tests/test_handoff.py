import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import handoff  # noqa: E402


def _report(tmp: Path) -> Path:
    (tmp / "thumbnails").mkdir()
    (tmp / "thumbnails" / "tiktok-1.jpg").write_bytes(b"x" * 10)
    (tmp / "thumbnails" / "tiktok-2.jpg").write_bytes(b"y" * 20)
    data = {
        "cover": {"clientName": "Acme"},
        "platforms": {
            "tiktok": {
                "brand_videos": [{"url": "u1", "thumb": "thumbnails/tiktok-1.jpg"}],
                "creator_videos": [{"url": "u2", "thumb": "./thumbnails/tiktok-2.jpg"}],
            }
        },
        "meta_ads": {"ads": [{"advertiser": "A", "thumb": "thumbnails/ad-missing.jpg"}]},
        "strategies": {
            "items": [
                {
                    "title": "S1",
                    "url": "https://x/1",
                    "thumb": "thumbnails/tiktok-1.jpg",
                    "avatar": "UGC — a",
                    "keep": "k",
                    "change": "c",
                    "overlays": ["o1", "o2"],
                }
            ]
        },
        "connect": {"aboutAdantCopy": "drop me"},
    }
    path = tmp / "report_data.json"
    path.write_text(json.dumps(data))
    (tmp / "deck.pdf").write_bytes(b"%PDF")
    return path


def test_manifest_lists_each_thumbnail_once_and_reports_missing(tmp_path: Path) -> None:
    data = _report(tmp_path)
    result = handoff.cmd_manifest(
        SimpleNamespace(data=str(data), pdf=str(tmp_path / "deck.pdf"), html=None, audit=None)
    )
    names = [f["filename"] for f in result["files"]]
    assert names == ["tiktok-1.jpg", "tiktok-2.jpg", "deck.pdf"]
    assert result["entries"][1]["path"] == "thumbnails/tiktok-2.jpg"
    assert result["files"][0] == {
        "filename": "tiktok-1.jpg",
        "contentType": "image/jpeg",
        "sizeBytes": 10,
    }
    assert result["missing"] == ["thumbnails/ad-missing.jpg"]


def test_payload_maps_uploads_fills_messages_and_drops_connect(tmp_path: Path) -> None:
    data = _report(tmp_path)
    manifest = handoff.cmd_manifest(
        SimpleNamespace(data=str(data), pdf=str(tmp_path / "deck.pdf"), html=None, audit=None)
    )
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    completed = {
        "files": [
            {"uploadId": "f1", "file": {"filename": "tiktok-1.jpg"}},
            {"uploadId": "f2", "error": "size mismatch"},
            {"uploadId": "fpdf", "file": {"filename": "deck.pdf"}},
        ]
    }
    (tmp_path / "completed.json").write_text(json.dumps(completed))
    result = handoff.cmd_payload(
        SimpleNamespace(
            data=str(data),
            manifest=str(tmp_path / "manifest.json"),
            completed=str(tmp_path / "completed.json"),
            uploads=None,
            report_id="rp_1",
            source="chatgpt",
        )
    )
    payload = result["payload"]
    assert payload["assets"] == [{"path": "thumbnails/tiktok-1.jpg", "uploadId": "f1"}]
    assert payload["pdfUploadId"] == "fpdf"
    assert payload["reportId"] == "rp_1"
    assert payload["source"] == "chatgpt"
    assert "connect" not in payload["data"]
    assert payload["data"]["strategies"]["items"][0]["message"] == (
        "analyze https://x/1\n\nAvatar: UGC — a\n\nKeep: k\n\nChange: c\n\nOverlay:\no1\no2"
    )
    assert any("tiktok-2.jpg" in n for n in result["notes"])
