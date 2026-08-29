#!/usr/bin/env python3
"""
TikTok Keyword Research — Generate TikTok-native keywords from client context.

Uses authenticated AdAnt to analyze client description, website, and competitors and produce
a structured keyword list optimized for TikTok search/discovery.

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
sys.path.insert(0, str(_plugin_root / "local-server" / "src"))

from adant_local.inference import ask_adant  # noqa: E402


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
    """Use AdAnt to generate TikTok-native keywords."""

    competitor_section = ""
    if competitors:
        competitor_section = f"\n**Known Competitors:** {', '.join(competitors)}\nIdentify their TikTok handles and presence level. ONLY include competitors with strong TikTok presence as keywords — skip weak/none presence."

    website_section = ""
    if website_text:
        website_section = f"\n**Website Content (excerpt):**\n{website_text[:3000]}"

    prompt = f"""You are a TikTok marketing researcher. Generate a FOCUSED set of TikTok-native search keywords for this client.

**Client:** {client}
**Description:** {description}
{website_section}
{competitor_section}

**GOAL:** Produce exactly {max_keywords} high-quality keywords that will find VIRAL content on TikTok related to this brand's niche. Quality over quantity.

**KEYWORD SELECTION CRITERIA (strict):**
1. Must be terms people ACTUALLY search on TikTok (not Google SEO terms)
2. Must be likely to return videos with 10K+ views
3. 1-3 words maximum (TikTok search bar is small)
4. Conversational and natural — how real people talk
5. Specific enough to be relevant to the brand's EXACT niche — not the broader industry
6. NO hashtag-only keywords (hashtags are for discovery, not search)
7. Include top competitor names — people search for competitors to find reviews/comparisons
8. NO jargon that regular TikTok users wouldn't search

**CRITICAL — AVOID GENERIC KEYWORDS:**
The following types of keywords are TOO GENERIC and must be excluded from round 1:
- Broad psychology/behavior terms: "consumer behavior", "human behavior", "customer psychology", "why customers leave"
- Broad business terms: "future of marketing", "business growth", "startup tips", "marketing strategy"
- Broad AI terms: "AI innovation", "future of AI", "AI tools" (unless the brand IS an AI tool, then "AI" prefix is good but must be combined with the specific niche)
- Any keyword that would return millions of unrelated results

**CRITICAL — AVOID AMBIGUOUS KEYWORDS:**
Many short keywords have a DOMINANT alternative meaning on TikTok that drowns out the intended results. You MUST check each keyword for ambiguity:
- "AI interviews" → 90% of results are JOB INTERVIEW PREP, not customer/user interviews. Use "AI user interviews" or "AI customer interviews" instead.
- "AI personas" → could return AI character/avatar content. Use "AI buyer personas" or "AI research personas" if that's the intent.
- "No more surveys" → could return unrelated anti-survey memes.
- "Predict customer" → too vague, returns fortune-telling/astrology content.

For EVERY keyword, ask: "What will TikTok ACTUALLY show for this search?" If 50%+ of results would be about a DIFFERENT topic, the keyword is ambiguous — make it more specific or drop it.

**CRITICAL — APP-NAME KEYWORDS (when the client or a competitor is an app):**
If the product is an APP (mobile/consumer app — infer from the description or website), plain brand names are usually ambiguous on TikTok and drown in the alternative meaning:
- "spark" → fireworks/electricity, "mint" → herbs/candy
Always use the "app" suffix form for app brands, for BOTH the client and competitors:
- GOOD: "spark app", "mint finance app", "[brand] app review"
- BAD: "spark", "mint" (dominant alternative meaning wins the search)
If the plain name is globally unambiguous, the suffix is optional but "[name] app" still surfaces more review/comparison content.

**GOOD KEYWORD PATTERNS BY VERTICAL:**

For AI tools, combine "AI" with the specific use case:
- GOOD: "AI user research", "AI customer insights", "AI buyer personas"
- BAD: "AI for business", "customer insights", "AI interviews" (ambiguous — returns job prep)

For finance/credit, include the core problem-space terms people actually search:
- GOOD: "credit repair", "creditdebt", "debtfree", "build credit fast", "credit score", "credit builder", "low credit score", "bad credit help", "credit hacks"
- BAD: "personalfinance", "moneytok", "financetok" (too broad — these are community hashtags, not niche searches)

For health/wellness, include specific conditions and goals:
- GOOD: "gut health tips", "hormone balance", "PCOS diet", "sleep hack"
- BAD: "healthtok", "wellnesstok" (community hashtags, not niche searches)

The key distinction: **niche keywords return content directly about the problem the brand solves**. Community hashtags return everything loosely related to a broad topic.

**CATEGORY GUIDELINES:**
- **brand** (0-2 keywords): Client name only — as "[name] app" if the client is an app (see app-name rule above). Skip if brand is new/unknown on TikTok.
- **niche** (6-8 keywords): The CORE of round 1 — gets the MOST keywords. Include THREE types:
  1. **Product keywords**: What the brand's product/service IS (e.g., "credit builder", "AI user research")
  2. **Problem-space keywords**: The problem the audience HAS, using their language (e.g., "credit repair", "creditdebt", "debtfree", "bad credit help")
  3. **Action keywords**: What people search when trying to solve the problem (e.g., "build credit fast", "fix credit score", "improve credit")
  All three types are specific to the niche and return directly relevant content.
