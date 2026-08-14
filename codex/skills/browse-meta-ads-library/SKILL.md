---
name: browse-meta-ads-library
description: Browse Meta Ad Library by keywords and competitor names to find active Facebook and Instagram ad campaigns. Extracts ad creatives (images, videos), copy, CTAs, landing pages, and longevity data. Competitor search mode finds all ads from specific advertisers. Use when analyzing competitor advertising strategy on Facebook/Instagram.
---

# Browse Meta Ads Library

Search the Meta Ad Library by keywords and competitor names using direct CDP browser automation. The Meta Ad Library is publicly accessible (no login required). Extract ad creatives, copy, CTAs, landing pages, and advertiser information.

## Prerequisites

- `uv` (Python package manager)
- Google Chrome installed

## Quick Start

```bash
# Search by keyword
uv run --project runtime runtime/browse.py "credit building app"

# Search by competitor name (finds all their active ads)
uv run --project runtime runtime/browse.py --advertiser "Example Finance" --advertiser "Example Credit"

# Combine keywords + competitors
uv run --project runtime runtime/browse.py "credit building" --advertiser "Example Finance" --advertiser "Example Banking"

# Filter by platform and media type
uv run --project runtime runtime/browse.py "AI research tool" --platform instagram --media-type video

# Save to file
uv run --project runtime runtime/browse.py "fintech app" -n 30 -o output/ads_research.json

# JSON output
uv run --project runtime runtime/browse.py "skincare" --advertiser "Example Skincare" --json -o output/skincare_ads.json
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `keywords` | Keywords to search (positional, space-separated) | — |
| `-a, --advertiser` | Competitor/advertiser name (repeatable) | — |
| `-n, --max-results` | Max ads per keyword/advertiser | `20` |
| `-o, --output` | Save JSON report to file | stdout |
| `--json` | Output raw JSON | formatted |
| `--platform` | Filter: `all`, `facebook`, `instagram` | `all` |
| `--media-type` | Filter: `all`, `image`, `video`, `carousel` | `all` |
| `--country` | Country code for ad targeting | `US` |
| `--screenshot-dir` | Directory to save ad screenshots | None |

## How It Works

The Meta Ad Library (https://www.facebook.com/ads/library/) is a public transparency tool. No login is required.

Searches run in a headless research browser that never opens a window or takes focus, and every browser this skill launches — including `screenshot_ads.py` — is muted with autoplay blocked (`--mute-audio`, `--autoplay-policy=document-user-activation-required`), so video-heavy ad cards never play sound over your work.

**All searches use `search_type=keyword_unordered`** and `is_targeted_country=false` for the broadest possible match. The URL format is:
`https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=US&is_targeted_country=false&media_type=all&q={query}&search_type=keyword_unordered`

**Best Practice:** Search by exact **competitor/brand names** rather than generic keywords. Brand name searches return the most relevant ads in the Ad Library. Generic keywords often return noise from unrelated industries.

**Longevity Scoring:** Each ad is tagged based on how long it has been running:
- `proven_performer` (90+ days) — likely a high-performing ad
- `established` (30-89 days) — gaining traction
- `testing` (7-29 days) — in testing phase
- `new` (<7 days) — recently launched

## Output

```json
{
  "search_keywords": ["credit building"],
  "advertisers": ["Example Finance", "Example Credit"],
  "filters": { "platform": "all", "media_type": "all", "country": "US" },
  "summary": {
    "total_ads_found": 60,
    "proven_performers_count": 8,
    "keyword_breakdown": {
      "credit building": { "ad_count": 20, "advertisers": ["Brand1"] },
      "Example Finance": { "ad_count": 25, "advertisers": ["Example Finance"] }
    },
    "top_advertisers": [
      { "name": "Example Finance", "ad_count": 25, "platforms": ["facebook", "instagram"] }
    ]
  },
  "proven_performers": [
    {
      "advertiser": "Example Finance",
      "ad_text": "Build credit with everyday purchases...",
      "days_running": 142,
      "longevity_tag": "proven_performer",
      "media_type": "video",
      "creative_urls": [
        { "type": "video", "url": "https://example.com/media/video.mp4" },
        { "type": "video_thumbnail", "url": "https://example.com/media/thumb.jpg" }
      ]
    }
  ],
  "all_results": {
    "credit building": [
      {
        "advertiser": "Brand Name",
        "advertiser_page_url": "https://www.facebook.com/brandname",
        "ad_text": "Ad copy text...",
        "headline": "Ad headline",
        "cta": "Learn More",
        "media_type": "video",
        "platforms": ["facebook", "instagram"],
        "start_date": "Month DD, YYYY",
        "days_running": 71,
        "longevity_tag": "established",
        "landing_url": "https://example.com/offer",
        "creative_urls": [
          { "type": "image", "url": "https://example.com/media/ad.jpg" }
        ],
        "ad_id": "123456789",
        "ad_library_url": "https://www.facebook.com/ads/library/?id=123"
      }
    ]
  }
}
```

## Screenshot Ad Cards by ID

Capture individual ad card screenshots from the Meta Ad Library. Useful for pitch reports and competitive analysis decks.

```bash
# Screenshot specific ads by Library ID
uv run --project runtime runtime/screenshot_ads.py --ids 709633901484822 1227184966143012

