#!/usr/bin/env python3
"""
Product Research — Turn a website URL + free-form notes into a structured client profile.

The entry point of the initial-social-content-research workflow: the user provides a
product URL and whatever context they have in natural language ("it is a dating and
friendship app for GenZ, focus on dating now"), and this skill produces the structured
client profile every downstream skill needs (client name, description, vertical,
audience, niche label, keyword seeds, known competitor candidates, brand folder slug).

Usage:
  uv run --project skills/product-research/runtime \
    skills/product-research/runtime/research_product.py \
    --url "https://example.com/" \
    --notes "dating and friendship app for GenZ, focus on dating now" \
    -o example-app/product_profile.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

_skill_dir = Path(__file__).resolve().parent.parent
_plugin_root = _skill_dir.parent.parent
sys.path.insert(0, str(_plugin_root / "local-server" / "src"))

from adant_local.inference import ask_adant  # noqa: E402


def fetch_website(url: str) -> str:
    """Fetch website text content (first 6000 chars)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:6000]
    except Exception as e:
        print(f"Warning: Could not fetch website: {e}", file=sys.stderr)
        return ""


def slugify(name: str) -> str:
    slug = name.lower().replace(" ", "-")
    return re.sub(r"[^a-z0-9-]", "", slug)


def research_product(url: str, notes: str, website_text: str) -> dict:
    """Build a structured client profile from the URL, notes, and live web research."""

    notes_section = f"\n**User notes (natural language, treat as authoritative context):**\n{notes}" if notes else ""
    website_section = f"\n**Website content (excerpt):**\n{website_text[:4000]}" if website_text else ""

    prompt = f"""You are a brand strategist preparing a social content research brief. A user gave you a product website URL and some natural-language notes. Research the product on the web and produce a structured client profile.

**Product URL:** {url}
{notes_section}
{website_section}

## TASK

Research this product (search for the product name, the domain, app store listings, press coverage) and fill in the profile below. The user's notes override anything you infer — if the notes say "focus on dating", the niche and keywords must center dating even if the product also does other things.

Return ONLY valid JSON:
{{
  "client_name": "Official product/brand name (e.g., 'Example App')",
  "website": "{url}",
  "client_description": "3-4 sentence description usable as research input: what the product is, what it does, who it's for, how it's positioned. Fold in the user's notes.",
  "is_app": true,
  "vertical": "Short category label (e.g., 'GenZ Dating & Friendship App')",
  "niche_label": "Short niche label for reports (e.g., 'GenZ Dating Apps')",
  "target_audience": "Who the product targets — age range, demographics, psychographics",
  "focus": "The strategic focus per the user's notes (e.g., 'dating (friendship secondary)')",
  "platform_presence": {{
    "tiktok": "@handle or null — search 'site:tiktok.com {{product}}' and the website footer",
    "instagram": "@handle or null",
    "youtube": "@handle or null",
    "notes": "1-2 sentences on their current social presence"
  }},
  "known_competitor_candidates": [
    {{"name": "Competitor", "website": "https://example.com", "why": "one line"}}
  ],
  "keyword_seeds": ["8-12 social-native search keyword seeds for this niche, informed by the focus"],
  "positioning_hooks": ["3-5 angles/hooks that make this product interesting in short-form content"],
  "brand_folder": "lowercase-hyphen slug of client_name",
  "research_sources": [{{"title": "source title", "uri": "https://source.example/page"}}]
}}

RULES:
- is_app: true only when the primary product is a mobile/consumer APP (app store links, "download the app" CTAs, mobile-first product). Set false for hardware, physical products, services, and web SaaS even when they include a companion mobile app. Classify the primary product customers are buying, not every supporting surface.
- known_competitor_candidates: 5-10 true competitors (same problem, same customer). For a GenZ dating app that means other dating/social-discovery apps, not generic social networks.
- keyword_seeds must be phrases people actually search on TikTok/Instagram/YouTube, not marketing jargon.
- If is_app is true, keyword_seeds MUST include "app"-suffixed variants for the client and top competitors (e.g., "spark app", "mint finance app", "best dating apps"). Plain common-word app names can be ambiguous in social search ("spark" → fireworks/electricity, "mint" → herbs/candy), and the "xxx app" form returns more relevant results.
- Verify the client_name against the website — do not guess from the domain alone.
- Be factual; every competitor must be a real, operating product.
- Use web research and include direct source URLs in research_sources."""

    print("  Researching product through authenticated AdAnt...")
    parsed = ask_adant(prompt, title=f"Product research: {url}")
    if not parsed.get("brand_folder"):
        parsed["brand_folder"] = slugify(parsed.get("client_name", "client"))
    else:
        parsed["brand_folder"] = slugify(parsed["brand_folder"])
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Product research — website URL + notes → structured client profile")
    parser.add_argument("--url", required=True, help="Product website URL")
    parser.add_argument("--notes", default="", help="Free-form natural language notes about the product/focus")
    parser.add_argument("-o", "--output", default=None, help="Save profile JSON to file")
    args = parser.parse_args()

    print(f"Fetching website: {args.url}")
    website_text = fetch_website(args.url)

    profile = research_product(args.url, args.notes, website_text)

    print(f"\nClient: {profile.get('client_name')}")
    print(f"Vertical: {profile.get('vertical')}")
    print(f"Focus: {profile.get('focus')}")
    print(f"Brand folder: {profile.get('brand_folder')}")
    print(f"Competitor candidates: {', '.join(c['name'] for c in profile.get('known_competitor_candidates', []))}")
    print(f"Keyword seeds: {', '.join(profile.get('keyword_seeds', []))}")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(profile, indent=2))
        print(f"\nSaved to {args.output}")
    else:
        print(json.dumps(profile, indent=2))


if __name__ == "__main__":
    main()