- **hook** (3-5 keywords): Longer problem phrases that match how people type in TikTok search. These are 2-4 word phrases someone types when they have the EXACT problem the brand solves. Examples: "low credit score", "how to build credit", "credit score hack", "no credit history".
- **competitor** (3-5 keywords): Competitor brand names that have TikTok presence. Include the TOP competitors regardless of their TikTok follower count — people search for competitor names to find comparison/review content. Also try "get[competitor]", "use[competitor]", "[competitor] review" patterns — and "[competitor] app" when the competitor is an app (see app-name rule above).
- **trend** (1-2 keywords): Current TikTok trends or challenges in this SPECIFIC space.

**EXCLUDED FROM ROUND 1 — saved for round 2 only:**
- **tiktok_native** (list 3-5 but do NOT include in top_keywords): Broad community hashtags that define a TikTok subculture, NOT the specific problem. The test: does this keyword describe a COMMUNITY (too broad) or a PROBLEM/SOLUTION (good for round 1)?
  - COMMUNITY (exclude): "moneytok", "financetok", "personalfinance", "techtok", "beautytok" — these are identity labels, not problem searches
  - PROBLEM/SOLUTION (include as niche): "creditdebt", "debtfree", "credit repair", "build credit" — these describe the specific problem/goal the audience has. Even though they're popular hashtags too, they return focused content about the brand's niche.
  Rule of thumb: if someone searches this term, would 80%+ of results be about the brand's specific problem? If yes → niche keyword (include). If results span many unrelated topics → tiktok_native (exclude).

**TOTAL: Exactly {max_keywords} keywords in `top_keywords` (from brand + niche + hook + competitor + trend only). List tiktok_native separately but exclude from top_keywords.**

Also identify competitors and their TikTok presence level.

Return ONLY valid JSON:
{{
  "client": "{client}",
  "keyword_categories": {{
    "brand": ["kw1"],
    "niche": ["kw1", "kw2", "kw3", "kw4", "kw5", "kw6"],
    "hook": ["kw1", "kw2", "kw3"],
    "competitor": ["comp1", "comp2", "comp3"],
    "trend": ["kw1"],
    "tiktok_native": ["communitytok1", "communitytok2", "communitytok3"]
  }},
  "top_keywords": ["ranked {max_keywords} keywords from brand+niche+hook+competitor+trend ONLY — NO tiktok_native keywords here"],
  "tiktok_native_keywords": ["moneytok", "financetok", "etc — saved for round 2 hashtag expansion"],
  "competitors_found": [
    {{ "name": "CompName", "tiktok_handle": "@handle_or_unknown", "presence_level": "strong|medium|weak|none", "follower_estimate": "10K+" }}
  ]
}}"""

    parsed = ask_adant(prompt, title=f"TikTok keywords: {client}")

    # Collect tiktok_native keywords to exclude from round 1
    categories = parsed.get("keyword_categories", {})
    native_kws = {kw.lower().strip().lstrip("#") for kw in categories.get("tiktok_native", [])}
    # Also exclude from tiktok_native_keywords field if present
    for kw in parsed.get("tiktok_native_keywords", []):
        native_kws.add(kw.lower().strip().lstrip("#"))

    # Use top_keywords if provided, otherwise build from non-native categories
    top_kws = parsed.get("top_keywords", [])
    if not top_kws:
        for cat, cat_kws in categories.items():
            if cat != "tiktok_native":
                top_kws.extend(cat_kws)

    # Deduplicate preserving order, and exclude tiktok_native keywords
    seen: set[str] = set()
    unique: list[str] = []
    for kw in top_kws:
        lower = kw.lower().strip().lstrip("#")
        if lower not in seen and lower not in native_kws:
            seen.add(lower)
            unique.append(kw.strip())

    # Enforce max
    unique = unique[:max_keywords]

    # Collect native keywords separately for round 2
    native_list = list({kw.strip().lstrip("#") for kw in categories.get("tiktok_native", [])} | {kw.strip().lstrip("#") for kw in parsed.get("tiktok_native_keywords", [])})

    return {
        **parsed,
        "top_keywords": unique,
        "tiktok_native_keywords": native_list,
        "all_keywords": unique,
        "total_keywords": len(unique),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TikTok Keyword Research")
    parser.add_argument("--client", required=True, help="Client/brand name")
    parser.add_argument("--description", required=True, help="Product/service description")
    parser.add_argument("--website", default=None, help="Client website URL")
    parser.add_argument("--competitors", default="", help="Comma-separated competitor names")
    parser.add_argument("--max-keywords", type=int, default=15, help="Max keywords for round 1 (default 15)")
    parser.add_argument("-o", "--output", default=None, help="Save JSON to file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    competitors = [c.strip() for c in args.competitors.split(",") if c.strip()] if args.competitors else []

    website_text = ""
    if args.website:
        print(f"Fetching website: {args.website}")
        website_text = fetch_website(args.website)

    print(f"Generating TikTok keywords for: {args.client} (max {args.max_keywords})")
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
