---
name: trend-video-understanding
description: Download a short-form video and analyze it deeply through AdAnt's authenticated video-understanding API — narrative analysis, a compact concept fingerprint, and an evidence-based brand-promotion assessment for creator-partnership research. Users do not supply a Gemini or other model-provider key.
---

# Trend Video Understanding

Download any TikTok / Instagram Reel / YouTube Short via yt-dlp, then send the local file through `npx @anyloop/adant-cli media analyze`. AdAnt owns the upstream model credential and charges usage to the authenticated AdAnt account. The structured response contains:

1. **Narrative pass** — the same Pass-1 analysis prompt as `workflows/clone-video.anyt` Step 2 (visual style, setting, expressions, body mechanics, complete story, verbatim text overlays, verbatim dialogue, scene-by-scene breakdown). Anti-hallucination rules included (no invented dialogue, no invented expressions).
2. **Concept fingerprint** — structured JSON: `hook`, `hook_type`, `viral_format`, `concept_summary`, `why_it_works`, `text_overlays`, `dialogue_or_voiceover`, `music_style`, `character`, `setting`, `product_shown`, `adaptability_notes`.
3. **Promotion assessment** — `promoted_brand`, `promotion_strength`, observable
   `promotion_evidence`, `call_to_action`, and `creator_native_ugc_style`. This
   measures how directly the video promotes a named brand; it does not infer a
   sponsorship from production style.

The fingerprint is what downstream strategy generation uses to (a) avoid suggesting concepts already covered by past inspiration videos, and (b) adapt the format to promote a different product while keeping the hook and viral mechanics intact.

## Prerequisites

- Node.js/npm for `npx @anyloop/adant-cli`
- AdAnt authentication (`npx @anyloop/adant-cli auth login` when needed)
- `uv` and `yt-dlp`

Never ask the user for a Gemini key. If authentication is missing, request AdAnt
login only. The CLI uploads local media and calls `/v1/media.video.analyze`.

## Usage

```bash
uv run --project skills/trend-video-understanding/runtime \
  skills/trend-video-understanding/runtime/understand_video.py \
  --url "https://www.tiktok.com/@user/video/123" \
  -o candidates/analysis_123.json \
  --brand "Example Brand" \
  --context "food scanner app niche"
```

| Flag | Description |
|---|---|
| `--url` | Video URL (required) |
| `-o` | Output JSON path (required). **Skips the run if the file already exists** — safe to re-run batches. |
| `--context` | Optional niche/product context appended to the analysis prompt |
| `--brand` | Optional target brand/product for the promotion-strength assessment |
| `--model` | Optional AdAnt video-understanding model override; omit for the server default |
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
    "product_shown": "...", "promoted_brand": "...",
    "promotion_strength": "none | incidental | integrated | direct",
    "promotion_evidence": ["..."], "call_to_action": "...",
    "creator_native_ugc_style": true,
    "adaptability_notes": "..."
  }
}
```

Exit code 2 + `status: download_failed` when yt-dlp can't fetch the video (private, region-locked, deleted) — the strategist workflow should drop that candidate and move on.
