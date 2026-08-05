---
name: tiktok-keyword-research
description: Generate TikTok-native keywords from a client description, website, or niche. Produces search keywords optimized for TikTok's discovery algorithm, including competitor brand keywords, trending hashtags, problem/solution terms, and audience-specific phrases. Use when you need to discover what keywords to search on TikTok for a specific brand, product, or niche.
---

# TikTok Keyword Research

Generate TikTok-native search keywords from a client description, website URL, or niche. Outputs a structured keyword list optimized for TikTok's search and discovery algorithm.

## Prerequisites

- `uv` (Python package manager)
- `GEMINI_API_KEY` environment variable set (in `.env` or shell)

## Quick Start

```bash
# From client description
uv run --project runtime runtime/research_keywords.py \
  --client "Example Claims" \
  --description "Class action settlement app that helps users discover and claim settlements" \
  --competitors "Competitor One,Competitor Two,Competitor Three"

# From website
uv run --project runtime runtime/research_keywords.py \
  --client "Example Finance" \
  --website "https://example.com/" \
  --description "Credit building fintech app"

# Output to file
uv run --project runtime runtime/research_keywords.py \
  --client "MyBrand" \
  --description "..." \
  -o keywords.json
```

## Options

| Flag | Description | Required |
|------|-------------|----------|
| `--client` | Client/brand name | Yes |
| `--description` | Product/service description, target audience, niche | Yes |
| `--website` | Client website URL (fetched and analyzed for context) | No |
| `--competitors` | Comma-separated competitor names | No |
| `--max-keywords` | Max keywords for round 1 (default: 15) | No |
| `-o, --output` | Save JSON output to file | No (stdout) |

## How It Works

1. **Analyze client context** — Parses description and optionally fetches website to understand the product, value proposition, and target audience.

2. **Generate focused keyword list** (quality over quantity):
   - **Brand** (1-2) — Client name only, skip if new/unknown on TikTok
   - **Niche** (4-6) — Core vertical terms, the main search keywords
   - **Hook** (3-4) — Problem/curiosity phrases matching viral hook patterns
   - **Trend** (3-4) — Active TikTok community terms and trending topics
   - **Competitor** (0-2) — ONLY competitors with strong TikTok presence (10K+ followers)

3. **Strict filtering:**
   - No generic/broad terms ("marketing tips", "business growth hacks")
   - No SEO jargon that TikTok users wouldn't search
   - No hashtag-only keywords
   - No competitor names with weak/no TikTok presence
   - 1-3 words max per keyword
   - Must be likely to return videos with 10K+ views

## Output Format

```json
{
  "client": "ClientName",
  "keyword_categories": {
    "brand": ["example claims app", "example claims settlements"],
    "category": ["class action settlement", "lawsuit money"],
    "problem": ["money you're owed", "unclaimed settlements"],
    "trend": ["moneytok", "side hustle tips", "free money"],
    "audience": ["you didn't know this", "stop scrolling"],
    "competitor": ["competitor one", "competitor two"]
  },
  "all_keywords": ["flat list of all unique keywords"],
  "competitors_found": [
    {
      "name": "Competitor One",
      "tiktok_handle": "@competitorone",
      "presence_level": "strong"
    }
  ],
  "total_keywords": 35
}
```

## Keyword Quality Guidelines

Good TikTok keywords are:
- **Short** — 1-4 words (TikTok search bar is small)
- **Conversational** — How people actually talk, not SEO jargon
- **Discovery-oriented** — "how to claim settlement" not "class action lawsuit legal proceedings"
- **Trend-aware** — Include niche-specific TikTok community terms (#moneytok, #cleantok, etc.)
- **Hook-adjacent** — Terms that match viral hook patterns ("you didn't know", "stop scrolling")
