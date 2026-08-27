---
name: browse-tiktok-research
description: Search TikTok for videos by keywords with filters and generate research reports. In Codex Desktop, prefer the built-in Browser and its persistent session; otherwise use local Chrome/CDP. No model-provider API key is required.
---

# Browse TikTok Research

Search TikTok by keywords using Codex Browser when available, with local Chrome automation as the portable fallback.

## Browser backend selection

When the host lists the `control-in-app-browser` skill, read and follow it before
browser work. Use its browser-client selection flow; in Codex Desktop the runtime
prefers the persistent in-app Browser. Reuse that browser and any existing TikTok
session instead of running `runtime/browse.py`. If TikTok requires authentication,
follow the Browser skill's sign-in flow and ask the user to sign in in the selected
browser. Never inspect cookies, local storage, passwords, or profile files.

Collect only visible page evidence into the output schema below and add
`"browser_backend": "codex_in_app"` at the top level. Save it to the requested
output path, or return it in the conversation when no path was requested. Fall back
to the packaged Chrome/CDP runtime only when Browser is unavailable, setup/control
fails, or TikTok blocks the selected browser after authentication. State the
fallback once. Hosts such as Claude Code without Codex Browser use this fallback.

## Prerequisites

- `uv` (Python package manager)
- Codex's built-in Browser, or Google Chrome for the fallback

## How It Works

The fallback uses Chrome CDP (Chrome DevTools Protocol) with a dedicated persistent research
profile. **Your main Chrome is never closed or read.** Sign in once through the
skill's `--login` window, and later headless searches reuse that session.

- **Browsing:** A separate headless research browser runs the searches — no window, no dock icon, nothing to click away. Your main Chrome stays open and untouched.
- **Muted by default:** every browser this skill launches runs with `--mute-audio` and autoplay blocked (`--autoplay-policy=document-user-activation-required`), so a feed of short-form video never plays sound over your work.
- **Login:** sign in once with `--login`; the session persists in the research profile across runs. **Signed out, TikTok search returns almost nothing**, so getting signed in is what makes this skill useful — see below.
- **Session persistence:** the research browser profile lives under `data/research-profile/`.

## Chrome/CDP fallback

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
| `--login-check` | Print `{"logged_in": boolean \| null}` and exit; `null` means the session store was unreadable; opens nothing | - |
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
between research and an empty file. Before searching, run `--login-check`. If it
reports `logged_in: false`, tell the user that one dedicated, muted sign-in
window is about to open, run `--login`, and ask them to sign in, close the
window, and confirm. Open it at most once in the workflow, then re-run
`--login-check`. If the user declines or the check still fails, do not open it
again or keep prompting; continue the direct browser signed out and disclose the
thinner coverage. A direct runtime search still never opens a window
unexpectedly: only the skill's deliberate `--login` preflight does.

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
