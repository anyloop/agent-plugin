---
name: browse-instagram-reels
description: Browse Instagram Reels by keywords to find viral content for brand research. Uses browser-use with a persistent Chrome profile. Login once to Instagram, then search freely. Returns Reel URLs with engagement metrics (views, likes, comments). Use when researching Instagram Reels content, finding trending videos, or analyzing competitor presence on Instagram.
---

# Browse Instagram Reels

Search Instagram Reels by keywords using an AI-powered browser agent. Login once, then run keyword searches that return Reel URLs with engagement metrics.

## Prerequisites

- `uv` (Python package manager)
- Google Chrome installed
- `GEMINI_API_KEY` environment variable set
- Logged into Instagram in your Chrome browser

## How It Works

Uses [browser-use](https://github.com/browser-use/browser-use) with Chrome CDP. **Your main Chrome is never closed.** The skill launches a separate research browser that imports your Instagram session.

## Quick Start

```bash
# Step 1: Login to Instagram (only needed once)
uv run --project runtime runtime/browse.py --login

# Step 2: Search keywords
uv run --project runtime runtime/browse.py "skincare routine"

# Multiple keywords
uv run --project runtime runtime/browse.py "protein powder" "gym supplements"

# Save to file
uv run --project runtime runtime/browse.py "AI tools" -n 20 -o output/reels_research.json
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--login` | Open Instagram login page (run once) | - |
| `-n, --max-results` | Max results per keyword | `10` |
| `-o, --output` | Save JSON report to file | stdout |
| `--json` | Output raw JSON | formatted |
| `--min-views` | Minimum views for outlier detection | `50000` |
| `--min-ratio` | Minimum view/follower ratio | `5.0` |
| `--no-details` | Skip Phase 2 (no detail collection) | - |

## Two-Phase Approach

**Phase 1 - Search:** Navigate to Instagram search, enter keyword, switch to Reels tab, collect Reel URLs and basic metadata from search results.

**Phase 2 - Details:** Visit individual Reel pages to extract full engagement metrics (views, likes, comments, creator followers).

## Output

```json
{
  "search_keywords": ["kw1", "kw2"],
  "summary": {
    "total_reels_found": 20,
    "keyword_breakdown": {
      "kw1": { "reel_count": 10, "total_views": 500000, "avg_views": 50000 }
    }
  },
  "top_reels_by_views": [...],
  "top_reels_by_likes": [...],
  "all_results": { "kw1": [...], "kw2": [...] }
}
```

## Re-login

If your session expires:
```bash
uv run --project runtime runtime/browse.py --login
```

## Login-less discovery with hashtag expansion — `discover_reels.py`

When no Instagram session exists (or `browse.py` keeps returning low-view content), use the search-based discovery script. It needs **no login** and self-expands until it finds high-engagement Reels:

1. Searches the web (DuckDuckGo-indexed `instagram.com/reel/` pages) for each seed keyword
2. Fetches every candidate reel's **real og-tag metrics** (likes, comments, caption, handle, thumbnail)
3. Keeps only reels at/above `--min-likes` (default **10K** — the minimum-engagement hard floor; pass `50000` for the preferred tier)
4. **If too few qualify, it mines the hashtags from the accepted reels' captions and runs another search round with them** (up to `--rounds`)

```bash
uv run --project skills/browse-instagram-reels/runtime \
  skills/browse-instagram-reels/runtime/discover_reels.py \
  "food scanner app" "yuka app" "healthy grocery swaps" \
  --min-likes 10000 --target 8 --rounds 3 \
  -o {brandFolder}/browse_instagram_discovered.json
```

Output: `{accepted: [{url, shortcode, handle, likes, comments, caption, thumbnail, hashtags, found_via}], queries_used, rejected_below_threshold}` — sorted by likes, ready for curation. Exit code 2 if nothing clears the threshold (then widen the seed keywords).
