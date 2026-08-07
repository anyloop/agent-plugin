#!/usr/bin/env python3
"""
Instagram Keyword Research — Generate Instagram-native keywords from client context.

Uses authenticated AdAnt to analyze client description, website, and competitors and produce
a structured keyword list optimized for Instagram Reels discovery, the Explore
page, and Meta Ad Library search.

Usage:
  uv run --project runtime runtime/research_keywords.py \
    --client "BrandName" \
    --description "Product description..." \
    --competitors "Comp1,Comp2" \
    -o keywords.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

_skill_dir = Path(__file__).resolve().parent.parent
_plugin_root = _skill_dir.parent.parent
sys.path.insert(0, str(_plugin_root / "runtime"))

from adant_agent import ask_adant  # noqa: E402


def fetch_website(url: str) -> str:
    """Fetch website text content (first 5000 chars)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # Strip HTML tags roughly
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
    except Exception as e:
        print(f"Warning: Could not fetch website: {e}", file=sys.stderr)
        return ""


def generate_keywords(
    client: str,
    description: str,
    website_text: str,
    competitors: list[str],
    max_keywords: int = 15,
) -> dict:
    """Use AdAnt to generate Instagram-native keywords."""

    competitor_section = ""
    if competitors:
        competitor_section = (
            f"\n**Known Competitors:** {', '.join(competitors)}\n"
            "Identify their Instagram handles and presence level. "
            "ONLY include competitors with strong Instagram presence as keywords "
            "— skip weak/none presence."
        )

    website_section = ""
    if website_text:
        website_section = f"\n**Website Content (excerpt):**\n{website_text[:3000]}"

    prompt = f"""You are an Instagram marketing researcher. Generate TWO separate keyword lists for this client:
1. **Competitor keywords** — brand/competitor names for Meta Ads Library research
2. **Organic keywords** — niche keywords for Instagram Reels discovery

**Client:** {client}
**Description:** {description}
{website_section}
{competitor_section}

**GOAL:** Produce keyword lists optimized for TWO different research channels:
- **Meta Ads Library** → search by exact COMPETITOR/BRAND NAMES only. Generic keywords return too much noise in the Ad Library.
- **Instagram Reels** → search by niche-specific organic keywords that surface viral Reels content.

---

## COMPETITOR KEYWORDS (for Meta Ads Library)

These are used to search https://www.facebook.com/ads/library/ — the Meta Ad Library indexes ads by advertiser name, so searching by competitor/brand names is the MOST effective strategy.

**Include ALL of these as competitor keywords:**
- The client's own brand name ("{client}")
- Every confirmed competitor name (from the list above)
- Any well-known brand in the same space that runs Meta/Instagram ads

**Rules:**
- Use the EXACT brand name as people know it, without adding category terms
- One brand per keyword
- NO generic/niche terms — those return irrelevant ads from unrelated industries

---

## ORGANIC KEYWORDS (for Instagram Reels)

These are used to search Instagram's Explore/Reels — they should surface viral organic content.

**CATEGORY GUIDELINES:**
- **brand** (0-2): Client name only — as "[name] app" if the client is an app (see app-name rule below). Skip if brand is new/unknown on Instagram.
- **niche** (4-6): Core keywords combining technology/approach with specific use case. Narrow enough that search results are directly relevant.
- **hashtag** (4-6): Popular Instagram hashtags (WITHOUT the # symbol). Medium-specificity (not too broad like "marketing", not too narrow).
- **hook** (2-3): Problem phrases specific to the niche. Work as Reels caption hooks.
- **trend** (1-2): Current Instagram Reels trends in this specific space.

**CRITICAL — AVOID GENERIC KEYWORDS:**
- Broad psychology/behavior terms: "consumer behavior", "human behavior"
- Broad business terms: "future of marketing", "business growth", "startup tips"
- Broad AI terms: "AI innovation", "future of AI" (unless the brand IS an AI tool)
- Any keyword that would return millions of unrelated results

**CRITICAL — AVOID AMBIGUOUS KEYWORDS:**
For EVERY keyword, ask: "What will Instagram ACTUALLY show for this search?" If 50%+ of results would be about a DIFFERENT topic, drop it.

**CRITICAL — APP-NAME KEYWORDS (organic keywords only):**
If the client or a competitor is an APP (mobile/consumer app — infer from the description or website), plain common-word brand names can be ambiguous in organic search ("spark" → fireworks/electricity, "mint" → herbs/candy). For ORGANIC keywords use the "app" suffix form: "spark app", "mint finance app", "[brand] app review". This does NOT apply to competitor_keywords for the Meta Ads Library — those must stay the exact advertiser name.

**Organic keywords: aim for ~{max_keywords} across all categories.**

---

Return ONLY valid JSON:
{{
  "client": "{client}",
  "competitor_keywords": ["BrandName1", "BrandName2", "CompetitorA", "CompetitorB"],
  "keyword_categories": {{
    "brand": ["kw1"],
    "niche": ["kw1", "kw2"],
    "hashtag": ["personalfinance", "creditbuilding"],
    "hook": ["kw1"],
    "trend": ["kw1"]
  }},
  "top_keywords": ["ranked list of ~{max_keywords} best ORGANIC keywords"],
  "competitors_found": [
    {{ "name": "CompName", "instagram_handle": "@handle_or_unknown", "presence_level": "strong|medium|weak|none", "follower_estimate": "10K+" }}
  ]
}}"""

    parsed = ask_adant(prompt, title=f"Instagram keywords: {client}")

    # Extract competitor keywords (brand/competitor names for Meta Ads Library)
    competitor_kws = parsed.get("competitor_keywords", [])
    # Deduplicate competitor keywords
    comp_seen: set[str] = set()
    comp_unique: list[str] = []
    for kw in competitor_kws:
        lower = kw.lower().strip()
        if lower not in comp_seen:
            comp_seen.add(lower)
            comp_unique.append(kw.strip())

    # Use top_keywords if provided, otherwise build from categories
    top_kws = parsed.get("top_keywords", [])
    if not top_kws:
        for category_kws in parsed.get("keyword_categories", {}).values():
            top_kws.extend(category_kws)

    # Deduplicate preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for kw in top_kws:
        lower = kw.lower().strip().lstrip("#")
        if lower not in seen:
            seen.add(lower)
            unique.append(kw.strip())

    # Enforce max
    unique = unique[:max_keywords]

    return {
        **parsed,
        "competitor_keywords": comp_unique,
        "top_keywords": unique,
        "all_keywords": unique,
        "total_keywords": len(unique),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Instagram Keyword Research")
    parser.add_argument("--client", required=True, help="Client/brand name")
    parser.add_argument("--description", required=True, help="Product/service description")
    parser.add_argument("--website", default=None, help="Client website URL")
    parser.add_argument("--competitors", default="", help="Comma-separated competitor names")
    parser.add_argument("--max-keywords", type=int, default=15, help="Max keywords (default 15)")
    parser.add_argument("-o", "--output", default=None, help="Save JSON to file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    competitors = [c.strip() for c in args.competitors.split(",") if c.strip()] if args.competitors else []

    website_text = ""
    if args.website:
        print(f"Fetching website: {args.website}")
        website_text = fetch_website(args.website)

    print(f"Generating Instagram keywords for: {args.client} (max {args.max_keywords})")
    result = generate_keywords(args.client, args.description, website_text, competitors, args.max_keywords)

    output = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(output)
        print(f"Saved {result['total_keywords']} keywords to {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
