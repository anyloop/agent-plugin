---
name: browse-tiktok-research
description: Search TikTok for videos by keywords with filters (sort, time range, duration) and generate research reports. Uses direct Chrome CDP automation with a persistent research profile. Login once, then search freely; no model-provider API key is required.
---

# Browse TikTok Research

Search TikTok by keywords using direct Chrome automation. Login once to TikTok in a research browser, then run keyword searches that return video URLs with engagement metrics (views, likes, comments) and summary reports.

## Prerequisites

- `uv` (Python package manager)
- Google Chrome installed

## How It Works

Uses Chrome CDP (Chrome DevTools Protocol). **Your main Chrome is never closed.** The skill launches a separate research browser instance that imports your TikTok session from Chrome on first run.

- **Browsing:** A separate headless research browser runs the searches — no window, no dock icon, nothing to click away. Your main Chrome stays open and untouched.
- **Muted by default:** every browser this skill launches runs with `--mute-audio` and autoplay blocked (`--autoplay-policy=document-user-activation-required`), so a feed of short-form video never plays sound over your work.
- **Login:** sign in once with `--login`; the session persists in the research profile across runs. **Signed out, TikTok search returns almost nothing**, so getting signed in is what makes this skill useful — see below.
- **Session persistence:** the research browser profile lives under `data/research-profile/`.

## Quick Start

Run from the skill folder (`skills/browse-tiktok-research/`):

```bash
# Step 1: Sign in to TikTok (only needed once — opens a browser window)
uv run --project runtime runtime/browse.py --login

# Check whether a session exists (opens and launches nothing)
uv run --project runtime runtime/browse.py --login-check

# Step 2: Search keywords
uv run --project runtime runtime/browse.py "skincare routine"

# Search multiple keywords
uv run --project runtime runtime/browse.py "protein powder" "gym supplements"

# With filters
uv run --project runtime runtime/browse.py "coffee shop" --sort-by likes --time-range week

# Save report to file
uv run --project runtime runtime/browse.py "AI tools" -n 20 -o output/ai_research.json
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--login` | Open the TikTok sign-in window (run once) | - |
| `--login-check` | Print `{"logged_in": bool}` and exit; opens nothing | - |
| `-n, --max-results` | Max results per keyword | `10` |
| `-o, --output` | Save JSON report to file | stdout |
| `--json` | Output raw JSON | formatted text |
| `--sort-by` | Sort by: `relevance`, `likes`, `date` | `relevance` |
| `--time-range` | Filter: `all`, `day`, `week`, `month`, `3months`, `6months` | `month` |
| `--duration` | Filter: `all`, `short` (<1min), `medium` (1-5min), `long` (>5min) | `all` |
| `--min-views` | Minimum views for outlier detection | `50000` |
| `--min-ratio` | Minimum view/follower ratio for outliers | `5.0` |
| `--no-outliers` | Disable outlier filtering | - |
| `--no-details` | Skip Phase 2 (no detail collection) | - |

## How It Works (Two-Phase)

**Phase 1 - Search:** Collects video URLs, titles, usernames, and view counts from TikTok search results page.

**Phase 2 - Details:** Visits individual video pages for videos above the `--min-views` threshold to extract like count, comment count, duration, and creator's follower count.

## Output

### Report includes:
- Video URLs with full engagement metrics (views, likes, comments, duration, followers)
- Outlier videos (50K+ views, 5x+ view/follower ratio by default)
- Top videos ranked by views and likes
- Keyword performance breakdown (video count, avg views, avg likes)
- Applied search filters

### JSON report structure:
```json
{
  "search_keywords": ["kw1", "kw2"],
  "filters": { "sort_by": "relevance", "time_range": "all", "duration": "all" },
  "summary": {
    "total_videos_found": 20,
    "keyword_breakdown": {
      "kw1": { "video_count": 10, "total_views": 500000, "avg_views": 50000 }
    }
  },
  "top_videos_by_views": [...],
  "top_videos_by_likes": [...],
  "all_results": { "kw1": [...], "kw2": [...] }
}
```

### Video metadata fields:
`url`, `title`, `uploader`, `view_count`, `like_count`, `comment_count`, `duration`

## Signing in matters here

TikTok search is close to empty signed out, so a session is the difference
between research and an empty file. Nothing pops up on its own: a run without a
session prints a one-line request and carries on, and only `--login` — which you
run deliberately — opens a window. If you are driving this from an agent, ask
the user to run `--login` once rather than repeating searches that cannot work.

Session state is read from the profile's cookie store (cookie names and expiries
only — the values are encrypted and this skill never touches them), so an
expired session is reported as signed out instead of silently scraping nothing.

## Re-login

If your TikTok session expires, just run `--login` again:
```bash
uv run --project runtime runtime/browse.py --login
```

## Legacy Scripts

For direct API-based search (requires separate login):
- `runtime/login.py` - Login to TikTok via browser profile
- `runtime/search_tiktok.py` - Search via Playwright API interception
- `runtime/research.py` - Full company research report
