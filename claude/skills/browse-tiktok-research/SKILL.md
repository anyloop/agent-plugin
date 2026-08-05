---
name: browse-tiktok-research
description: Search TikTok for videos by keywords with filters (sort, time range, duration) and generate research reports. Uses browser-use with a persistent Chrome profile. Login once, then search freely. Use when the user wants to research TikTok content, find trending videos, analyze competitors, or discover relevant content for marketing.
---

# Browse TikTok Research

Search TikTok by keywords using an AI-powered browser agent. Login once to TikTok in a research browser, then run keyword searches that return video URLs with engagement metrics (views, likes, comments) and summary reports.

## Prerequisites

- `uv` (Python package manager)
- Google Chrome installed
- `GEMINI_API_KEY` environment variable set (in `.env` or `.env.production`)

## How It Works

Uses [browser-use](https://github.com/browser-use/browser-use) with Chrome CDP (Chrome DevTools Protocol). **Your main Chrome is never closed.** The skill launches a separate research browser instance that imports your TikTok session from Chrome on first run.

- **Login:** Just be logged into TikTok in your regular Chrome. Run `--login` to open TikTok in your browser if needed.
- **Browsing:** A separate research browser opens with CDP enabled, using an imported copy of your session. Your main Chrome stays open and untouched.
- **Session persistence:** The research browser profile is stored in `data/cdp-profile/`. Cookies are imported once and persist across runs.

## Quick Start

Run from the skill folder (`skills/browse-tiktok-research/`):

```bash
# Step 1: Login to TikTok (only needed once)
uv run --project runtime runtime/browse.py --login

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
| `--login` | Open TikTok login page (run once) | - |
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
