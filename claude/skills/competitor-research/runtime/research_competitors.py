#!/usr/bin/env python3
"""Bounded competitor research with local browsing and report generation.

Only Phase 1 uses AdAnt's remote model for current web research. The request tells
the existing AdAnt agent not to invoke execution tools. Website fetching, TikTok
browsing, data shaping, and report rendering all run on the user's computer.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

_runtime_dir = Path(__file__).resolve().parent
_skill_dir = _runtime_dir.parent
_plugin_root = _skill_dir.parent.parent
sys.path.insert(0, str(_plugin_root / "local-server" / "src"))

from adant_local.inference import ask_adant  # noqa: E402
from local_report import generate_report  # noqa: E402
from local_tiktok import (  # noqa: E402
    research_tiktok_presence,
    research_tiktok_presence_from_capture,
)


def fetch_website(url: str) -> str:
    """Fetch and reduce the client website locally."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")
        text = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", text).strip()[:5_000]
    except Exception as exc:
        print(f"Warning: Could not fetch website locally: {exc}", file=sys.stderr)
        return ""


def _call_adant_json(prompt: str, title: str) -> tuple[dict, list[dict]]:
    parsed = ask_adant(prompt, title=title)
    if not isinstance(parsed, dict):
        raise RuntimeError("AdAnt research returned a non-object response.")
    sources = parsed.get("research_sources", [])
    return parsed, sources if isinstance(sources, list) else []


def research_competitors(
    client: str,
    description: str,
    website_text: str,
    known_competitors: list[str],
    max_competitors: int = 8,
) -> dict:
    """Find true competitors with one bounded, web-enabled inference turn."""
    if max_competitors < 1:
        raise ValueError("max_competitors must be at least 1")
    known_section = ", ".join(known_competitors) or "None provided"
    website_section = website_text[:3_000] or "Not provided"
    prompt = f"""Research true competitors for the following client using current web sources.

Client: {client}
Description: {description}
Known competitors to verify and prioritize: {known_section}
Client website excerpt: {website_section}

First identify the client's capability clusters. Then find at most {max_competitors}
competitors total across these tiers:
- direct: same core problem, customer, and multiple capability clusters;
- partial_overlap: overlaps in one or two material capabilities;
- behavioral_substitute: what the customer does instead.

Exclude adjacent tool-layer products a buyer would not evaluate against {client}.
Every named company must be real and currently operating. Prefer official company
pages as sources. This is a research-only turn: use web research and model synthesis
only. Do not invoke workspace, shell, computer, artifact, media, or other execution
tools. Return the JSON directly in the response.

Return ONLY valid JSON with this shape:
{{
  "client": "{client}",
  "category": "precise product category",
  "core_problem": "specific customer problem",
  "capability_clusters": [{{
    "name": "cluster", "description": "what it covers",
    "client_strength": "primary|secondary", "client_approach": "specific approach"
  }}],
  "competitors": [{{
    "name": "company", "website": "https://official.example",
    "description": "specific 2-3 sentence description",
    "tier": "direct|partial_overlap|behavioral_substitute",
    "tier_label": "Tier 1 — Direct Competitor|Tier 2 — Partial Overlap|Tier 3 — Behavioral Substitute",
    "capability_overlap": ["cluster names from capability_clusters"],
    "overlap_count": 1,
    "why_competitor": "why a buyer would compare it",
    "key_differentiator": "difference from {client}",
    "competitive_strength": "specific relative strength",
    "competitive_weakness": "specific relative weakness",
    "founded_year": "year or unknown",
    "estimated_stage": "pre_seed|seed|series_a|series_b|growth|public|unknown",
    "estimated_size": "1-10|11-50|51-200|201-500|500+|unknown"
  }}],
  "not_competitors": [{{
    "name": "often-confused company", "reason": "why it is not a competitor",
    "what_they_actually_are": "its actual category"
  }}],
  "competitive_landscape_summary": {{
    "total_competitors": 0, "market_maturity": "early|growing|mature|consolidating",
    "competitive_intensity": "low|medium|high", "key_insight": "strategic takeaway",
    "whitespace": "unmet opportunity"
  }},
  "research_sources": [{{"url": "https://source", "title": "source title"}}]
}}

IMPORTANT:
- Return AT MOST {max_competitors} entries in "competitors" — keep the strongest
  matches and stop there. Do not exceed this cap.
- Order direct before partial_overlap before behavioral_substitute, then by
  overlap_count descending.
- Include 2-5 entries in "not_competitors" — especially tool-layer companies that people commonly confuse as competitors
- Be specific and factual — use information from search results, not vague marketing language
- For each competitor, the capability_overlap array should ONLY contain clusters from the capability_clusters list
- overlap_count must match the length of capability_overlap
- competitive_strength and competitive_weakness should be honest and specific"""

    print("  Phase 1: Running bounded web research (execution stays local)...")
    parsed, sources = _call_adant_json(prompt, f"Competitors: {client}")
    competitors = parsed.get("competitors", [])
    if not isinstance(competitors, list):
        competitors = []
    tier_order = {"direct": 0, "partial_overlap": 1, "behavioral_substitute": 2}
    competitors = sorted(
        [item for item in competitors if isinstance(item, dict)],
        key=lambda item: (
            tier_order.get(item.get("tier"), 9),
            -int(item.get("overlap_count", 0) or 0),
        ),
    )[:max_competitors]
    for competitor in competitors:
        overlap = competitor.get("capability_overlap", [])
        competitor["overlap_count"] = len(overlap) if isinstance(overlap, list) else 0
    parsed["competitors"] = competitors
    summary = parsed.get("competitive_landscape_summary")
    if not isinstance(summary, dict):
        summary = {}
        parsed["competitive_landscape_summary"] = summary
    summary["total_competitors"] = len(competitors)
    if sources:
        parsed["research_sources"] = sources
    parsed["execution"] = {
        "remote": ["bounded web search and model synthesis"],
        "local": [
            "website fetch",
            "TikTok browser",
            "data shaping",
            "report rendering",
        ],
        "computer_policy": "local-only",
    }
    return parsed


