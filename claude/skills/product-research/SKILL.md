---
name: product-research
description: Turn a product website URL plus free-form natural-language notes into a web-researched structured client profile (name, description, vertical, target audience, niche label, keyword seeds, competitor candidates, brand folder slug). Uses the authenticated AdAnt CLI, so users do not supply third-party model keys. The entry point of the initial-social-content-research workflow.
---

# Product Research

Turn `URL + natural language` into the structured client profile that every downstream research skill (competitor-research, keyword research, platform browsing, report generation) needs.

## Prerequisites

- `uv` (Python package manager)
- Node.js/npm for `npx @anyloop/adant-cli`
- AdAnt authentication (`npx @anyloop/adant-cli auth login` when needed)

Never ask the user for a Gemini or other model-provider API key. AdAnt owns the
upstream model credentials and accounts for usage through the user's AdAnt login.

## Quick Start

Run from the repo root:

```bash
uv run --project skills/product-research/runtime \
  skills/product-research/runtime/research_product.py \
  --url "https://example.com/" \
  --notes "dating and friendship app for GenZ, focus on dating now" \
  -o example-app/product_profile.json
```

## Options

| Flag | Description | Default |
|------|-------------|---------|
| `--url` | Product website URL (required) | — |
| `--notes` | Free-form natural-language notes; treated as authoritative and folded into the profile | `""` |
| `-o, --output` | Save profile JSON to file | stdout |

## How It Works

1. Fetches the website text directly (title, copy, footer links).
2. Starts an isolated authenticated AdAnt agent session to research app-store listings, press, social handles, and competitor candidates, then removes that temporary session.
3. The user's notes override inference — if notes say "focus on dating now", the niche label, keyword seeds, and competitor list center dating.
4. App detection: `is_app` is true only when the primary product is a mobile/consumer app (app-store links, "download the app" CTAs). It stays false for hardware, physical products, services, and web SaaS even when they include a companion app. When true, `keyword_seeds` include "xxx app" variants ("spark app", "mint finance app", "best dating apps") — plain common-word app names can be ambiguous in social search and the "app" suffix returns more relevant results. Downstream keyword skills (tiktok-keyword-research, instagram-keyword-research) apply the same rule to brand and competitor keywords.

## Output Schema (`product_profile.json`)

```json
{
  "client_name": "Example App",
  "website": "https://example.com/",
  "client_description": "3-4 sentence research-ready description",
  "is_app": true,
  "vertical": "GenZ Dating & Friendship App",
  "niche_label": "GenZ Dating Apps",
  "target_audience": "GenZ (18-25) ...",
  "focus": "dating (friendship secondary)",
  "platform_presence": {"tiktok": "@exampleapp", "instagram": null, "youtube": null, "notes": "..."},
  "known_competitor_candidates": [{"name": "...", "website": "...", "why": "..."}],
  "keyword_seeds": ["dating app for gen z", "..."],
  "positioning_hooks": ["..."],
  "brand_folder": "example-app",
  "research_sources": [{"title": "...", "uri": "..."}]
}
```

Downstream mapping:
- `client_name` / `client_description` / `website` → `--client` / `--description` / `--website` for `competitor-research` and keyword research skills
- `known_competitor_candidates` names → `--competitors` (comma-separated) for `competitor-research`
- `keyword_seeds` → first-round browse keywords when a keyword-research skill is skipped
- `brand_folder` → the per-brand output folder used by all workflow steps
- `niche_label` → the report's niche label
