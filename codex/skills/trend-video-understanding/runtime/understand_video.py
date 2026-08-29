#!/usr/bin/env python3
"""Analyze a short-form video through the authenticated AdAnt CLI."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

_skill_dir = Path(__file__).resolve().parent.parent
_plugin_root = _skill_dir.parent.parent
sys.path.insert(0, str(_plugin_root / "local-server" / "src"))

from adant_local.inference import analyze_video_file  # noqa: E402
from video_acquisition import AcquisitionResult, acquire_video


ANALYSIS_PROMPT = """Analyze this short-form social video using visuals and audio together.

Return a detailed narrative analysis and a compact concept fingerprint. Be strictly
evidence-based: never invent dialogue, text, expressions, actions, products, or music.
If speech is absent, say so. Transcribe visible text and audible dialogue verbatim only
when clear. The narrative must cover visual style, setting, characters, expressions,
body mechanics, hook in the first three seconds, complete beginning/middle/end story,
all text overlays with timing/position/style, audio, and a scene-by-scene timeline.

The fingerprint must identify the hook, hook type, viral format, concept summary, why
it works, exact overlays, dialogue or voiceover, music style, character, setting,
whether a product is shown, and how the format could adapt to a different product.

Also assess commercial intent from the video itself. Set promotion_strength to:
- none: the target brand/product is absent;
- incidental: it is only mentioned or briefly visible;
- integrated: it is central to the demo, story, problem, or outcome;
- direct: the video explicitly recommends, sells, or calls viewers to use/buy/download it.
List only observable promotion evidence. Mark creator_native_ugc_style true for a
creator-led testimonial, demo, tutorial, review, or skit rather than an owned-style
commercial. Creative style never proves that a sponsorship or collaboration exists.
When no target brand is provided, evaluate the most prominent named product; if no
product is present, return an empty promoted_brand and promotion_strength none."""

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "narrative_analysis": {"type": "string"},
        "fingerprint": {
            "type": "object",
            "properties": {
                "hook": {"type": "string"},
                "hook_type": {"type": "string"},
                "viral_format": {"type": "string"},
                "concept_summary": {"type": "string"},
                "why_it_works": {"type": "string"},
                "text_overlays": {"type": "array", "items": {"type": "string"}},
                "dialogue_or_voiceover": {"type": "string"},
                "music_style": {"type": "string"},
                "character": {"type": "string"},
                "setting": {"type": "string"},
                "product_shown": {"type": "string"},
                "promoted_brand": {"type": "string"},
                "promotion_strength": {
                    "type": "string",
                    "enum": ["none", "incidental", "integrated", "direct"],
                },
                "promotion_evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "call_to_action": {"type": "string"},
                "creator_native_ugc_style": {"type": "boolean"},
                "adaptability_notes": {"type": "string"},
            },
            "required": [
                "hook",
                "hook_type",
                "viral_format",
                "concept_summary",
                "why_it_works",
                "text_overlays",
                "dialogue_or_voiceover",
                "music_style",
                "character",
                "setting",
                "product_shown",
                "promoted_brand",
                "promotion_strength",
                "promotion_evidence",
                "call_to_action",
                "creator_native_ugc_style",
                "adaptability_notes",
            ],
        },
    },
    "required": ["narrative_analysis", "fingerprint"],
}


def log(message: str) -> None:
    print(message, flush=True)


def analyze_video(video: Path, prompt: str, model: str | None, output: Path) -> None:
    result = analyze_video_file(
        video,
        prompt,
        schema=ANALYSIS_SCHEMA,
        model=model,
        timeout=900,
    )
    output.write_text(result)


def write_status(
    output: Path,
    url: str,
    status: str,
    error: str | None = None,
    acquisition: dict | None = None,
) -> None:
    result = {"url": url, "analyzed_at": time.strftime("%Y-%m-%d"), "status": status}
    if error:
        result["error"] = error
    if acquisition:
        result["acquisition"] = acquisition
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False))


def successful_output_exists(output: Path) -> bool:
    if not output.exists():
        return False
    try:
        return json.loads(output.read_text()).get("status") == "ok"
    except (OSError, json.JSONDecodeError, AttributeError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a short-form video through AdAnt")
    parser.add_argument("--url", help="TikTok, Instagram, or YouTube URL")
    parser.add_argument(
        "--video",
        type=Path,
        help="already-downloaded local video; bypasses yt-dlp while retaining --url as provenance",
    )
    parser.add_argument("-o", "--output", required=True, help="Output JSON path")
    parser.add_argument("--context", default="", help="Optional niche or product context")
    parser.add_argument(
        "--brand",
        default="",
        help="Target brand/product for the promotion-strength assessment",
    )
    parser.add_argument("--model", help="Optional AdAnt video-understanding model override")
    parser.add_argument("--work-dir", help="Directory for the downloaded video")
    parser.add_argument("--keep-video", action="store_true", help="Keep the downloaded video")
    parser.add_argument(
        "--cookies-from-browser",
        help="optional yt-dlp browser cookie spec, e.g. chrome:/path/to/research-profile",
    )
    parser.add_argument(
        "--download-timeout",
        type=float,
        default=120,
        help="seconds allowed for media acquisition",
    )
    args = parser.parse_args()
    if not args.url and not args.video:
        parser.error("one of --url or --video is required")
    if args.download_timeout <= 0:
        parser.error("--download-timeout must be positive")

    output = Path(args.output)
    if successful_output_exists(output):
        log(f"Output already exists, skipping: {output}")
        return
    if output.exists():
        log(f"Retrying previous incomplete output: {output}")

    temp_dir = None
    if args.work_dir:
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory()
        work_dir = Path(temp_dir.name)

    source_url = args.url or args.video.expanduser().resolve().as_uri()
    if args.video:
        local_video = args.video.expanduser().resolve()
        if not local_video.is_file():
            acquisition = AcquisitionResult(
                None,
                "local-file",
                "failed",
                "missing_local_file",
                f"local video not found: {local_video}",
            )
        else:
            acquisition = AcquisitionResult(local_video, "local-file", "ok")
        video = acquisition.path
    else:
        log(f"Downloading: {source_url}")
        acquisition = acquire_video(
            source_url,
            work_dir,
            cookies_from_browser=args.cookies_from_browser,
            timeout_seconds=args.download_timeout,
        )
        video = acquisition.path
    if not video:
        metadata = acquisition.metadata()
        write_status(
            output,
            source_url,
            "download_failed",
            acquisition.error,
            metadata,
        )
        if acquisition.error:
            print(acquisition.error, file=sys.stderr)
        sys.exit(2)

    prompt = ANALYSIS_PROMPT
    if args.brand:
        prompt += f"\n\nTarget brand/product to evaluate: {args.brand}"
    if args.context:
        prompt += f"\n\nResearch context: {args.context}"

    raw_output = work_dir / "adant-analysis.json"
    try:
        log("Analyzing through authenticated AdAnt video understanding...")
        analyze_video(video, prompt, args.model, raw_output)
        analysis = json.loads(raw_output.read_text())
        result = {
            "url": source_url,
            "analyzed_at": time.strftime("%Y-%m-%d"),
            "status": "ok",
            "acquisition": acquisition.metadata(),
            **analysis,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        write_status(
            output,
            source_url,
            "analysis_failed",
            str(exc),
            acquisition.metadata(),
        )
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        if not args.video and args.work_dir and not args.keep_video and video.exists():
            video.unlink()
        if temp_dir:
            temp_dir.cleanup()

    fingerprint = result.get("fingerprint", {})
    log(f"Saved analysis to {output}")
    log(
        f"  format: {fingerprint.get('viral_format')} | "
        f"promotion: {fingerprint.get('promotion_strength')} | "
        f"hook: {str(fingerprint.get('hook'))[:80]}"
    )


if __name__ == "__main__":
    main()