# Save to a specific directory with custom prefix
uv run --project runtime runtime/screenshot_ads.py --ids 709633901484822 -o output/thumbnails/ --prefix "newsbreak-"

# Read IDs from a file (one per line)
uv run --project runtime runtime/screenshot_ads.py --ids-file ad_ids.txt -o output/thumbnails/

# For pitch decks: crop to just the ad creative (skip metadata header)
uv run --project runtime runtime/screenshot_ads.py --ids 709633901484822 --creative-only -o output/thumbnails/
```

### Screenshot Options

| Flag | Description | Default |
|------|-------------|---------|
| `--ids` | Ad Library IDs to screenshot (space-separated) | -- |
| `--ids-file` | File with ad IDs (one per line) | -- |
| `-o, --output-dir` | Directory to save screenshots | `output/ad-screenshots` |
| `--prefix` | Filename prefix | `ad-` |
| `--creative-only` | Crop to just the ad creative (skip metadata header) | false |

Each screenshot captures the ad card. With `--creative-only`, it crops to the bottom 65% showing just the advertiser, ad copy, and video thumbnail (skipping Library ID, dates, and platform badges). Use this for pitch decks where you want to zoom into the creative. Output is JPEG format.

## Tips

- **Search by competitor name** with `--advertiser` to see all their active ads
- **Long-running ads** (90+ days, tagged `proven_performer`) are likely performing well — study these closely
- **Video ads on Instagram** are often repurposed from Reels — great for content inspiration
- **Creative URLs** give you direct links to ad images/videos for reference
- **Landing URLs** show where competitors send their ad traffic
- Combine with browse-instagram-reels for a complete picture of competitor content strategy
- Use `--platform instagram` to focus only on Instagram ad placements

## Data-Completeness Caveat (IMPORTANT for client deliverables)

Meta Ad Library scrapes from this skill are best-effort, not authoritative. Pagination limits, regional / placement filters, expired or hidden ads, and Meta-side throttling mean results can undercount reality.

**Use the data for qualitative research, not published stats.**

Safe to use:
- Ad creative examples, thumbnails, ad copy, CTA patterns, hook patterns
- Qualitative observations ("competitor X relies heavily on same-cut trailer format")
- Links to the Meta Ad Library for each advertiser so the reader can verify

Do **NOT** publish in client decks, pitch reports, or external-facing materials:
- Exact ad counts per advertiser ("X has 20 active ads")
- Aggregate totals ("N ads across Y advertisers")
- Specific day-running counts on ad thumbnails (`602d`, `165d`, etc.)
- "Top advertisers by ad volume" rankings based on scrape counts
- Claims that a competitor has "zero ads" (absence in scrape ≠ absence in reality)

Internal research notes can reference the raw numbers for directional signal, but every client-facing slide should describe *patterns* rather than exact quantities.
