---
name: trend-video-understanding
description: Download a short-form video and analyze it deeply through AdAnt's authenticated video-understanding API — narrative analysis, a compact concept fingerprint, and an evidence-based brand-promotion assessment for creator-partnership research. Users do not supply a Gemini or other model-provider key.
---

# Trend Video Understanding

Acquire any TikTok / Instagram Reel / YouTube Short through browser-compatible
`yt-dlp`, or accept a video already downloaded by the authenticated browser,
then send the local file through `npx @anyloop/adant-cli media analyze`. AdAnt
owns the upstream model credential and charges usage to the authenticated AdAnt
account. The structured response contains:

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
| `--url` | Original video URL; required unless `--video` is supplied. |
| `--video` | Existing local video. Bypasses `yt-dlp`; pair with `--url` to preserve provenance. |
| `-o` | Output JSON path (required). **Skips the run if the file already exists** — safe to re-run batches. |
| `--context` | Optional niche/product context appended to the analysis prompt |
| `--brand` | Optional target brand/product for the promotion-strength assessment |
| `--model` | Optional AdAnt video-understanding model override; omit for the server default |
| `--work-dir` | Keep downloads here instead of a temp dir |
| `--keep-video` | Don't delete the downloaded video (only with `--work-dir`) |
| `--cookies-from-browser` | Optional `yt-dlp` browser-cookie spec for the dedicated research profile. Never print or inspect cookie values. |
| `--download-timeout` | Media-acquisition limit in seconds (default 120). |

At least one of `--url` or `--video` is required. In Codex Browser mode, prefer
`--video`: save the selected clip through the already-authenticated browser while
its page is open, without reading cookies or local storage, and retain the permanent
platform URL with `--url`. A DOM `blob:` URL is not a downloadable source—use the
browser's download or network-response capability. Otherwise the runtime
enables Chrome impersonation, the local Node.js runtime, short retries, and an
optional dedicated research-browser profile. Do not point it at the user's primary
browser profile.

## Output JSON

```json
{
  "url": "...",
  "analyzed_at": "YYYY-MM-DD",
  "status": "ok | download_failed",
  "acquisition": {
    "backend": "local-file | yt-dlp",
    "status": "ok | failed",
    "error_code": "platform_blocked | forbidden | auth_required | js_runtime_missing | timeout | ..."
  },
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

Exit code 2 + `status: download_failed` when acquisition fails. A failed output is
retryable; only `status: ok` is cached. The strategist workflow should classify the
error, try one different acquisition backend when available, then replace the clip
with a ranked reserve instead of rerunning the same command in the foreground.
