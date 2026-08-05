#!/usr/bin/env python3
"""
Trend Video Understanding — Download a short-form video and analyze it deeply with Gemini.

Used by the social-content-strategist workflow: every inspiration-video candidate is
downloaded (yt-dlp) and run through Gemini video understanding using the same Pass-1
analysis prompt as clone-video.anyt (narrative + structured scene JSON), plus a compact
"concept fingerprint" (hook type, viral format, concept summary) that downstream
strategy generation uses to avoid re-suggesting concepts already covered by past
inspiration videos.

Usage:
  uv run --project skills/trend-video-understanding/runtime \
    skills/trend-video-understanding/runtime/understand_video.py \
    --url "https://www.tiktok.com/@user/video/123" \
    -o candidate_123.json \
    [--context "food scanner app niche"] \
    [--work-dir /tmp/videos] [--keep-video]
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

_skill_dir = Path(__file__).resolve().parent.parent
_project_root = _skill_dir.parent.parent
for env_file in [_skill_dir / ".env", _project_root / ".env", _project_root / ".env.production"]:
    if env_file.exists():
        load_dotenv(env_file)

GEMINI_BASE = "https://generativelanguage.googleapis.com"

# Pass-1 analysis prompt from workflows/clone-video.anyt (Step 2), trimmed to the parts
# needed for concept understanding and later clone-prompt writing.
ANALYSIS_PROMPT = """You are analyzing a short-form social media video to create a comprehensive video description for AI video recreation.

**YOUR TASK:**
Analyze this video (both visuals and audio together) and create a detailed video description.

**CRITICAL - AVOID HALLUCINATION FOR DIALOGUE:**
- Many TikTok/social media videos have NO dialogue - only background music
- Do NOT fabricate or imagine dialogue that doesn't exist
- If no one is speaking, explicitly state: "No dialogue - background music only"
- Only transcribe speech if someone is CLEARLY speaking with audible words
- Lip-syncing to music is NOT dialogue - describe it as lip-syncing

**CRITICAL - AVOID HALLUCINATION FOR ACTIONS & EXPRESSIONS:**
- Only describe actions that are CLEARLY VISIBLE in the video
- Only describe expressions you can ACTUALLY SEE on the face
- If a face is not clearly visible, obscured, or too small: say "face not clearly visible"
- Do NOT infer or assume - describe only what is shown
- When uncertain: use phrases like "appears to be", "seems to", "possibly"

**CRITICAL INSTRUCTIONS:**
1. **VISUAL STYLE** (2-3 sentences): camera/capture method, camera movement, lighting
   (indoor/outdoor, time of day, source, quality, direction), color grading, production quality.
2. **SETTING & ENVIRONMENT**: location type, background elements, props, atmosphere,
   visual aesthetics, depth (foreground/midground/background).
3. **FACIAL EXPRESSIONS & EMOTIONS**: expressions in detail throughout, how they change,
   micro-expressions. Only what you can clearly see.
4. **CHARACTER ACTIONS & BODY MECHANICS**: body mechanics (locomotion, posture, weight
   transfer, upper body, head/neck), object interactions, transitions, speed and energy,
   spatial changes.
5. **COMPLETE STORY** (150-300 words): Hook (first 3 seconds - what grabs attention),
   setting, beginning (character descriptions), middle (vivid physics-based actions),
   end (resolution).
6. **TEXT OVERLAYS**: transcribe ALL on-screen text EXACTLY word-for-word with timing,
   position, styling. Format: [TEXT OVERLAY: "exact text" - position, style, timing]
7. **AUDIO & DIALOGUE**: if no dialogue state "No dialogue - background music only" and
   describe the music; if dialogue exists TRANSCRIBE EVERY WORD VERBATIM with timestamps.
8. **SCENE-BY-SCENE BREAKDOWN**: for each distinct scene/shot: shot type, angle, movement,
   lighting, setting, expression, facing, dialogue, text, action with body mechanics.

Write the complete video description now:"""

FINGERPRINT_PROMPT = """Based on the video you just analyzed, output a compact structured JSON "concept fingerprint" used to compare content concepts:

