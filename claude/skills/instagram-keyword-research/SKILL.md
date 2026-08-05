---
name: instagram-keyword-research
description: Generate Instagram-native keywords from a client description, website, or niche. Produces search keywords optimized for Instagram's Reels discovery and Explore page, including competitor brand keywords, trending hashtags, and audience-specific terms. Use when you need to discover what keywords to search on Instagram Reels for a specific brand, product, or niche.
---

# Instagram Keyword Research

Generate Instagram-native search keywords from a client description, website URL, or niche. Outputs a structured keyword list optimized for Instagram Reels discovery and the Explore page.

## Prerequisites

- `uv` (Python package manager)
- `GEMINI_API_KEY` environment variable set

## Quick Start

```bash
uv run --project skills/instagram-keyword-research/runtime \
  skills/instagram-keyword-research/runtime/research_keywords.py \
  --client "BrandName" \
  --description "Product description" \
  --competitors "Comp1,Comp2" \
  --max-keywords 50 \
  -o keywords.json
```

## Options

| Flag | Description | Required |
|------|-------------|----------|
| `--client` | Client/brand name | Yes |
| `--description` | Product/service description | Yes |
| `--website` | Client website URL | No |
| `--competitors` | Comma-separated competitor names | No |
| `--max-keywords` | Max keywords (default: 15) | No |
| `-o, --output` | Save JSON to file | No (stdout) |

## Keyword Categories

- **brand** (0-2) -- Client name, skip if unknown on Instagram
- **niche** (4-6) -- Core keywords combining technology/approach with use case
- **hashtag** (4-6) -- Instagram hashtags (without #) that are searchable and relevant
- **hook** (2-3) -- Problem/curiosity phrases for Reels captions
- **trend** (1-2) -- Current Instagram Reels trends in the niche
- **competitor** (0-3) -- Competitor names with strong Instagram presence
- **meta_ads** (2-3) -- Keywords optimized for Meta Ad Library search

## Output Format

```json
{
  "client": "BrandName",
  "keyword_categories": {
    "brand": ["brandname"],
    "niche": ["AI user research", "customer insights"],
    "hashtag": ["marketresearch", "aitools", "customerfeedback"],
    "hook": ["stop guessing what customers want"],
    "trend": ["AI in marketing"],
    "competitor": ["competitorname"],
    "meta_ads": ["research platform app", "AI insights tool"]
  },
  "top_keywords": ["ranked list"],
  "all_keywords": ["deduped flat list"],
  "total_keywords": 50
}
```
