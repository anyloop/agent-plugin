#!/usr/bin/env python3
"""
Build the Social Content Research deck HTML from a single report_data.json.

Reads the consolidated report data, generates the platform content grids (with
diversity validation: ~10 contents per platform, max 3 per account, format mix),
fills every {{placeholder}} in templates/deck.html, and writes the final HTML.

Usage:
  uv run --project skills/social-content-research-report/runtime \
    skills/social-content-research-report/runtime/build_deck.py \
    --data example-app/report_data.json \
    -o example-app/social_content_research.html

Then render the PDF with the slide-pdf-generator skill:
  python3 skills/slide-pdf-generator/runtime/to_pdf.py \
    example-app/social_content_research.html example-app/social_content_research.pdf --wait 8
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "deck.html"

PLATFORM_PILL = {"tiktok": "TIKTOK", "instagram": "REELS", "youtube": "YT SHORTS"}

MAX_PER_ACCOUNT = 3
TARGET_PER_PLATFORM = 10


MIN_VIEWS_PREFERRED = 50_000
MIN_VIEWS_FLOOR = 10_000


def parse_metric(metric: str) -> int:
    """Parse '1.2M likes' / '37.6K views' / '854 views' into an int, 0 if unparseable."""
    m = re.search(r"([\d.,]+)\s*([KM]?)", str(metric), re.IGNORECASE)
    if not m:
        return 0
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0
    unit = m.group(2).upper()
    return int(n * (1_000_000 if unit == "M" else 1_000 if unit == "K" else 1))


def build_vid_grid(
    videos: list[dict], platform: str, *, enforce_engagement_floor: bool = True
) -> str:
    """Build a <div class="vid-grid vid-grid--N"> block from a list of video dicts.

    Each video dict: {url, thumb, handle, metric, format}
    """
    if not videos and not enforce_engagement_floor:
        return ('<div class="vid-empty">No brand or competitor content was found. '
                'The slot is open.</div>')
    if not videos:
        return ('<div class="vid-empty">No content in this niche clears the '
                '10K-view floor. The slot is open.</div>')
    n = min(len(videos), 5)
    pill = PLATFORM_PILL.get(platform, platform.upper())
    cards = []
    for v in videos[:5]:
        fmt = v.get("format", "")
        fmt_html = f'<div class="f">{fmt}</div>' if fmt else ""
        cards.append(
            f'    <a class="vid-card" href="{v["url"]}" target="_blank">\n'
            f'      <div class="vid-thumb"><div class="pf">{pill}</div>'
            f'<img src="{v["thumb"]}" alt="{v.get("handle", "")}"></div>\n'
            f'      <div class="vid-meta"><div class="h">{v.get("handle", "")}</div>'
            f'<div class="v">{v.get("metric", "")}</div>{fmt_html}</div>\n'
            f"    </a>"
        )
    return f'<div class="vid-grid vid-grid--{n}">\n' + "\n".join(cards) + "\n  </div>"


def build_ads_grid(ads: list[dict], cropped: bool = False) -> str:
    """Build the 3x2 Meta Ads grid. Each ad dict: {advertiser, thumb, ad_id?, query?}.

    Cards deep-link to the specific ad via ad_id; query/advertiser keyword
    search is only the fallback when no ad_id is present.
    """
    cls = "ads-grid ads-grid--cropped" if cropped else "ads-grid"
    cards = []
    for ad in ads[:6]:
        if ad.get("ad_id"):
            href = f"https://www.facebook.com/ads/library/?id={ad['ad_id']}"
        else:
            query = urllib.parse.quote(ad.get("query") or ad["advertiser"])
            href = (
                "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
                f"&country=US&q={query}&search_type=keyword_unordered"
            )
        cards.append(
            f'    <a class="ad-card" href="{href}" target="_blank">\n'
            f'      <div class="ad-thumb"><img src="{ad["thumb"]}" alt="{ad["advertiser"]} ad"></div>\n'
            f'      <div class="ad-label">{ad["advertiser"]}</div>\n'
            f"    </a>"
        )
    return f'<div class="{cls}">\n' + "\n".join(cards) + "\n  </div>"


def validate_platform(name: str, section: dict) -> list[str]:
    """Diversity checks for one platform: content count, per-account cap, format mix,
    and the minimum-engagement rule (>=50K preferred, >=10K hard floor)."""
    warnings = []
    videos = section.get("brand_videos", []) + section.get("creator_videos", [])
    # Minimum-engagement rule applies to ORGANIC CREATOR content only - the
    # brand/competitor side shows the top available regardless (weak numbers
    # there are themselves a finding).
    for v in section.get("creator_videos", []):
        n = parse_metric(v.get("metric", ""))
        if n and n < MIN_VIEWS_FLOOR:
            warnings.append(f"{name}: creator {v.get('handle', '?')} at {v.get('metric')} is below the 10K hard floor - remove it")
        elif n and n < MIN_VIEWS_PREFERRED:
            warnings.append(f"{name}: creator {v.get('handle', '?')} at {v.get('metric')} is in the 10K-50K fallback tier (prefer >=50K)")
    total = len(videos)
    if total < TARGET_PER_PLATFORM - 2:
        warnings.append(f"{name}: only {total} contents (target ~{TARGET_PER_PLATFORM})")
    accounts = Counter(v.get("handle", "?").lower().lstrip("@") for v in videos)
    for handle, count in accounts.items():
        if count > MAX_PER_ACCOUNT:
            warnings.append(
                f"{name}: @{handle} appears {count}x (max {MAX_PER_ACCOUNT} per account for diversity)"
            )
    formats = {v.get("format", "").lower() for v in videos if v.get("format")}
    if total >= 5 and len(formats) < 3:
        warnings.append(f"{name}: only {len(formats)} distinct content formats — aim for 3+")
    return warnings


def _plain(text: str) -> str:
    """Strip the light HTML markup (<strong>, quotes) used in deck copy for markdown output."""
    return re.sub(r"</?[a-z][^>]*>", "", str(text))


def build_markdown(data: dict) -> str:
    """Render report_data.json as a readable markdown version of the deck."""
    cover = data.get("cover", {})
    ex = data.get("exec", {})
    land = data.get("landscape", {})
    comp = data.get("competitive", {})
    platforms = data.get("platforms", {})
    ads = data.get("meta_ads", {})
    fmts = data.get("formats", {})
    conn = data.get("connect", {})

    lines = [
        f"# {cover.get('clientName', '')} — Social Content Research",
        f"*{_plain(cover.get('reportSubtitle', ''))}*",
        "",
        f"Prepared for {cover.get('clientContact', '')} · {cover.get('reportDate', '')}",
        "",
        "## Executive Summary",
        f"**{_plain(ex.get('execSummaryHeadline', ''))}**",
        "",
    ]
    for i in (1, 2, 3):
        lines.append(f"{i}. {_plain(ex.get(f'finding{i}', ''))}")
    lines += ["", f"**What this means for content:** {_plain(ex.get('execRecommendation', ''))}", ""]

    lines += [
        "## The Landscape",
        f"**{_plain(land.get('landscapeHeadline', ''))}**",
        "",
        _plain(land.get("landscapeCopy", "")),
        "",
        f"> **{land.get('heroStatNumber', '')}{land.get('heroStatSup', '')}** — {_plain(land.get('heroStatLabel', ''))} ({land.get('heroStatPlatforms', '')})",
        "",
        "## Competitive Field",
        "",
    ]
    for i in (1, 2, 3):
        lines.append(f"- **{comp.get(f'tier{i}Header', '')}: {comp.get(f'tier{i}Brand', '')}** [{comp.get(f'tier{i}Badge', '')}] — {_plain(comp.get(f'tier{i}Desc', ''))}")
    lines.append("")

    def vid_table(videos: list[dict]) -> list[str]:
        rows = ["| Account | Metric | Format | Link |", "|---|---|---|---|"]
        for v in videos:
            rows.append(f"| {v.get('handle', '')} | {v.get('metric', '')} | {v.get('format', '')} | [watch]({v.get('url', '')}) |")
        return rows

    for key, label in [("tiktok", "TikTok"), ("instagram", "Instagram Reels"), ("youtube", "YouTube Shorts")]:
        section = platforms.get(key, {})
        if not section:
            continue
        lines += [f"## {label} — Brand & Competitor", f"**{_plain(section.get('brand_headline', ''))}**", "", _plain(section.get("brand_intro", "")), ""]
        lines += vid_table(section.get("brand_videos", [])) + [""]
        lines += [f"## {label} — Organic Creators", f"**{_plain(section.get('creator_headline', ''))}**", "", _plain(section.get("creator_intro", "")), ""]
        lines += vid_table(section.get("creator_videos", [])) + [""]

    lines += ["## Meta Ads — Creative Reference", f"**{_plain(ads.get('headline', ''))}**", "", _plain(ads.get("intro", "")), ""]
    lines += ["| Advertiser | Ad |", "|---|---|"]
    for ad in ads.get("ads", []):
        if ad.get("ad_id"):
            href = f"https://www.facebook.com/ads/library/?id={ad['ad_id']}"
        else:
            href = ("https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
                    f"&country=US&q={urllib.parse.quote(ad.get('query') or ad.get('advertiser', ''))}&search_type=keyword_unordered")
        lines.append(f"| {ad.get('advertiser', '')} | [view ad]({href}) |")
    lines.append("")

    lines += ["## Content Format Patterns", f"**{_plain(fmts.get('formatsHeadline', ''))}**", ""]
    for i in (1, 2, 3, 4):
        lines.append(f"- **{fmts.get(f'format{i}Name', '')}** [{fmts.get(f'format{i}Tag', '')}] — {_plain(fmts.get(f'format{i}Desc', ''))}")
    lines.append("")

    lines += ["## About Adant AI", "", _plain(conn.get("aboutAdantCopy", "")), ""]
    for i in (1, 2, 3):
        if conn.get(f"case{i}_brand"):
            lines.append(f"- {conn[f'case{i}_brand']} — {conn.get(f'case{i}_stat', '')}: {conn.get(f'case{i}_url', '')}")
    lines += ["", f"{conn.get('connectContact', '')} · {conn.get('connectUrl', '')}", ""]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Social Content Research deck HTML")
    parser.add_argument("--data", required=True, help="Path to report_data.json")
    parser.add_argument("-o", "--output", required=True, help="Output HTML path")
    parser.add_argument("--md", help="Also write a markdown version of the report to this path")
    parser.add_argument("--strict", action="store_true", help="Fail on diversity warnings instead of just printing them")
    args = parser.parse_args()

    data = json.loads(Path(args.data).read_text())
    html = TEMPLATE_PATH.read_text()

    # ── Diversity validation ────────────────────────────────────────────
    warnings = []
    platforms = data.get("platforms", {})
    for key, label in [("tiktok", "TikTok"), ("instagram", "Instagram"), ("youtube", "YouTube Shorts")]:
        if key in platforms:
            warnings += validate_platform(label, platforms[key])
    if warnings:
        print("Diversity warnings:")
        for w in warnings:
            print(f"  ⚠ {w}")
        if args.strict:
            sys.exit(1)

    # ── Grid HTML blocks ────────────────────────────────────────────────
    grids = {}
    grid_keys = {
        "tiktok": ("ttBrandGridHtml", "ttCreatorGridHtml"),
        "instagram": ("igBrandGridHtml", "igCreatorGridHtml"),
        "youtube": ("ytBrandGridHtml", "ytCreatorGridHtml"),
    }
    for pkey, (brand_key, creator_key) in grid_keys.items():
        section = platforms.get(pkey, {})
        grids[brand_key] = build_vid_grid(
            section.get("brand_videos", []),
            pkey,
            enforce_engagement_floor=False,
        )
        grids[creator_key] = build_vid_grid(section.get("creator_videos", []), pkey)

    ads = data.get("meta_ads", {})
    grids["adsGridHtml"] = build_ads_grid(ads.get("ads", []), cropped=ads.get("cropped", False))

    # ── Flat placeholder map ────────────────────────────────────────────
    placeholders = {}
    placeholders.update(data.get("cover", {}))
    placeholders.update(data.get("exec", {}))
    placeholders.update(data.get("landscape", {}))
    placeholders.update(data.get("competitive", {}))
    for pkey, section in platforms.items():
        prefix = {"tiktok": "tt", "instagram": "ig", "youtube": "yt"}[pkey]
        placeholders[f"{prefix}BrandHeadline"] = section.get("brand_headline", "")
        placeholders[f"{prefix}BrandIntro"] = section.get("brand_intro", "")
        placeholders[f"{prefix}CreatorHeadline"] = section.get("creator_headline", "")
        placeholders[f"{prefix}CreatorIntro"] = section.get("creator_intro", "")
    placeholders["adsHeadline"] = ads.get("headline", "")
    placeholders["adsIntro"] = ads.get("intro", "")
    placeholders.update(data.get("formats", {}))
    placeholders.update(data.get("connect", {}))
    placeholders.update(grids)

    for k, v in placeholders.items():
        html = html.replace(f"{{{{{k}}}}}", str(v))

    leftover = sorted(set(re.findall(r"{{([a-zA-Z0-9_]+)}}", html)))
    if leftover:
        print(f"Warning: unfilled placeholders: {', '.join(leftover)}")
        if args.strict:
            sys.exit(1)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Deck HTML written to {out}")

    if args.md:
        md_out = Path(args.md)
        md_out.parent.mkdir(parents=True, exist_ok=True)
        md_out.write_text(build_markdown(data))
        print(f"Markdown report written to {md_out}")

    # Summary
    for key, label in [("tiktok", "TikTok"), ("instagram", "Instagram"), ("youtube", "YouTube Shorts")]:
        section = platforms.get(key, {})
        b, c = len(section.get("brand_videos", [])), len(section.get("creator_videos", []))
        print(f"  {label}: {b} brand/competitor + {c} organic creator = {b + c} contents")
    print(f"  Meta Ads: {len(ads.get('ads', []))} creatives")


if __name__ == "__main__":
    main()
