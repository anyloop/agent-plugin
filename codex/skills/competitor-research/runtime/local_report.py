"""Deterministic local Markdown rendering for competitor research."""

from __future__ import annotations


def _text(value: object, fallback: str = "Not available") -> str:
    text = str(value or "").strip()
    return text if text else fallback


def _cell(value: object, limit: int = 100) -> str:
    return _text(value).replace("|", "\\|").replace("\n", " ")[:limit]


def _number(value: object) -> str:
    return f"{int(value):,}" if isinstance(value, (int, float)) else "0"


def _competitor_block(competitor: dict) -> list[str]:
    website = competitor.get("website")
    heading = (
        f"**[{competitor.get('name', 'Unknown')}]({website})**"
        if website
        else f"**{competitor.get('name', 'Unknown')}**"
    )
    overlap = ", ".join(competitor.get("capability_overlap", []))
    return [
        f"- {heading} — {_text(competitor.get('description'))}",
        f"  - Why it competes: {_text(competitor.get('why_competitor'))}",
        *([f"  - Capability overlap: {overlap}"] if overlap else []),
        f"  - Differentiator: {_text(competitor.get('key_differentiator'))}",
        f"  - Strength: {_text(competitor.get('competitive_strength'))}",
        f"  - Weakness: {_text(competitor.get('competitive_weakness'))}",
    ]


def generate_report(
    client: str, competitor_data: dict, tiktok_data: dict | None
) -> str:
    """Render a factual report locally; never invokes a model or cloud computer."""
    competitors = competitor_data.get("competitors", [])
    landscape = competitor_data.get("competitive_landscape_summary", {})
    lines = [
        "# Competitor Analysis Report",
        "",
        f"Prepared for: **{client}**",
        "",
        "## Executive Summary",
        "",
        f"{client} operates in **{_text(competitor_data.get('category'))}**. The core problem is {_text(competitor_data.get('core_problem')).rstrip('.')}. This bounded review identified **{len(competitors)}** competitors.",
        "",
        _text(landscape.get("key_insight")),
        "",
    ]

    clusters = competitor_data.get("capability_clusters", [])
    if clusters:
        lines.extend(
            [
                "## Client Capability Clusters",
                "",
                "| Cluster | Strength | Approach |",
                "|---|---|---|",
            ]
        )
        for cluster in clusters:
            lines.append(
                f"| {_cell(cluster.get('name'))} | {_cell(cluster.get('client_strength'))} | {_cell(cluster.get('client_approach'))} |"
            )
        lines.append("")

    tiers = [
        ("direct", "Tier 1 — Direct Competitors"),
        ("partial_overlap", "Tier 2 — Partial Overlap"),
        ("behavioral_substitute", "Tier 3 — Behavioral Substitutes"),
    ]
    lines.extend(["## True Competitors", ""])
    for tier, title in tiers:
        lines.extend([f"### {title}", ""])
        group = [c for c in competitors if c.get("tier") == tier]
        if not group:
            lines.extend(["No entries identified in this tier.", ""])
            continue
        for competitor in group:
            lines.extend(_competitor_block(competitor))
        lines.append("")

    excluded = competitor_data.get("not_competitors", [])
    if excluded:
        lines.extend(["## Not Competitors (Excluded)", ""])
        for item in excluded:
            lines.append(
                f"- **{_text(item.get('name'))}** — {_text(item.get('reason'))}"
            )
        lines.append("")

    if tiktok_data:
        lines.extend(
            [
                "## Competitor TikTok Presence",
                "",
                "This section was captured on the user's local computer. “Not found” is not proof that an account does not exist.",
                "",
                "| Rank | Company | Handle | Followers | Likes | Videos | Presence |",
                "|---:|---|---|---:|---:|---:|---|",
            ]
        )
        ranked = tiktok_data.get("presence_ranking", [])
        for row in ranked:
            lines.append(
                f"| {row.get('rank', '')} | {_cell(row.get('name'))} | {_cell(row.get('handle'))} | {_number(row.get('followers'))} | {_number(row.get('total_likes'))} | {_number(row.get('videos'))} | {_cell(row.get('level'))} |"
            )
        own = tiktok_data.get("client", {})
        lines.append(
            f"| — | {_cell(own.get('name', client))} (client) | {_cell(own.get('tiktok_handle'))} | {_number(own.get('followers'))} | {_number(own.get('total_likes'))} | {_number(own.get('videos'))} | {_cell(own.get('presence_level'))} |"
        )
        lines.append("")
        if ranked:
            strongest_name = ranked[0].get("name")
            strongest = next(
                (
                    p
                    for p in tiktok_data.get("competitors", [])
                    if p.get("name") == strongest_name
                ),
                {},
            )
            lines.extend(
                [
                    f"### Deep Dive: {_text(strongest_name)}",
                    "",
                    f"- Profile: {_text(strongest.get('tiktok_handle'))}; {_number(strongest.get('followers'))} followers; {_number(strongest.get('videos'))} videos.",
                    f"- Content pattern: {_text(strongest.get('content_strategy'))}",
                ]
            )
            for video in strongest.get("notable_videos", [])[:3]:
                lines.append(
                    f"- [{_text(video.get('description'), 'Notable video')}]({video.get('url', '')}) — {_number(video.get('views'))} views"
                )
            lines.append("")

    lines.extend(
        [
            "## Competitive Landscape Summary",
            "",
            "| Dimension | Assessment |",
            "|---|---|",
            f"| Market maturity | {_cell(landscape.get('market_maturity'))} |",
            f"| Competitive intensity | {_cell(landscape.get('competitive_intensity'))} |",
            f"| Key insight | {_cell(landscape.get('key_insight'))} |",
            f"| Whitespace opportunity | {_cell(landscape.get('whitespace'))} |",
            "",
            "## Method Note",
            "",
            "Competitor discovery used a bounded AdAnt turn instructed to use web research only. Website fetching, TikTok browsing, data shaping, and this report rendering ran locally.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"
