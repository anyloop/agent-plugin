---
name: browse-youtube-shorts
description: Browse YouTube Shorts by keywords to find viral content for brand research. Uses Chrome DevTools Protocol in a headless research browser (no login required). Returns Shorts URLs with channel, views, and upload date metrics. Use when researching YouTube Shorts content, finding trending short-form videos, or analyzing competitor presence on YouTube.
---

# Browse YouTube Shorts

Search YouTube Shorts by keywords using a headless research browser. YouTube search is public, so no login is required.

## Prerequisites

- `uv` (Python package manager)
- Google Chrome installed

## How It Works

Uses a separate headless Chrome instance driven via Chrome DevTools Protocol (CDP). **Your main Chrome is never touched.** The skill launches a dedicated research browser on a unique port (9336) with its own profile directory.

## Quick Start

```bash
# Single keyword search
uv run --project runtime runtime/browse.py "short drama"

# Multiple keywords
uv run --project runtime runtime/browse.py "short drama" "mini series"

# Save to file
uv run --project runtime runtime/browse.py "short drama" -n 20 -o output/shorts_research.json
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `-n, --max-results` | Max results per keyword (max 50) | `10` |
| `-o, --output` | Save JSON report to file | stdout |
| `--json` | Output raw JSON | formatted |
| `--min-views` | Minimum views for outlier detection | `100000` |
| `--time-range` | today/week/month/year/all | `all` |
| `--sort-by` | relevance/views/date | `relevance` |
| `--screenshot-dir` | Directory to save per-keyword screenshots | - |

## Search Filters

YouTube's `sp` URL parameter controls the result filter:

- Shorts only: `sp=EgQQARgC`
- Shorts + this month: `sp=EgQIBBABGAI%3D`
- Shorts + sort by views: `sp=EgQQARgCCAE%3D`

## Output

```json
{
  "search_keywords": ["short drama"],
  "filters": {"time_range": "month", "sort_by": "relevance", "min_views": 100000},
  "summary": {
    "total_videos_found": 10,
    "keywords_searched": 1,
    "keyword_breakdown": {
      "short drama": {"video_count": 10, "total_views": 5000000, "avg_views": 500000, "outlier_count": 3}
    },
    "outliers_count": 3
  },
  "all_results": {
    "short drama": [
      {
        "url": "https://www.youtube.com/shorts/abc123",
        "video_id": "abc123",
        "title": "...",
        "channel_name": "...",
        "channel_url": "https://www.youtube.com/@...",
        "views_text": "1.2M views",
        "views_number": 1200000,
        "upload_date_text": "2 weeks ago",
        "thumbnail_url": "...",
        "is_outlier": true,
        "search_keyword": "short drama"
      }
    ]
  },
  "outliers": [...]
}
```
