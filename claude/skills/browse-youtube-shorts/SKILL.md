---
name: browse-youtube-shorts
description: Browse YouTube Shorts by keywords to find viral content for brand research. In Codex Desktop, prefer the built-in Browser; otherwise use local Chrome/CDP. Returns Shorts URLs with channel, views, and upload-date evidence.
---

# Browse YouTube Shorts

Search public YouTube Shorts by keywords using Codex Browser when available, with local Chrome/CDP as the portable fallback.

## Browser backend selection

When the host lists the `control-in-app-browser` skill, read and follow it before
browser work. Use its browser-client selection flow; in Codex Desktop the runtime
prefers the persistent in-app Browser. Use it instead of running `runtime/browse.py`.
Never inspect cookies, local storage, passwords, or profile files.

Collect only visible page evidence into the output schema below and add
`"browser_backend": "codex_in_app"` at the top level. Save it to the requested
output path, or return it in the conversation when no path was requested. Fall back
to the packaged Chrome/CDP runtime only when Browser is unavailable, setup/control
fails, or YouTube blocks the selected browser. State the fallback once. Hosts such
as Claude Code without Codex Browser use this fallback.

The Codex Browser tab is workflow-owned and must not survive this skill. Record the
tab when it is created, reuse that one tab for every query, and close it in a
`finally` block immediately after the output is saved or an error interrupts the
browse. Do not rely on end-of-turn cleanup and never close a user-created tab.

## Prerequisites

- `uv` (Python package manager)
- Codex's built-in Browser, or Google Chrome for the fallback

## How It Works

The fallback uses a separate headless Chrome instance driven via Chrome DevTools Protocol (CDP). **Your main Chrome is never touched.** The skill launches a dedicated research browser on a unique port (9336) with its own profile directory — no window, no dock icon, no focus stealing.

The research browser is muted with autoplay blocked (`--mute-audio`, `--autoplay-policy=document-user-activation-required`), so Shorts never play sound over your work.

## Chrome/CDP fallback

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
