#!/usr/bin/env python3
"""
Competitor Research — Three-phase competitive intelligence.

Phase 1: Identify true competitors via Gemini with Google Search grounding
Phase 2: Research each competitor's TikTok presence (handles, followers, content strategy)
Phase 3: Generate a competitor analysis report (markdown)

Usage:
  # Full pipeline: research + TikTok presence + report
  uv run --project runtime runtime/research_competitors.py \
    --client "Example Insights" \
    --description "AI-powered user research platform with synthetic personas" \
    --website "https://example.com/" \
    --competitors "Competitor One,Competitor Two,Competitor Three" \
    --tiktok-presence \
    --report \
    -o competitors.json

  # Just competitor discovery (no TikTok, no report)
  uv run --project runtime runtime/research_competitors.py \
    --client "Example Insights" \
    --description "AI-powered user research platform" \
    -o competitors.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

# Load env files
_skill_dir = Path(__file__).resolve().parent.parent
_project_root = _skill_dir.parent.parent
for env_file in [_skill_dir / ".env", _project_root / ".env", _project_root / ".env.production"]:
    if env_file.exists():
        load_dotenv(env_file)


def fetch_website(url: str) -> str:
    """Fetch website text content (first 5000 chars)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        import re
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:5000]
    except Exception as e:
        print(f"Warning: Could not fetch website: {e}", file=sys.stderr)
        return ""


def _call_gemini(prompt: str, api_key: str, timeout: int = 120, use_search: bool = True) -> tuple[dict, list[dict]]:
    """Call Gemini with optional Google Search grounding. Returns (parsed_json, grounding_sources)."""
    import re as _re

    tools = [{"google_search": {}}] if use_search else []

    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 16384,
        },
        **({"tools": tools} if tools else {}),
    }).encode()

    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())

    # Extract text from response (may have multiple parts with grounding)
    parts = result["candidates"][0]["content"]["parts"]
    text = ""
    for part in parts:
        if "text" in part:
            text += part["text"]

    # Extract grounding metadata
    grounding_sources = []
    grounding_metadata = result["candidates"][0].get("groundingMetadata", {})
    for chunk in grounding_metadata.get("groundingChunks", []):
        web = chunk.get("web", {})
        if web:
            grounding_sources.append({
                "title": web.get("title", ""),
                "uri": web.get("uri", ""),
            })

    # Strip markdown code blocks
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]

    # Clean common LLM JSON issues
    cleaned = text.strip()
    cleaned = _re.sub(r",\s*([}\]])", r"\1", cleaned)
    cleaned = _re.sub(r'[\x00-\x1f]', ' ', cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        last_brace = cleaned.rfind("}")
        if last_brace > 0:
            candidate = cleaned[:last_brace + 1]
            depth = 0
            for c in candidate:
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
            if depth != 0:
                candidate += "}" * depth
            parsed = json.loads(candidate)
        else:
            raise

    return parsed, grounding_sources


def _call_gemini_text(prompt: str, api_key: str, timeout: int = 120) -> str:
    """Call Gemini and return raw text (for markdown report generation)."""
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 16384,
        },
    }).encode()

    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())

    text = result["candidates"][0]["content"]["parts"][0]["text"].strip()

    # Strip markdown code block wrappers
    if text.startswith("```markdown"):
        text = text[len("```markdown"):].strip()
    if text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    return text


# ---------------------------------------------------------------------------
# Phase 1: Competitor Discovery
# ---------------------------------------------------------------------------

