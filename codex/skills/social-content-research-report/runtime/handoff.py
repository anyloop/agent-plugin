#!/usr/bin/env python3
"""Hand a finished report to AdAnt Studio.

Three subcommands bracket the MCP calls the agent makes (the agent calls the
tools; this script does the file work around them):

  manifest  --data report_data.json [--pdf deck.pdf] [--html deck.html]
            [--audit curation_audit.json] -o manifest.json
      Lists every thumbnail the report references plus the deck files, as the
      `files` input of `adant_prepare_uploads`.

  upload    --manifest manifest.json --slots slots.json -o uploads.json
      `slots.json` is the `adant_prepare_uploads` result. PUTs each file's
      bytes to its presigned URL and writes the `uploads` input of
      `adant_complete_uploads`.

  payload   --data report_data.json --manifest manifest.json
            --completed completed.json [--report-id rp_…] [--source chatgpt]
            -o save.json
      `completed.json` is the `adant_complete_uploads` result. Writes the
      full `adant_save_product_report` input: report data with every
      strategy's `message` filled in, the asset → uploadId map, and the deck
      upload ids. Files that failed to upload are dropped with a note.

Thumbnail paths are resolved relative to the report_data.json directory,
exactly as the deck builder resolves them.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import ssl
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from strategy_slides import strategy_message  # noqa: E402

DECK_KEYS = {"pdf": "pdfUploadId", "html": "htmlUploadId", "audit": "auditUploadId"}


def _upload_context() -> ssl.SSLContext:
    """Use a portable CA bundle for presigned uploads.

    Python installations on macOS do not always inherit the operating system's
    trusted roots. The report runtime installs certifi, while the fallback keeps
    direct system-Python usage functional when its trust store is configured.
    """
    try:
        import certifi
    except ImportError:
        return ssl.create_default_context()
    return ssl.create_default_context(cafile=certifi.where())


def _thumb_paths(data: dict) -> list[str]:
    """Every distinct `thumb` the deck would render, in document order."""
    seen: list[str] = []

    def add(value: object) -> None:
        if isinstance(value, str) and value and value not in seen:
            seen.append(value)

    for section in (data.get("platforms") or {}).values():
        for key in ("brand_videos", "creator_videos"):
            for video in section.get(key, []) or []:
                add(video.get("thumb"))
    for ad in (data.get("meta_ads") or {}).get("ads", []) or []:
        add(ad.get("thumb"))
    for item in (data.get("strategies") or {}).get("items", []) or []:
        add(item.get("thumb"))
    return seen


def _content_type(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def cmd_manifest(args: argparse.Namespace) -> dict:
    data = json.loads(Path(args.data).read_text())
    base = Path(args.data).resolve().parent
    entries: list[dict] = []
    missing: list[str] = []
    names: set[str] = set()
    for rel in _thumb_paths(data):
        path = (base / rel).resolve()
        if not path.is_file():
            missing.append(rel)
            continue
        filename = path.name
        if filename in names:
            # Two thumbnails sharing a basename would collide in the assets
            # folder; prefix the second with its parent directory.
            filename = f"{path.parent.name}-{path.name}"
        names.add(filename)
        entries.append(
            {
                "kind": "asset",
                "path": rel.removeprefix("./"),
                "filename": filename,
                "contentType": _content_type(path),
                "sizeBytes": path.stat().st_size,
                "local": str(path),
            }
        )
    for kind in ("pdf", "html", "audit"):
        value = getattr(args, kind)
        if not value:
            continue
        path = Path(value).resolve()
        if not path.is_file():
            missing.append(value)
            continue
        entries.append(
            {
                "kind": kind,
                "path": kind,
                "filename": path.name,
                "contentType": _content_type(path),
                "sizeBytes": path.stat().st_size,
                "local": str(path),
            }
        )
    return {
        "files": [
            {k: e[k] for k in ("filename", "contentType", "sizeBytes")} for e in entries
        ],
        "entries": entries,
        "missing": missing,
    }


def cmd_upload(args: argparse.Namespace) -> dict:
    manifest = json.loads(Path(args.manifest).read_text())
    slots = json.loads(Path(args.slots).read_text())
    slot_list = slots.get("uploads") or slots.get("structuredContent", {}).get("uploads") or []
    by_name = {s["filename"]: s for s in slot_list}
    uploads: list[dict] = []
    failed: list[dict] = []
    for entry in manifest["entries"]:
        slot = by_name.get(entry["filename"])
        if not slot:
            failed.append({"filename": entry["filename"], "error": "no upload slot"})
            continue
        body = Path(entry["local"]).read_bytes()
        req = urllib.request.Request(
            slot["uploadUrl"],
            data=body,
            method="PUT",
            headers={"Content-Type": entry["contentType"], "Content-Length": str(len(body))},
        )
        try:
            with urllib.request.urlopen(  # noqa: S310 — presigned URL from our own server
                req, timeout=120, context=_upload_context()
            ) as resp:
                if resp.status >= 300:
                    raise RuntimeError(f"PUT returned {resp.status}")
        except Exception as exc:  # noqa: BLE001 — report and continue
            failed.append({"filename": entry["filename"], "error": str(exc)})
            continue
        uploads.append(
            {
                "uploadId": slot["uploadId"],
                "filename": entry["filename"],
                "contentType": entry["contentType"],
            }
        )
    return {"uploads": uploads, "failed": failed}


def cmd_payload(args: argparse.Namespace) -> dict:
    data = json.loads(Path(args.data).read_text())
    manifest = json.loads(Path(args.manifest).read_text())
    completed = json.loads(Path(args.completed).read_text())
    rows = completed.get("files") or completed.get("structuredContent", {}).get("files") or []
    ok_ids = {r["uploadId"] for r in rows if r.get("file")}
    by_name: dict[str, str] = {}
    slots_by_name = {}
    if args.uploads:
        for u in json.loads(Path(args.uploads).read_text()).get("uploads", []):
            slots_by_name[u["filename"]] = u["uploadId"]
    for r in rows:
        f = r.get("file") or {}
        if f.get("filename"):
            by_name[f["filename"]] = r["uploadId"]
    notes: list[str] = []
    assets: list[dict] = []
    payload: dict = {"data": data, "assets": assets}
    for entry in manifest["entries"]:
        upload_id = by_name.get(entry["filename"]) or slots_by_name.get(entry["filename"])
        if not upload_id or upload_id not in ok_ids:
            notes.append(f"{entry['filename']}: not uploaded — the web will show a placeholder")
            continue
        if entry["kind"] == "asset":
            assets.append({"path": entry["path"], "uploadId": upload_id})
        else:
            payload[DECK_KEYS[entry["kind"]]] = upload_id
    # The brief is the one thing Studio sends verbatim; write it once, here,
    # so the web never has to re-assemble it.
    for item in data.get("strategies", {}).get("items", []):
        item["message"] = strategy_message(item)
    data.pop("connect", None)
    if args.report_id:
        payload["reportId"] = args.report_id
    if args.source:
        payload["source"] = args.source
    return {"payload": payload, "notes": notes}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("manifest")
    m.add_argument("--data", required=True)
    m.add_argument("--pdf")
    m.add_argument("--html")
    m.add_argument("--audit")
    m.add_argument("-o", "--output", required=True)

    u = sub.add_parser("upload")
    u.add_argument("--manifest", required=True)
    u.add_argument("--slots", required=True)
    u.add_argument("-o", "--output", required=True)

    p = sub.add_parser("payload")
    p.add_argument("--data", required=True)
    p.add_argument("--manifest", required=True)
    p.add_argument("--completed", required=True)
    p.add_argument("--uploads", help="upload.json from the upload step (filename → uploadId fallback)")
    p.add_argument("--report-id")
    p.add_argument("--source", choices=["chatgpt", "codex", "claude", "cli"])
    p.add_argument("-o", "--output", required=True)

    args = parser.parse_args()
    result = {"manifest": cmd_manifest, "upload": cmd_upload, "payload": cmd_payload}[args.cmd](args)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n")
    summary = {k: (len(v) if isinstance(v, list) else "ok") for k, v in result.items() if k != "payload"}
    print(f"[handoff] {args.cmd} → {out} {json.dumps(summary)}")


if __name__ == "__main__":
    main()
