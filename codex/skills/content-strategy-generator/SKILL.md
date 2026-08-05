---
name: content-strategy-generator
description: Generate 5-10 copy-paste-ready content strategies for a product from Gemini-analyzed trending videos. Reads the initial research report (md/pdf), excludes past inspiration videos and concept-duplicates via the strategy history, adapts scripts/text overlays to the product while keeping the source hook and viral format, and writes the strategies markdown + updated history. Use as the final step of the social-content-strategist workflow.
---

# Content Strategy Generator

Two scripts power `workflows/social-content-strategist.anyt`:

## `mine_report_keywords.py` — expand research from example videos (report-driven or standalone)

Works from the initial report's example videos (`--report`, md or pdf), from **client-provided videos they like** (repeatable `--video URL` — standalone mode, no report needed), or both. Collects captions (initial-research browse JSONs via `--captions-from`, with oEmbed / og-tag network fallback), mines the hashtags and caption phrasings those winners actually use, and has Gemini synthesize NEW per-platform search keywords grounded by `--description` (deduped against `--base-keywords`). Run it in the strategist's Step 1 so the trend browse rides the proven language of the niche.

```bash
uv run --project skills/content-strategy-generator/runtime \
  skills/content-strategy-generator/runtime/mine_report_keywords.py \
  --report {brandFolder}/{product}_social_content_research_{date}.md \
  --captions-from {initialBrandFolder}/browse_tiktok.json \
  --captions-from {initialBrandFolder}/browse_instagram.json \
  --product-name "Example Product" --niche "food scanner apps" \
  --base-keywords {workspace}/trend_keywords.json \
  -o {workspace}/expanded_keywords.json
```

Output: `{"mined_hashtags": [...], "tiktok": [...], "instagram": [...], "youtube": [...]}` — merge these into the trend browse keywords.

## `generate_strategies.py` — the synthesis step

Takes:

- **`--report`** — the initial social content research report (`.md` or `.pdf`) — OR **`--product-description`** for standalone mode (no report; the description becomes the product context)
- **`--candidates`** — JSON list of trend-video candidates, each pointing at its `trend-video-understanding` analysis:
  ```json
  [{"url": "...", "platform": "tiktok", "handle": "@x", "metric": "1.2M likes",
    "posted": "YYYY-MM-DD", "analysis_path": "candidates/analysis_123.json"}]
  ```
- **`--history`** — strategy history JSON (past batches and/or user-provided past inspiration videos):
  ```json
  {"strategies": [{"batch": 1, "date": "...", "inspiration_url": "...", "title": "...",
                   "viral_format": "...", "concept_summary": "..."}],
   "excluded_urls": ["<user-provided past inspiration video URLs>"]}
  ```

And produces:

1. **Strategies markdown** — header + footer tell the reader to copy a strategy's message and paste it into **Adant** (https://adant.ai); a single **General Instructions** section (analyze → first-frame review → script rewrite → Seedance 2.0 generation) applies to every strategy and is NOT repeated per strategy. Each strategy is **concise — one short copyable message**, focused only on the inspiration video, the avatar, what to keep, and what to change:

   ```text
   analyze <inspiration url>, and use a UGC avatar: <one-sentence avatar>

   Hook to keep: <one sentence>

   What to change: <one sentence - how the product swaps in>

   Add text overlay:
   <short overlay line>
   <product tag, e.g. "Example Product: Ingredient Scanner">
   ```

   A `.json` with the raw strategies is saved next to the `.md` (same name) for re-rendering or downstream use.

   No full scripts, no timelines, no long editing sections — the inspiration-video pick (proven engagement + hook that maps to the product) is the most important part.
2. **Updated history JSON** — this batch appended, so the next run never repeats a URL or concept.

## Exclusion pipeline (in order)

1. **URL hard-exclusion** — candidate URL appears in `history.strategies[].inspiration_url` or `history.excluded_urls` → dropped.
2. **Analysis gate** — candidates whose analysis is missing or `status != ok` → dropped.
3. **Concept-similarity filter** — Gemini compares each candidate's fingerprint (viral format + hook + concept summary) against past strategy concepts; "same format AND same core idea" → dropped. Same broad format with a genuinely different angle survives.
4. **Minimum-engagement rule** — candidates need **≥50K views/likes**; when fewer than the target count clear 50K, the floor relaxes to **≥10K**; anything under 10K is always dropped.

Exit code 2 when nothing survives — the workflow should widen/refresh the trend browse (adjacent formats, new keywords) and retry.

## Usage

```bash
uv run --project skills/content-strategy-generator/runtime \
  skills/content-strategy-generator/runtime/generate_strategies.py \
  --report {brandFolder}/{product}_social_content_research_{date}.md \
  --candidates {workspace}/candidates.json \
  --product-name "Example Product" --product-url "https://example.com/" \
  --history {workspace}/{product}_strategy_history.json \
  --count 8 \
  -o {workspace}/{product}_content_strategies_{date}.md
```

| Flag | Description |
|---|---|
| `--count` | Target strategies, clamped 5-10 (default 8) |
| `--history-out` | Custom path for updated history (default: overwrite `--history`) |
| `--model` | Gemini model (default `gemini-2.5-flash`) |

## Prerequisites

- `GEMINI_API_KEY` in `.env` / `.env.production`
- `uv` (deps: python-dotenv, pymupdf)