def research_competitors(
    client: str,
    description: str,
    website_text: str,
    known_competitors: list[str],
    api_key: str,
    max_competitors: int = 15,
) -> dict:
    """Phase 1: Find true competitors using Gemini with Google Search grounding."""

    known_section = ""
    if known_competitors:
        known_section = f"\n**User-Provided Competitors (include and verify these):** {', '.join(known_competitors)}\nThese are competitors the user already knows about. Search for each one to get their website, description, and positioning. Include ALL of them in the output (in the appropriate tier). Only put them in not_competitors if they genuinely do NOT compete."

    website_section = ""
    if website_text:
        website_section = f"\n**Website Content (excerpt):**\n{website_text[:3000]}"

    prompt = f"""You are a competitive intelligence analyst specializing in startup and technology markets. Your job is to identify TRUE competitors for a company using current web research.

**Client:** {client}
**Description:** {description}
{website_section}
{known_section}

## TASK

Perform a thorough competitive analysis for {client}. This is a TWO-PART analysis:

### PART 1: Identify the client's capability clusters

First, understand WHAT {client} actually does by breaking their product into capability clusters. Common capability clusters in technology products include (but are not limited to):

For AI/research platforms:
- Persona & behavioral simulation (synthetic consumers, digital twins)
- AI-led conversational research (interviews, qualitative at scale)
- Trend intelligence / always-on signals (real-time monitoring)
- Synthetic panels (AI-generated respondents)
- Workflow automation & reporting (end-to-end research pipeline)

For other product types, identify the relevant capability clusters based on the product description.

Determine which clusters {client} operates in, and how central each cluster is to their product (primary vs secondary).

### PART 2: Find competitors per capability cluster

For EACH capability cluster the client operates in, search for companies that compete in that specific area. Then assess:

1. **Full-stack competitors** — Companies that compete across MULTIPLE of the same clusters (these are Tier 1 direct competitors)
2. **Cluster-specific competitors** — Companies strong in 1-2 of the same clusters (Tier 2 partial overlap)
3. **Behavioral substitutes** — What customers actually DO instead of using any product in this category (Tier 3)

## CRITICAL RULES

1. **Same Problem, Same Customer** — A true competitor solves the SAME core problem for the SAME target user. Not adjacent tools, not upstream/downstream.

2. **Decision-Layer vs Tool-Layer** — If {client} is a decision/intelligence product, don't list voice-synthesis, design, or avatar-generation tools as competitors — they're different product layers entirely.

3. **Category Precision** — Ask: "Would a customer choosing {client} also be evaluating this company?" If yes → competitor. If no → not a competitor.

4. **Include Newer/Smaller Players** — Don't just list the big obvious names. Include newer startups, stealth-mode companies, and emerging players. Search for "alternatives to {client}", "{client} competitors", and related queries.

5. **Search for EACH user-provided competitor** — If the user listed known competitors, search for each one individually to get accurate details. Include them unless they genuinely don't compete.

6. **Verify existence** — Every company must be a real, currently operating company with a real website. Don't hallucinate companies.

## OUTPUT FORMAT

Return ONLY valid JSON:
{{
  "client": "{client}",
  "category": "One-line description of what product category {client} is in",
  "core_problem": "The specific problem {client} solves",
  "capability_clusters": [
    {{
      "name": "Cluster name (e.g., Persona & behavioral simulation)",
      "description": "What this cluster covers",
      "client_strength": "primary|secondary",
      "client_approach": "How {client} addresses this cluster specifically"
    }}
  ],
  "competitors": [
    {{
      "name": "Company Name",
      "website": "https://example.com",
      "description": "2-3 sentence description: what they do, their core product, target customer",
      "tier": "direct|partial_overlap|behavioral_substitute",
      "tier_label": "Tier 1 — Direct Competitor|Tier 2 — Partial Overlap|Tier 3 — Behavioral Substitute",
      "capability_overlap": ["List which of the client's capability clusters this competitor also covers"],
      "overlap_count": 3,
      "why_competitor": "Specific reason — what problem overlap exists, would a buyer compare them?",
      "key_differentiator": "How they differ from {client} in approach, focus, or positioning",
      "competitive_strength": "What they do BETTER than {client} in their area of overlap",
      "competitive_weakness": "Where they fall short compared to {client}",
      "founded_year": "2020 or unknown",
      "estimated_stage": "pre_seed|seed|series_a|series_b|growth|public|unknown",
      "estimated_size": "1-10|11-50|51-200|201-500|500+|unknown"
    }}
  ],
  "not_competitors": [
    {{
      "name": "Company often confused as competitor",
      "reason": "Why NOT a true competitor — be specific: different layer, different problem, different customer",
      "what_they_actually_are": "What category/layer they belong to instead"
    }}
  ],
  "competitive_landscape_summary": {{
    "total_competitors": 10,
    "market_maturity": "early|growing|mature|consolidating",
    "competitive_intensity": "low|medium|high",
    "key_insight": "1-2 sentence summary of the competitive landscape — what's the strategic takeaway?",
    "whitespace": "Where is the opportunity that no competitor is addressing well?"
  }}
}}

IMPORTANT:
- Order competitors: Tier 1 first (sorted by overlap_count desc), then Tier 2, then Tier 3
- Include 2-5 entries in "not_competitors" — especially tool-layer companies that people commonly confuse as competitors
- Be specific and factual — use information from search results, not vague marketing language
- For each competitor, the capability_overlap array should ONLY contain clusters from the capability_clusters list
- overlap_count must match the length of capability_overlap
- competitive_strength and competitive_weakness should be honest and specific"""

    print("  Phase 1: Calling Gemini with Google Search grounding...")
    parsed, grounding_sources = _call_gemini(prompt, api_key, timeout=180)

    # Add grounding sources
    if grounding_sources:
        parsed["research_sources"] = grounding_sources

    # Ensure counts are accurate
    competitors = parsed.get("competitors", [])
    parsed["competitive_landscape_summary"] = parsed.get("competitive_landscape_summary", {})
    parsed["competitive_landscape_summary"]["total_competitors"] = len(competitors)

    return parsed


