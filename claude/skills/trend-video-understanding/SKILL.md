---
name: trend-video-understanding
description: Download a short-form video and analyze it deeply with Gemini video understanding — clone-video Pass-1 narrative analysis plus a compact concept fingerprint (hook, viral format, concept summary, adaptability notes). Use for every inspiration-video candidate in the social-content-strategist workflow so concepts can be compared, deduped against history, and adapted to a product.
---

# Trend Video Understanding

Download any TikTok / Instagram Reel / YouTube Short via yt-dlp, upload it to the Gemini Files API, and run video understanding twice:

1. **Narrative pass** — the same Pass-1 analysis prompt as `workflows/clone-video.anyt` Step 2 (visual style, setting, expressions, body mechanics, complete story, verbatim text overlays, verbatim dialogue, scene-by-scene breakdown). Anti-hallucination rules included (no invented dialogue, no invented expressions).
2. **Concept fingerprint** — structured JSON: `hook`, `hook_type`, `viral_format`, `concept_summary`, `why_it_works`, `text_overlays`, `dialogue_or_voiceover`, `music_style`, `character`, `setting`, `product_shown`, `adaptability_notes`.

The fingerprint is what downstream strategy generation uses to (a) avoid suggesting concepts already covered by past inspiration videos, and (b) adapt the format to promote a different product while keeping the hook and viral mechanics intact.

## Prerequisites

- `GEMINI_API_KEY` in `.env` / `.env.production`
- `uv` (deps: yt-dlp, python-dotenv)

## Usage

```bash
uv run --project skills/trend-video-understanding/runtime \
  skills/trend-video-understanding/runtime/understand_video.py \
  --url "https://www.tiktok.com/@user/video/123" \
  -o candidates/analysis_123.json \
  --context "food scanner app niche"
```

| Flag | Description |
|---|---|
| `--url` | Video URL (required) |
| `-o` | Output JSON path (required). **Skips the run if the file already exists** — safe to re-run batches. |
| `--context` | Optional niche/product context appended to the analysis prompt |
| `--model` | Gemini model (default `gemini-2.5-flash`) |
| `--work-dir` | Keep downloads here instead of a temp dir |
| `--keep-video` | Don't delete the downloaded video (only with `--work-dir`) |

## Output JSON

```json
{
  "url": "...",
  "analyzed_at": "YYYY-MM-DD",
  "status": "ok | download_failed",
  "narrative_analysis": "<full Pass-1 rich text>",
  "fingerprint": {
    "hook": "...", "hook_type": "...", "viral_format": "...",
    "concept_summary": "...", "why_it_works": "...",
    "text_overlays": ["..."], "dialogue_or_voiceover": "...",
    "music_style": "...", "character": "...", "setting": "...",
    "product_shown": "...", "adaptability_notes": "..."
  }
}
```

Exit code 2 + `status: download_failed` when yt-dlp can't fetch the video (private, region-locked, deleted) — the strategist workflow should drop that candidate and move on.
