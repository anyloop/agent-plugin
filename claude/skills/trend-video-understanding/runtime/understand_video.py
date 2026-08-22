#!/usr/bin/env python3
"""Analyze a short-form video through the authenticated AdAnt CLI."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


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


def download_video(url: str, work_dir: Path) -> Path | None:
    output_template = str(work_dir / "source.%(ext)s")
    command = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize",
        "200M",
        "-f",
        "best[ext=mp4]/best",
        "-o",
        output_template,
        url,
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        return None
    return next(iter(work_dir.glob("source.*")), None)


def analyze_video(video: Path, prompt: str, model: str | None, output: Path) -> None:
    command = [
        "npx",
        "--yes",
        "@anyloop/adant-cli",
        "media",
        "analyze",
        "--video",
        str(video),
        "--prompt",
        prompt,
        "--schema",
        json.dumps(ANALYSIS_SCHEMA),
        "-o",
        str(output),
    ]
    if model:
        command.extend(["--model", model])
    result = subprocess.run(command, capture_output=True, text=True, timeout=900)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        auth_markers = (
            "http 401",
            "status: 401",
            "not authenticated",
            "authentication required",
            "not logged in",
            "unauthorized",
        )
        if any(marker in detail.lower() for marker in auth_markers):
            detail = (
                "AdAnt authentication is required. Run "
                "`npx @anyloop/adant-cli auth login` in your system terminal, then "
                "retry. No Gemini API key is needed."
            )
        raise RuntimeError(detail)


def write_status(output: Path, url: str, status: str, error: str | None = None) -> None:
    result = {"url": url, "analyzed_at": time.strftime("%Y-%m-%d"), "status": status}
    if error:
        result["error"] = error
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a short-form video through AdAnt")
    parser.add_argument("--url", required=True, help="TikTok, Instagram, or YouTube URL")
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
    args = parser.parse_args()

    output = Path(args.output)
    if output.exists():
        log(f"Output already exists, skipping: {output}")
        return

    temp_dir = None
    if args.work_dir:
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
    else:
        temp_dir = tempfile.TemporaryDirectory()
        work_dir = Path(temp_dir.name)

    log(f"Downloading: {args.url}")
    video = download_video(args.url, work_dir)
    if not video:
        write_status(output, args.url, "download_failed")
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
            "url": args.url,
            "analyzed_at": time.strftime("%Y-%m-%d"),
            "status": "ok",
            **analysis,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001
        write_status(output, args.url, "analysis_failed", str(exc))
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    finally:
        if args.work_dir and not args.keep_video and video.exists():
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