# ---------------------------------------------------------------------------
# Phase 2: TikTok Presence Research
# ---------------------------------------------------------------------------

def research_tiktok_presence(
    client: str,
    competitors: list[dict],
    api_key: str,
    client_description: str = "",
) -> dict:
    """Phase 2: Research TikTok presence for client and all competitors via Google Search."""

    competitor_names = [c["name"] for c in competitors]
    competitor_list = "\n".join(
        f"- {c['name']} ({c.get('website', 'unknown')})" for c in competitors
    )

    prompt = f"""You are a TikTok research analyst. Your job is to find the OFFICIAL TikTok account for each company listed below. This is critical — many companies use non-obvious handles.

For EACH company, find:
1. Their official TikTok handle
2. Follower count, total likes, number of videos
3. Bio/description and link in bio
4. Whether it's verified or clearly the official account
5. Notable/viral videos with URLs and view counts
6. Content strategy observations
7. Whether they run TikTok ads (search "[company] TikTok ads" or "[company] Spark Ads")

Also search for the client: **{client}** ({client_description})

**Companies to research:**
{competitor_list}

**SEARCH STRATEGY (CRITICAL — follow ALL steps for EACH company):**

Brand TikTok handles are often NOT the company name. You MUST search broadly:

1. **Search Google** for: "[company name] TikTok" and "[company name] TikTok account"
   - Look for the official handle in search results, social media links, press mentions

2. **Search Google** for: "site:tiktok.com [company name]"
   - This finds their actual TikTok profile page

3. **Check the company's website** ({', '.join(c.get('website', '') for c in competitors if c.get('website'))})
   - Look for TikTok social links in the footer, about page, or contact page
   - The website will have the EXACT handle they use

4. **Try ALL common handle patterns** — brands rarely use just their company name. Search for:
   - @companyname, @company.name, @company_name
   - @getcompanyname, @usecompanyname, @trycompanyname (VERY common for apps/fintech)
   - @companynameapp, @companynameofficial, @companynamehq
   - @companyname_official, @thecompanyname, @companyname.co
   - @companynameai (for AI companies)

   For example, a company may use @getbrand rather than @brand. This pattern is EXTREMELY common:
   - Example Brand → @examplebrand (but could also be @getexamplebrand)
   - Cash App → @cashapp
   - Example Credit → @examplecredit
   - Dave → @dave (banking app)

5. **Search for ads presence**: "[company name] TikTok ads" or "[company name] TikTok marketing"
   - Many fintech/app companies run heavy TikTok ad campaigns even without an organic account
   - Note if they have paid presence but no organic content

6. **Verify the account is REAL**: Check bio text, link in bio, content relevance, verified badge
   - If @companyname belongs to an unrelated person, note it and keep searching other patterns
   - The official account often has the company website in bio or link in bio

**DO NOT give up after checking just @companyname.** Most brands use prefixed handles (get, use, try, the, etc.).

Return ONLY valid JSON:
{{
  "research_date": "today's date",
  "client": {{
    "name": "{client}",
    "tiktok_handle": "@handle or null",
    "has_tiktok": true,
    "followers": 0,
    "total_likes": 0,
    "videos": 0,
    "bio": "bio text",
    "bio_link": "url or null",
    "presence_level": "strong|medium|weak|minimal|none",
    "notes": "Any observations about their TikTok strategy"
  }},
  "competitors": [
    {{
      "name": "Company Name",
      "tiktok_handle": "@handle or null",
      "has_tiktok": true,
      "followers": 0,
      "total_likes": 0,
      "videos": 0,
      "bio": "bio text or empty",
      "bio_link": "url or null",
      "is_official_account": true,
      "presence_level": "strong|medium|weak|minimal|none",
      "content_strategy": "Brief description of what they post, if anything",
      "notable_videos": [
        {{
          "url": "https://www.tiktok.com/@handle/video/...",
          "description": "What the video is about",
          "views": 0,
          "format": "interview|talking-head|skit|product-demo|other"
        }}
      ],
      "notes": "Observations — is this really their account? Any viral content? Active or dormant?",
      "also_checked": ["@other_handle (not found)", "@another (unrelated account)"]
    }}
  ],
  "summary": {{
    "total_analyzed": 10,
    "with_meaningful_presence": 1,
    "with_account_no_content": 3,
    "no_account": 6,
    "strongest_competitor": "Name — brief why",
    "key_insight": "Overall TikTok landscape assessment for this competitive category"
  }},
  "presence_ranking": [
    {{"rank": 1, "name": "Company", "handle": "@handle", "followers": 0, "total_likes": 0, "videos": 0, "level": "strong"}}
  ]
}}

**PRESENCE LEVEL CRITERIA:**
- strong: 1000+ followers AND regular posting (10+ videos) AND engagement (likes > followers)
- medium: 500+ followers OR notable engagement on some videos
- weak: Account exists with some content but very low engagement
- minimal: Account exists with 0-2 videos or <10 followers
- none: No account found after exhaustive search

**ADS PRESENCE:**
- If a company runs TikTok ads but has no organic account, note "ads_only" in the notes field
- If they have both organic and paid, note "organic + paid" in notes

**ALSO_CHECKED FIELD:**
- List ALL handle patterns you tried, including the prefixed variants (get, use, try, etc.)
- Example: ["@examplebrand (personal account)", "@getexamplebrand (FOUND - official)", "@useexamplebrand (not found)"]
- This documents the thoroughness of the search"""

    print("  Phase 2: Researching TikTok presence via Google Search...")
    parsed, grounding_sources = _call_gemini(prompt, api_key, timeout=180)

    if grounding_sources:
        parsed["tiktok_research_sources"] = grounding_sources

    return parsed


