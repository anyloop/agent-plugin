#!/usr/bin/env python3
"""
TikTok Research for Company
Takes company info and keywords, searches TikTok, and produces a research report.
Run with: uv run --project runtime runtime/research.py --company "Company Name" --keywords "kw1,kw2,kw3" [options]
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from config import (
    DEFAULT_OUTPUT_DIR,
    DEFAULT_RESULTS_PER_KEYWORD,
    DURATION_FILTER,
    PUBLISH_TIME,
    SORT_TYPE,
    LoginRequiredError,
    ValidationError,
)
from search_tiktok import SearchFilters, search_multiple_keywords


def parse_keywords(keywords_str: str) -> list[str]:
    """Parse comma-separated keywords string into a list."""
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    if not keywords:
        raise ValidationError("At least one keyword is required")
    return keywords


def build_research_report(
    company_name: str,
    company_description: str,
    industry: str,
    keywords: list[str],
    results: dict[str, list[dict]],
    filters: SearchFilters,
) -> dict:
    """Build a structured research report from search results."""
    total_videos = sum(len(v) for v in results.values())

    all_videos = []
    for keyword, videos in results.items():
        for video in videos:
            all_videos.append({**video, "search_keyword": keyword})

    top_by_views = sorted(
        [v for v in all_videos if v.get("view_count")],
        key=lambda v: v.get("view_count", 0),
        reverse=True,
    )[:10]

    top_by_likes = sorted(
        [v for v in all_videos if v.get("like_count")],
        key=lambda v: v.get("like_count", 0),
        reverse=True,
    )[:10]

    keyword_summary = {}
    for keyword, videos in results.items():
        total_views = sum(v.get("view_count", 0) for v in videos if v.get("view_count"))
        total_likes = sum(v.get("like_count", 0) for v in videos if v.get("like_count"))
        keyword_summary[keyword] = {
            "video_count": len(videos),
            "total_views": total_views,
            "total_likes": total_likes,
            "avg_views": total_views // len(videos) if videos else 0,
            "avg_likes": total_likes // len(videos) if videos else 0,
        }

    return {
        "report_date": datetime.now().isoformat(),
        "company": {
            "name": company_name,
            "description": company_description,
            "industry": industry,
        },
        "search_keywords": keywords,
        "filters": {
            "sort_by": filters.sort_by,
            "time_range": filters.time_range,
            "duration": filters.duration,
        },
        "summary": {
            "total_videos_found": total_videos,
            "keywords_searched": len(keywords),
            "keyword_breakdown": keyword_summary,
        },
        "top_videos_by_views": top_by_views,
        "top_videos_by_likes": top_by_likes,
        "all_results": results,
    }


def format_report_text(report: dict) -> str:
    """Format the research report as readable text."""
    lines = []
    company = report["company"]
    summary = report["summary"]
    filters = report.get("filters", {})

    lines.append("=" * 70)
    lines.append(f"TIKTOK RESEARCH REPORT: {company['name']}")
    lines.append(f"Date: {report['report_date'][:10]}")
    lines.append("=" * 70)

    if company.get("description"):
        lines.append(f"\nCompany: {company['description']}")
    if company.get("industry"):
        lines.append(f"Industry: {company['industry']}")

    lines.append(f"\nKeywords searched: {', '.join(report['search_keywords'])}")
    lines.append(f"Total videos found: {summary['total_videos_found']}")

    # Show active filters
    active_filters = []
    if filters.get("sort_by", "relevance") != "relevance":
        active_filters.append(f"Sort: {filters['sort_by']}")
    if filters.get("time_range", "all") != "all":
        active_filters.append(f"Time: {filters['time_range']}")
    if filters.get("duration", "all") != "all":
        active_filters.append(f"Duration: {filters['duration']}")
    if active_filters:
        lines.append(f"Filters: {' | '.join(active_filters)}")

    lines.append("\n## Keyword Performance")
    lines.append("-" * 50)
    for keyword, stats in summary["keyword_breakdown"].items():
        lines.append(f"  \"{keyword}\":")
        lines.append(f"    Videos: {stats['video_count']} | Avg Views: {stats['avg_views']:,} | Avg Likes: {stats['avg_likes']:,}")

    if report.get("top_videos_by_views"):
        lines.append("\n## Top Videos by Views")
        lines.append("-" * 50)
        for i, video in enumerate(report["top_videos_by_views"][:5], 1):
            views = video.get("view_count", 0)
            likes = video.get("like_count", 0)
            lines.append(f"  {i}. {video['title'][:70]}")
            lines.append(f"     @{video['uploader']} | {views:,} views | {likes:,} likes")
            lines.append(f"     Keyword: \"{video['search_keyword']}\"")
            lines.append(f"     {video['url']}")
            lines.append("")

    if report.get("top_videos_by_likes"):
        lines.append("\n## Top Videos by Likes")
        lines.append("-" * 50)
        for i, video in enumerate(report["top_videos_by_likes"][:5], 1):
            views = video.get("view_count", 0)
            likes = video.get("like_count", 0)
            lines.append(f"  {i}. {video['title'][:70]}")
            lines.append(f"     @{video['uploader']} | {views:,} views | {likes:,} likes")
            lines.append(f"     Keyword: \"{video['search_keyword']}\"")
            lines.append(f"     {video['url']}")
            lines.append("")

    lines.append("\n## All Results by Keyword")
    lines.append("-" * 50)
    for keyword, videos in report["all_results"].items():
        lines.append(f"\n### \"{keyword}\" ({len(videos)} results)")
        for i, video in enumerate(videos, 1):
            dur = ""
            if video.get("duration"):
                d = int(video["duration"])
                dur = f" | {d // 60}:{d % 60:02d}"
            views_str = f" | {video['view_count']:,} views" if video.get("view_count") else ""
            likes_str = f" | {video['like_count']:,} likes" if video.get("like_count") else ""
            lines.append(f"  {i}. {video['title'][:70]}")
            lines.append(f"     @{video['uploader']}{dur}{views_str}{likes_str}")
            lines.append(f"     {video['url']}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="TikTok research for a company")
    parser.add_argument("--company", required=True, help="Company name")
    parser.add_argument("--keywords", required=True, help="Comma-separated keywords to search")
    parser.add_argument("--description", default="", help="Brief company description")
    parser.add_argument("--industry", default="", help="Company industry/niche")
    parser.add_argument(
        "-n",
        "--max-results",
        type=int,
        default=DEFAULT_RESULTS_PER_KEYWORD,
        help=f"Max results per keyword (default: {DEFAULT_RESULTS_PER_KEYWORD})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help=f"Output directory for report files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Output only JSON report to stdout",
    )
    parser.add_argument(
        "--sort-by",
        choices=list(SORT_TYPE.keys()),
        default="relevance",
        help="Sort results by: relevance, likes, or date (default: relevance)",
    )
    parser.add_argument(
        "--time-range",
        choices=list(PUBLISH_TIME.keys()),
        default="all",
        help="Filter by publish time: all, day, week, month, 3months, 6months (default: all)",
    )
    parser.add_argument(
        "--duration",
        choices=list(DURATION_FILTER.keys()),
        default="all",
        help="Filter by duration: all, short (<1min), medium (1-5min), long (>5min) (default: all)",
    )

    args = parser.parse_args()

    try:
        keywords = parse_keywords(args.keywords)
    except ValidationError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    filters = SearchFilters(
        sort_by=args.sort_by,
        time_range=args.time_range,
        duration=args.duration,
    )

    print(f"Starting TikTok research for: {args.company}")
    print(f"Keywords: {', '.join(keywords)}")
    print(f"Max results per keyword: {args.max_results}")
    print()

    try:
        results = search_multiple_keywords(keywords, max_results_per_keyword=args.max_results, filters=filters)
    except LoginRequiredError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    report = build_research_report(
        company_name=args.company,
        company_description=args.description,
        industry=args.industry,
        keywords=keywords,
        results=results,
        filters=filters,
    )

    if args.json_only:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        sys.exit(0)

    print(format_report_text(report))

    output_dir = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = args.company.lower().replace(" ", "_")[:30]
    json_path = output_dir / f"research_{safe_name}_{timestamp}.json"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nJSON report saved to: {json_path}")


if __name__ == "__main__":
    main()