def format_summary(result: dict) -> str:
    """Format a compact console summary."""
    lines = [
        f"\n{'=' * 60}",
        f"COMPETITOR RESEARCH: {result.get('client', 'Unknown')}",
        f"{'=' * 60}",
        f"Category: {result.get('category', '')}",
        f"Core Problem: {result.get('core_problem', '')}",
    ]
    clusters = result.get("capability_clusters", [])
    if clusters:
        lines.append(f"\nCapability Clusters ({len(clusters)}):")
        for cluster in clusters:
            marker = "*" if cluster.get("client_strength") == "primary" else " "
            lines.append(
                f"  {marker} {cluster.get('name', 'Unknown')} [{cluster.get('client_strength', 'unknown')}]"
            )
    groups = [
        ("direct", "TIER 1 — Direct Competitors"),
        ("partial_overlap", "TIER 2 — Partial Overlap"),
        ("behavioral_substitute", "TIER 3 — Behavioral Substitutes"),
    ]
    for tier, label in groups:
        competitors = [
            item for item in result.get("competitors", []) if item.get("tier") == tier
        ]
        if competitors:
            lines.append(f"\n{label} ({len(competitors)}):")
            for competitor in competitors:
                lines.append(
                    f"  - {competitor.get('name')} ({competitor.get('website', '')})"
                )
    landscape = result.get("competitive_landscape_summary", {})
    lines.extend(
        [
            "\nLANDSCAPE SUMMARY:",
            f"  Market maturity: {landscape.get('market_maturity', 'unknown')}",
            f"  Competitive intensity: {landscape.get('competitive_intensity', 'unknown')}",
            f"  Key insight: {landscape.get('key_insight', '')}",
            f"\n{'=' * 60}",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Competitor research with local TikTok capture and report rendering"
    )
    parser.add_argument("--client", default=None, help="Client/brand name")
    parser.add_argument(
        "--description", default="", help="Product/service description"
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Existing Phase 1 JSON; skips the remote discovery turn",
    )
    parser.add_argument("--website", default=None, help="Client website URL")
    parser.add_argument(
        "--competitors", default="", help="Comma-separated known competitors"
    )
    parser.add_argument(
        "--max-competitors",
        type=int,
        default=8,
        help="Maximum competitors (default: 8)",
    )
    parser.add_argument(
        "--tiktok-presence", action="store_true", help="Browse TikTok locally"
    )
    parser.add_argument(
        "--tiktok-input",
        default=None,
        help="Raw host-browser capture JSON; skips the Chrome/CDP runtime",
    )
    parser.add_argument(
        "--tiktok-max-time",
        type=int,
        default=300,
        help="Local TikTok time limit in seconds",
    )
    parser.add_argument(
        "--report", action="store_true", help="Render the Markdown report locally"
    )
    parser.add_argument(
        "--report-output", default=None, help="Markdown report output path"
    )
    parser.add_argument("--tiktok-output", default=None, help="TikTok JSON output path")
    parser.add_argument(
        "-o", "--output", default=None, help="Competitor JSON output path"
    )
    return parser.parse_args()


def _write_json(path: str, value: dict) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False))