# ---------------------------------------------------------------------------
# Phase 3: Report Generation
# ---------------------------------------------------------------------------

def _summarize_data(data: dict, max_chars: int = 8000) -> str:
    """Summarize competitor data to fit within prompt limits, avoiding giant JSON dumps."""
    parts = []

    parts.append(f"Client: {data.get('client', 'Unknown')}")
    parts.append(f"Category: {data.get('category', '')}")
    parts.append(f"Core Problem: {data.get('core_problem', '')}")

    # Capability clusters — only include if there are 3+ clusters
    clusters = data.get("capability_clusters", [])
    if len(clusters) >= 3:
        parts.append("\nCapability Clusters:")
        for c in clusters:
            parts.append(f"  - {c['name']} [{c.get('client_strength', '')}]: {c.get('client_approach', '')[:150]}")

    # Competitors — summarize each concisely
    parts.append("\nCompetitors:")
    for comp in data.get("competitors", []):
        line = f"  - {comp['name']} ({comp.get('website', '')}) [{comp.get('tier_label', comp.get('tier', ''))}]"
        line += f"\n    {comp.get('description', '')[:200]}"
        if comp.get('why_competitor'):
            line += f"\n    Why: {comp['why_competitor'][:150]}"
        if comp.get('key_differentiator'):
            line += f"\n    Differentiator: {comp['key_differentiator'][:150]}"
        if comp.get('competitive_strength'):
            line += f"\n    Strength: {comp['competitive_strength'][:100]}"
        if comp.get('competitive_weakness'):
            line += f"\n    Weakness: {comp['competitive_weakness'][:100]}"
        parts.append(line)

    # Not competitors
    not_comps = data.get("not_competitors", [])
    if not_comps:
        parts.append("\nNot Competitors:")
        for nc in not_comps:
            parts.append(f"  - {nc['name']}: {nc.get('reason', '')[:150]}")

    # Landscape summary
    summary = data.get("competitive_landscape_summary", {})
    if summary:
        parts.append(f"\nLandscape: maturity={summary.get('market_maturity', '')}, "
                     f"intensity={summary.get('competitive_intensity', '')}")
        if summary.get("key_insight"):
            parts.append(f"  Insight: {summary['key_insight'][:200]}")
        if summary.get("whitespace"):
            parts.append(f"  Whitespace: {summary['whitespace'][:200]}")

    result = "\n".join(parts)
    return result[:max_chars]