{
  "duration_seconds": <number>,
  "hook": "<the first-3-seconds attention grab, one sentence>",
  "hook_type": "<label: question hook / shock stat / POV caption / transformation / greenscreen rant / receipt reveal / duet-stitch / talking head confession / skit / demo / other>",
  "viral_format": "<the repeatable format label, e.g. 'UGC scan demo', 'POV skit', 'street interview', 'label-shock swap', 'grocery haul', 'talking head', 'day in my life', 'app review'>",
  "concept_summary": "<2-3 sentences: what the video's CONCEPT is - the idea a strategist would copy>",
  "why_it_works": "<1-2 sentences on the mechanics that make it perform>",
  "text_overlays": ["<all on-screen text verbatim, in order>"],
  "dialogue_or_voiceover": "<full transcript, or 'none - music only'>",
  "music_style": "<music description or 'none'>",
  "character": "<who is on camera: demographics, styling, energy - or 'no person'>",
  "setting": "<where it is shot>",
  "product_shown": "<any product/app shown or promoted, or 'none'>",
  "adaptability_notes": "<1-2 sentences: what to keep vs swap when adapting this format to promote a different product>"
}"""


def log(msg: str) -> None:
    print(msg, flush=True)


def download_video(url: str, work_dir: Path) -> Path | None:
    """Download the video with yt-dlp. Returns the file path or None."""
    out_tpl = str(work_dir / "video.%(ext)s")
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--no-playlist", "-f", "mp4/bv*+ba/b",
        "--merge-output-format", "mp4",
        "--max-filesize", "80M",
        "-o", out_tpl, url,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        log(f"  yt-dlp failed: {r.stderr.strip()[-300:]}")
        return None
    for f in sorted(work_dir.glob("video.*")):
        if f.suffix in (".mp4", ".webm", ".mov", ".mkv"):
            return f
    return None


def upload_to_gemini(video_path: Path, api_key: str) -> dict:
    """Upload the video via the Gemini Files API (resumable) and wait until ACTIVE."""
    mime = mimetypes.guess_type(str(video_path))[0] or "video/mp4"
    size = video_path.stat().st_size

    start_req = urllib.request.Request(
        f"{GEMINI_BASE}/upload/v1beta/files?key={api_key}",
        data=json.dumps({"file": {"display_name": video_path.name}}).encode(),
        headers={
            "X-Goog-Upload-Protocol": "resumable",
            "X-Goog-Upload-Command": "start",
            "X-Goog-Upload-Header-Content-Length": str(size),
            "X-Goog-Upload-Header-Content-Type": mime,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(start_req, timeout=60) as resp:
        upload_url = resp.headers["X-Goog-Upload-URL"]

    upload_req = urllib.request.Request(
        upload_url,
        data=video_path.read_bytes(),
        headers={
            "X-Goog-Upload-Command": "upload, finalize",
            "X-Goog-Upload-Offset": "0",
            "Content-Length": str(size),
        },
        method="POST",
    )
    with urllib.request.urlopen(upload_req, timeout=600) as resp:
        file_info = json.loads(resp.read().decode())["file"]

    # Poll until the file is processed
    for _ in range(60):
        if file_info.get("state") == "ACTIVE":
            return file_info
        time.sleep(5)
        with urllib.request.urlopen(
            f"{GEMINI_BASE}/v1beta/{file_info['name']}?key={api_key}", timeout=30
        ) as resp:
            file_info = json.loads(resp.read().decode())
    raise RuntimeError(f"Gemini file processing did not complete: {file_info.get('state')}")


def gemini_video_call(file_info: dict, prompt: str, api_key: str, model: str,
                      json_mode: bool = False, temperature: float = 0.4) -> str:
    body: dict = {
        "contents": [{"parts": [
            {"file_data": {"file_uri": file_info["uri"], "mime_type": file_info["mimeType"]}},
            {"text": prompt},
        ]}],
        "generationConfig": {"temperature": temperature, "maxOutputTokens": 8192},
    }
    if json_mode:
        body["generationConfig"]["response_mime_type"] = "application/json"
    req = urllib.request.Request(
        f"{GEMINI_BASE}/v1beta/models/{model}:generateContent?key={api_key}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=600) as resp:
        result = json.loads(resp.read().decode())
    parts = result["candidates"][0]["content"]["parts"]
    return "".join(p["text"] for p in parts if "text" in p)


def parse_json_loose(text: str) -> dict:
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    cleaned = re.sub(r",\s*([}\]])", r"\1", text.strip())
    return json.loads(cleaned)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download + Gemini-understand a short-form video")
    parser.add_argument("--url", required=True, help="Video URL (TikTok / Instagram / YouTube)")
    parser.add_argument("-o", "--output", required=True, help="Output JSON path")
    parser.add_argument("--context", default="", help="Optional niche/product context appended to the analysis prompt")
    parser.add_argument("--model", default="gemini-2.5-flash", help="Gemini model for analysis")
    parser.add_argument("--work-dir", help="Directory for the downloaded video (default: temp dir)")
    parser.add_argument("--keep-video", action="store_true", help="Keep the downloaded video file")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.output)
    if out_path.exists():
        log(f"Output already exists, skipping: {out_path}")
        return

    if args.work_dir:
        work_dir = Path(args.work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)
        cleanup = not args.keep_video
    else:
        tmp = tempfile.TemporaryDirectory()
        work_dir = Path(tmp.name)
        cleanup = False  # TemporaryDirectory cleans itself

    log(f"Downloading: {args.url}")
    video_path = download_video(args.url, work_dir)
    result: dict = {"url": args.url, "analyzed_at": time.strftime("%Y-%m-%d")}
    if not video_path:
        result["status"] = "download_failed"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        log("Download failed; wrote status=download_failed")
        sys.exit(2)

    log(f"Uploading to Gemini ({video_path.stat().st_size // 1024} KB)...")
    file_info = upload_to_gemini(video_path, api_key)

    prompt = ANALYSIS_PROMPT
    if args.context:
        prompt += f"\n\n**CONTEXT:** This analysis is for content research in this niche: {args.context}"

    log("Analyzing (narrative pass)...")
    narrative = gemini_video_call(file_info, prompt, api_key, args.model, temperature=0.4)

    log("Extracting concept fingerprint...")
    fp_text = gemini_video_call(file_info, FINGERPRINT_PROMPT, api_key, args.model,
                                json_mode=True, temperature=0.2)
    try:
        fingerprint = parse_json_loose(fp_text)
    except json.JSONDecodeError:
        fingerprint = {"raw": fp_text}

    # Delete the uploaded file from Gemini
    try:
        req = urllib.request.Request(
            f"{GEMINI_BASE}/v1beta/{file_info['name']}?key={api_key}", method="DELETE")
        urllib.request.urlopen(req, timeout=30)
    except Exception:
        pass
    if cleanup and video_path.exists():
        video_path.unlink()

    result.update({
        "status": "ok",
        "narrative_analysis": narrative,
        "fingerprint": fingerprint,
    })
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log(f"Saved analysis to {out_path}")
    log(f"  format: {fingerprint.get('viral_format')} | hook: {str(fingerprint.get('hook'))[:80]}")


if __name__ == "__main__":
    main()