def main() -> None:
    args = parse_args()
    if args.max_competitors < 1:
        raise SystemExit("--max-competitors must be at least 1")
    if args.input:
        result = json.loads(Path(args.input).read_text())
        if not isinstance(result, dict):
            raise SystemExit("--input must contain a JSON object")
        client = args.client or str(result.get("client", "")).strip()
        if not client:
            raise SystemExit("--client is required when --input has no client")
        print(f"Loading existing competitor research for: {client}")
    else:
        if not args.client:
            raise SystemExit("--client is required unless --input is provided")
        client = args.client
        known = [item.strip() for item in args.competitors.split(",") if item.strip()]
        website_text = ""
        if args.website:
            print(f"Fetching website locally: {args.website}")
            website_text = fetch_website(args.website)
        print(f"Researching competitors for: {client} (max {args.max_competitors})")
        result = research_competitors(
            client, args.description, website_text, known, args.max_competitors
        )
    print(format_summary(result))
    if args.output:
        _write_json(args.output, result)
        print(f"\nPhase 1 saved to {args.output}")

    tiktok_data = None
    if args.tiktok_presence or args.tiktok_input:
        if args.tiktok_input:
            capture = json.loads(Path(args.tiktok_input).read_text())
            if not isinstance(capture, dict):
                raise SystemExit("--tiktok-input must contain a JSON object")
            print("  Phase 2: Shaping Codex Browser capture locally...")
            tiktok_data = research_tiktok_presence_from_capture(
                client,
                result.get("competitors", []),
                capture,
                browser_backend="codex_in_app",
                client_website=args.website or "",
            )
        else:
            tiktok_data = research_tiktok_presence(
                client,
                result.get("competitors", []),
                args.description,
                args.website or "",
                args.tiktok_max_time,
            )
        result["tiktok_presence"] = tiktok_data
        tiktok_path = args.tiktok_output or (
            str(Path(args.output).parent / "competitors_tiktok_presence.json")
            if args.output
            else "competitors_tiktok_presence.json"
        )
        _write_json(tiktok_path, tiktok_data)
        print(f"\nPhase 2 (local TikTok presence) saved to {tiktok_path}")
        if args.output:
            _write_json(args.output, result)

    if args.report:
        print("  Phase 3: Rendering report locally...")
        report = generate_report(client, result, tiktok_data)
        report_path = args.report_output or (
            str(Path(args.output).parent / "competitor_report.md")
            if args.output
            else "competitor_report.md"
        )
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report)
        print(f"\nPhase 3 (local report) saved to {report_path}")

    if not args.output:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