def generate_report(
    client: str,
    competitor_data: dict,
    tiktok_data: dict | None,
    api_key: str,
) -> str:
    """Phase 3: Generate a markdown competitor analysis report."""

    # Summarize data instead of dumping raw JSON (avoids giant prompts and broken tables)
    context = _summarize_data(competitor_data)

    if tiktok_data:
        tiktok_lines = ["\nTikTok Presence:"]
        client_tt = tiktok_data.get("client", {})
        if client_tt:
            tiktok_lines.append(f"  Client (@{client_tt.get('tiktok_handle', 'none')}): "
                                f"{client_tt.get('followers', 0)} followers, "
                                f"{client_tt.get('total_likes', 0)} likes, "
                                f"{client_tt.get('videos', 0)} videos, "
                                f"level={client_tt.get('presence_level', 'none')}")

        for comp in tiktok_data.get("competitors", []):
            handle = comp.get("tiktok_handle") or "none"
            tiktok_lines.append(f"  {comp['name']} (@{handle}): "
                                f"{comp.get('followers', 0)} followers, "
                                f"{comp.get('total_likes', 0)} likes, "
                                f"{comp.get('videos', 0)} videos, "
                                f"level={comp.get('presence_level', 'none')}")
            if comp.get("content_strategy"):
                tiktok_lines.append(f"    Strategy: {comp['content_strategy'][:150]}")
            for vid in comp.get("notable_videos", [])[:2]:
                tiktok_lines.append(f"    Video: {vid.get('url', '')} ({vid.get('views', 0)} views, {vid.get('format', '')})")

        tt_summary = tiktok_data.get("summary", {})
        if tt_summary:
            tiktok_lines.append(f"  Summary: {tt_summary.get('with_meaningful_presence', 0)} with presence, "
                                f"{tt_summary.get('no_account', 0)} no account")
            if tt_summary.get("key_insight"):
                tiktok_lines.append(f"  Insight: {tt_summary['key_insight'][:200]}")

        context += "\n" + "\n".join(tiktok_lines)

    # Decide whether to include capability clusters section
    clusters = competitor_data.get("capability_clusters", [])
    has_multiple_clusters = len(clusters) >= 3

    cluster_section = ""
    if has_multiple_clusters:
        cluster_section = """
## Client Capability Clusters

Table showing what the client does:
| Cluster | Strength | Approach |

Keep the "Approach" column SHORT — max 1 sentence per row.
"""

    competitor_format = ""
    if has_multiple_clusters:
        competitor_format = """For each competitor:
- **[Name]** ([website])
  - 1-2 sentence description
  - Capability overlap: [which clusters they share with the client]
  - Why they compete
  - Key differentiator
  - Strength / Weakness (1 line each)"""
    else:
        competitor_format = """For each competitor:
- **[Name]** ([website])
  - 1-2 sentence description
  - Why they compete with the client
  - Key differentiator from the client
  - Strength / Weakness (1 line each)"""

    tiktok_sections = ""
    if tiktok_data:
        tiktok_sections = """
## Competitor TikTok Presence

Ranked table of ALL competitors:
| Rank | Company | Handle | Followers | Total Likes | Videos | Presence |

Keep table cells SHORT. No sentences in table cells — just data.
Include the client's own row at the bottom for comparison.

### Deep Dive: [Strongest Competitor on TikTok]

If any competitor has strong/medium TikTok presence:
- Profile: handle, bio, followers, videos
- Top videos with stats and URLs
- Content strategy: what they post and why it works
- Gap the client can exploit

If NO competitor has meaningful presence, state this as a whitespace opportunity (1-2 sentences, no table).
"""

    prompt = f"""Generate a Competitor Analysis Report in Markdown format.

**DATA:**
{context}

**REPORT STRUCTURE:**

# Competitor Analysis Report
Prepared for: {client}

## Executive Summary
2-3 short paragraphs: what the client does, how many competitors found, TikTok landscape overview, key strategic takeaway.
{cluster_section}
## True Competitors

### Tier 1 — Direct Competitors
{competitor_format}

### Tier 2 — Partial Overlap
Same format, briefer.

### Tier 3 — Behavioral Substitutes
1-2 sentences each.

## Not Competitors (Excluded)
Brief list: Company — why NOT a competitor (1 line each).
Only include if data is available.
{tiktok_sections}
## Competitive Landscape Summary

| Dimension | Assessment |
|-----------|------------|
| Market maturity | ... |
| Competitive intensity | ... |
| Key insight | ... |
| Whitespace opportunity | ... |

**FORMATTING RULES (CRITICAL):**
- Keep ALL table cells SHORT — max 20 words per cell. No paragraphs in tables.
- Use bullet points for longer descriptions, NOT table cells.
- No cell in any table should exceed 100 characters.
- Use actual data from the input — don't invent numbers or companies.
- Be specific and factual — cite follower counts, video stats.
- Direct, professional tone. No filler.
- Total report should be 800-1500 words, not longer.

Return ONLY the Markdown report."""

    print("  Phase 3: Generating competitor analysis report...")
    return _call_gemini_text(prompt, api_key, timeout=120)


