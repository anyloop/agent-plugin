---
name: browse-instagram-reels
description: Browse Instagram Reels by keywords to find viral content for brand research. Uses direct Chrome CDP automation with a persistent profile and a public-index fallback. Login once to Instagram, then search freely; no model-provider API key is required.
---

# Browse Instagram Reels

Search Instagram Reels by keywords using direct Chrome automation. Login once, then run keyword searches that return Reel URLs with engagement metrics.

## Prerequisites

- `uv` (Python package manager)
- Google Chrome installed

## How It Works

Uses Chrome CDP in a separate **headless** research browser — no window, no dock icon, nothing to click away. **Your main Chrome is never touched.**

Every browser this skill launches runs with `--mute-audio` and autoplay blocked (`--autoplay-policy=document-user-activation-required`), so a Reels feed never plays sound over your work.

**Signed out, Instagram walls most search results**, so signing in once is what
makes this skill useful. Before searching, run `--login-check`. If it reports
`logged_in: false`, tell the user that one dedicated, muted sign-in window is
about to open, run `--login`, and ask them to sign in, close the window, and
confirm. Open it at most once in the workflow, then re-run `--login-check`. If
the user declines or the check still fails, do not open it again or keep
prompting; use `discover_reels.py` and disclose the thinner coverage. A direct
runtime search still never opens a window unexpectedly: only the skill's
deliberate `--login` preflight does.

## Quick Start

```bash
# Step 1: Sign in to Instagram (only needed once — opens a browser window)
uv run --project runtime runtime/browse.py --login

# Check whether a session exists (opens and launches nothing)
uv run --project runtime runtime/browse.py --login-check

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
| `--login` | Open the Instagram sign-in window (run once) | - |
| `--login-check` | Print `{"logged_in": boolean \| null}` and exit; `null` means the session store was unreadable; opens nothing | - |
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