# ---------------------------------------------------------------------------
# Console Output
# ---------------------------------------------------------------------------

def format_summary(result: dict) -> str:
    """Format a human-readable summary for console output."""
    lines = []
    client = result.get("client", "Unknown")
    category = result.get("category", "")
    core_problem = result.get("core_problem", "")

    lines.append(f"\n{'=' * 60}")
    lines.append(f"COMPETITOR RESEARCH: {client}")
    lines.append(f"{'=' * 60}")
    lines.append(f"Category: {category}")
    lines.append(f"Core Problem: {core_problem}")

    # Capability clusters
    clusters = result.get("capability_clusters", [])
    if clusters:
        lines.append(f"\nCapability Clusters ({len(clusters)}):")
        for c in clusters:
            strength = c.get("client_strength", "unknown")
            marker = "*" if strength == "primary" else " "
            lines.append(f"  {marker} {c['name']} [{strength}]")

    # Competitors by tier
    competitors = result.get("competitors", [])
    tier_groups = {"direct": [], "partial_overlap": [], "behavioral_substitute": []}
    for comp in competitors:
        tier = comp.get("tier", "unknown")
        if tier in tier_groups:
            tier_groups[tier].append(comp)

    tier_labels = {
        "direct": "TIER 1 — Direct Competitors",
        "partial_overlap": "TIER 2 — Partial Overlap",
        "behavioral_substitute": "TIER 3 — Behavioral Substitutes",
    }

    for tier_key, label in tier_labels.items():
        group = tier_groups[tier_key]
        if group:
            lines.append(f"\n{label} ({len(group)}):")
            for comp in group:
                overlap = comp.get("overlap_count", 0)
                website = comp.get("website", "")
                lines.append(f"  - {comp['name']} ({website}) [{overlap} cluster overlap]")
                lines.append(f"    {comp.get('description', '')[:100]}")

    # Not competitors
    not_comps = result.get("not_competitors", [])
    if not_comps:
        lines.append(f"\nNOT COMPETITORS ({len(not_comps)}):")
        for nc in not_comps:
            lines.append(f"  x {nc['name']}: {nc['reason'][:80]}")

    # Landscape summary
    summary = result.get("competitive_landscape_summary", {})
    if summary:
        lines.append(f"\nLANDSCAPE SUMMARY:")
        lines.append(f"  Market maturity: {summary.get('market_maturity', 'unknown')}")
        lines.append(f"  Competitive intensity: {summary.get('competitive_intensity', 'unknown')}")
        lines.append(f"  Key insight: {summary.get('key_insight', '')}")
        lines.append(f"  Whitespace: {summary.get('whitespace', '')}")

    lines.append(f"\n{'=' * 60}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Competitor Research — Find true competitors, research TikTok presence, generate report"
    )
    parser.add_argument("--client", required=True, help="Client/brand name")
    parser.add_argument("--description", required=True, help="Product/service description")
    parser.add_argument("--website", default=None, help="Client website URL")
    parser.add_argument("--competitors", default="", help="Comma-separated known competitor names (will be verified)")
    parser.add_argument("--max-competitors", type=int, default=15, help="Max competitors to find (default 15)")
    parser.add_argument("--tiktok-presence", action="store_true", help="Phase 2: Research TikTok presence for all competitors")
    parser.add_argument("--report", action="store_true", help="Phase 3: Generate markdown competitor analysis report")
    parser.add_argument("--report-output", default=None, help="Output path for markdown report (default: competitor_report.md)")
    parser.add_argument("--tiktok-output", default=None, help="Output path for TikTok presence JSON (default: competitors_tiktok_presence.json)")
    parser.add_argument("-o", "--output", default=None, help="Save competitor research JSON to file")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    known_competitors = [c.strip() for c in args.competitors.split(",") if c.strip()] if args.competitors else []

    website_text = ""
    if args.website:
        print(f"Fetching website: {args.website}")
        website_text = fetch_website(args.website)

    # Phase 1: Competitor Discovery
    print(f"Researching competitors for: {args.client} (max {args.max_competitors})")
    if known_competitors:
        print(f"  Known competitors to verify: {', '.join(known_competitors)}")

    result = research_competitors(
        args.client, args.description, website_text, known_competitors, api_key, args.max_competitors
    )

    # Print summary
    print(format_summary(result))

    # Save Phase 1 output
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2))
        print(f"\nPhase 1 saved to {args.output}")

    # Phase 2: TikTok Presence Research
    tiktok_data = None
    if args.tiktok_presence:
        competitors_list = result.get("competitors", [])
        if competitors_list:
            tiktok_data = research_tiktok_presence(
                args.client, competitors_list, api_key, args.description
            )

            # Merge TikTok data into main result
            result["tiktok_presence"] = tiktok_data

            # Save TikTok presence data
            tiktok_path = args.tiktok_output or (
                str(Path(args.output).parent / "competitors_tiktok_presence.json") if args.output else "competitors_tiktok_presence.json"
            )
            Path(tiktok_path).parent.mkdir(parents=True, exist_ok=True)
            Path(tiktok_path).write_text(json.dumps(tiktok_data, indent=2))
            print(f"\nPhase 2 (TikTok presence) saved to {tiktok_path}")

            # Print TikTok summary
            summary = tiktok_data.get("summary", {})
            print(f"\n  TikTok Presence Summary:")
            print(f"    Competitors with meaningful presence: {summary.get('with_meaningful_presence', 0)}")
            print(f"    Competitors with account, no content: {summary.get('with_account_no_content', 0)}")
            print(f"    No account: {summary.get('no_account', 0)}")
            if summary.get("strongest_competitor"):
                print(f"    Strongest: {summary['strongest_competitor']}")

            # Re-save main result with TikTok data merged
            if args.output:
                Path(args.output).write_text(json.dumps(result, indent=2))

    # Phase 3: Report Generation
    if args.report:
        report_md = generate_report(args.client, result, tiktok_data, api_key)

        report_path = args.report_output or (
            str(Path(args.output).parent / "competitor_report.md") if args.output else "competitor_report.md"
        )
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(report_md)
        print(f"\nPhase 3 (report) saved to {report_path}")

    if not args.output:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
