#!/usr/bin/env python3
"""
TikTok Keyword Search
Searches TikTok for videos matching given keywords using the persistent login profile.

Navigates to TikTok search pages and intercepts API responses for reliable data extraction.
Run with: uv run --project runtime runtime/search_tiktok.py "keyword" [options]
"""

import argparse
import json
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass

from playwright.sync_api import BrowserContext, Page, Response, sync_playwright

from config import (
    API_PAGE_SIZE,
    COOKIES_PATH,
    DEFAULT_RESULTS_PER_KEYWORD,
    DURATION_FILTER,
    MAX_RESULTS_PER_KEYWORD,
    PROFILE_DIR,
    PUBLISH_TIME,
    SORT_TYPE,
    LoginRequiredError,
    SearchError,
    ValidationError,
)


@dataclass(frozen=True)
class SearchFilters:
    """Immutable search filter configuration."""

    sort_by: str = "relevance"  # relevance, likes, date
    time_range: str = "all"  # all, day, week, month, 3months, 6months
    duration: str = "all"  # all, short (<1min), medium (1-5min), long (>5min)

    def to_api_params(self) -> dict[str, int]:
        """Convert filters to TikTok API parameter values."""
        return {
            "sort_type": SORT_TYPE.get(self.sort_by, 0),
            "publish_time": PUBLISH_TIME.get(self.time_range, 0),
            "filter_duration": DURATION_FILTER.get(self.duration, 0),
        }


def validate_keyword(keyword: str) -> str:
    """Validate and normalize a search keyword."""
    keyword = keyword.strip()
    if not keyword:
        raise ValidationError("Keyword cannot be empty")
    if len(keyword) > 200:
        raise ValidationError(f"Keyword too long ({len(keyword)} chars, max 200)")
    return keyword


def _ensure_login() -> None:
    """Verify that a login profile exists, raise if not."""
    if not PROFILE_DIR.exists() or not any(PROFILE_DIR.iterdir()):
        raise LoginRequiredError(
            "No TikTok login found. Run 'uv run --project runtime runtime/login.py' first."
        )


def _parse_video_item(item: dict) -> dict:
    """Parse video data from TikTok API response item."""
    inner = item.get("item", item)
    author = inner.get("author", {})
    stats = inner.get("stats", {})
    video_info = inner.get("video", {})
    video_id = str(inner.get("id", ""))

    if isinstance(author, dict):
        unique_id = author.get("uniqueId", "") or author.get("unique_id", "")
    else:
        unique_id = str(author) if author else ""

    return {
        "id": video_id,
        "title": inner.get("desc", ""),
        "url": f"https://www.tiktok.com/@{unique_id}/video/{video_id}" if unique_id and video_id else "",
        "uploader": unique_id,
        "uploader_url": f"https://www.tiktok.com/@{unique_id}" if unique_id else "",
        "duration": video_info.get("duration") if isinstance(video_info, dict) else None,
        "view_count": stats.get("playCount") if isinstance(stats, dict) else None,
        "like_count": stats.get("diggCount") if isinstance(stats, dict) else None,
        "comment_count": stats.get("commentCount") if isinstance(stats, dict) else None,
        "share_count": stats.get("shareCount") if isinstance(stats, dict) else None,
        "description": inner.get("desc", ""),
        "thumbnail": (video_info.get("cover", "") or video_info.get("dynamicCover", ""))
        if isinstance(video_info, dict)
        else "",
        "upload_date": "",
    }


def _build_search_url(keyword: str, filters: SearchFilters) -> str:
    """Build TikTok search page URL with filters."""
    encoded = urllib.parse.quote(keyword)
    params = filters.to_api_params()
    url = f"https://www.tiktok.com/search?q={encoded}"
    if params["sort_type"]:
        url += f"&sort_type={params['sort_type']}"
    if params["publish_time"]:
        url += f"&publish_time={params['publish_time']}"
    if params["filter_duration"]:
        url += f"&filter_duration={params['filter_duration']}"
    return url


def _extract_videos_from_api_response(response_body: str) -> list[dict]:
    """Extract video items from a TikTok search API response body."""
    try:
        data = json.loads(response_body)
    except (json.JSONDecodeError, ValueError):
        return []

    items = data.get("item_list", []) or data.get("data", [])
    videos = []
    for item in items:
        video = _parse_video_item(item)
        if video.get("id"):
            videos.append(video)
    return videos


def _extract_videos_from_page_data(page: Page) -> list[dict]:
    """Extract video data from page's embedded JSON (fallback)."""
    try:
        html = page.content()
    except Exception:
        return []

    # Try multiple known data variable names
    patterns = [
        r'<script[^>]*id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(.*?)</script>',
        r'<script[^>]*id="SIGI_STATE"[^>]*>(.*?)</script>',
        r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL)
        if not match:
            continue
        try:
            data = json.loads(match.group(1))
            videos = _find_video_items_in_data(data)
            if videos:
                return videos
        except (json.JSONDecodeError, ValueError):
            continue

    return []


def _find_video_items_in_data(data: dict, depth: int = 0) -> list[dict]:
    """Recursively search for video item lists in nested data structures."""
    if depth > 8:
        return []

    # Check for direct item_list
    if isinstance(data, dict):
        item_list = data.get("item_list") or data.get("itemList") or data.get("items")
        if isinstance(item_list, list) and item_list:
            videos = []
            for item in item_list:
                if isinstance(item, dict):
                    video = _parse_video_item(item)
                    if video.get("id"):
                        videos.append(video)
            if videos:
                return videos

        # Recurse into dict values
        for value in data.values():
            if isinstance(value, (dict, list)):
                found = _find_video_items_in_data(value, depth + 1)
                if found:
                    return found

    elif isinstance(data, list):
        for item in data:
            if isinstance(item, (dict, list)):
                found = _find_video_items_in_data(item, depth + 1)
                if found:
                    return found

    return []


def _search_keyword(
    page: Page,
    keyword: str,
    max_results: int,
    filters: SearchFilters,
) -> list[dict]:
    """
    Search TikTok for a keyword by navigating to the search page.

    Intercepts API responses during page load and scrolling for data extraction.
    Falls back to embedded page data if API interception fails.
    """
    captured_videos: list[dict] = []
    seen_ids: set[str] = set()

    def handle_response(response: Response) -> None:
        """Capture video data from search API responses."""
        url = response.url
        if "api/search" not in url and "search/item" not in url:
            return
        try:
            body = response.text()
            videos = _extract_videos_from_api_response(body)
            for video in videos:
                vid = video.get("id", "")
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    captured_videos.append(video)
        except Exception:
            pass

    page.on("response", handle_response)

    search_url = _build_search_url(keyword, filters)

    try:
        page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(4)  # Wait for initial API responses
    except Exception as e:
        raise SearchError(f"Failed to load search page: {e}") from e

    # Scroll to trigger more results if we need more
    scroll_attempts = 0
    max_scrolls = max(0, (max_results - len(captured_videos)) // API_PAGE_SIZE + 1)

    while len(captured_videos) < max_results and scroll_attempts < max_scrolls:
        prev_count = len(captured_videos)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(2)
        scroll_attempts += 1

        # Stop scrolling if no new results after scroll
        if len(captured_videos) == prev_count:
            break

    page.remove_listener("response", handle_response)

    # Fallback: extract from embedded page data if API interception got nothing
    if not captured_videos:
        captured_videos = _extract_videos_from_page_data(page)

    return captured_videos[:max_results]


def _save_cookies(context: BrowserContext) -> None:
    """Save browser cookies for future sessions."""
    try:
        updated_cookies = context.cookies()
        if updated_cookies:
            COOKIES_PATH.parent.mkdir(parents=True, exist_ok=True)
            COOKIES_PATH.write_text(json.dumps(updated_cookies, indent=2))
    except Exception:
        pass


def _launch_context(p, headless: bool = True) -> BrowserContext:
    """Launch a persistent browser context using the login profile."""
    return p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=headless,
        viewport={"width": 1280, "height": 720},
        locale="en-US",
        channel="chrome",
        args=["--mute-audio", "--autoplay-policy=document-user-activation-required"],
    )


def search_tiktok(
    keyword: str,
    max_results: int = DEFAULT_RESULTS_PER_KEYWORD,
    filters: SearchFilters | None = None,
    headless: bool = True,
) -> list[dict]:
    """
    Search TikTok for videos matching a keyword.

    Uses the persistent browser profile from login.py.
    Returns a list of video metadata dicts.
    """
    keyword = validate_keyword(keyword)
    max_results = min(max_results, MAX_RESULTS_PER_KEYWORD)
    _ensure_login()

    if filters is None:
        filters = SearchFilters()

    with sync_playwright() as p:
        context = _launch_context(p, headless=headless)
        page = context.new_page()
        videos = _search_keyword(page, keyword, max_results, filters)

        _save_cookies(context)
        page.close()
        context.close()

    return videos


def search_multiple_keywords(
    keywords: list[str],
    max_results_per_keyword: int = DEFAULT_RESULTS_PER_KEYWORD,
    filters: SearchFilters | None = None,
    headless: bool = True,
) -> dict[str, list[dict]]:
    """
    Search TikTok for multiple keywords in a single browser session.

    Returns a dict mapping each keyword to its list of video results.
    """
    max_results_per_keyword = min(max_results_per_keyword, MAX_RESULTS_PER_KEYWORD)
    _ensure_login()

    if filters is None:
        filters = SearchFilters()

    results: dict[str, list[dict]] = {}

    with sync_playwright() as p:
        context = _launch_context(p, headless=headless)
        page = context.new_page()

        for keyword in keywords:
            try:
                keyword = validate_keyword(keyword)
                videos = _search_keyword(page, keyword, max_results_per_keyword, filters)
                results[keyword] = videos
                print(f"  '{keyword}': {len(videos)} videos found")
            except (SearchError, ValidationError) as e:
                print(f"  '{keyword}': ERROR - {e}", file=sys.stderr)
                results[keyword] = []

            time.sleep(2)  # Pause between searches

        _save_cookies(context)
        page.close()
        context.close()

    return results


def format_results_summary(results: dict[str, list[dict]]) -> str:
    """Format search results into a readable summary."""
    lines = []
    for keyword, videos in results.items():
        lines.append(f"\n## Keyword: \"{keyword}\" ({len(videos)} results)")
        lines.append("-" * 60)
        if not videos:
            lines.append("  No results found.")
            continue
        for i, video in enumerate(videos, 1):
            duration_str = ""
            if video.get("duration"):
                dur = int(video["duration"])
                duration_str = f" | {dur // 60}:{dur % 60:02d}"

            views = video.get("view_count")
            views_str = f" | {views:,} views" if views else ""

            likes = video.get("like_count")
            likes_str = f" | {likes:,} likes" if likes else ""

            lines.append(f"  {i}. {video['title'][:80]}")
            lines.append(f"     @{video['uploader']}{duration_str}{views_str}{likes_str}")
            lines.append(f"     {video['url']}")
            lines.append("")

    return "\n".join(lines)


def _parse_filters(args) -> SearchFilters:
    """Build SearchFilters from CLI args."""
    return SearchFilters(
        sort_by=args.sort_by,
        time_range=args.time_range,
        duration=args.duration,
    )


def main():
    parser = argparse.ArgumentParser(description="Search TikTok for videos by keyword")
    parser.add_argument("keywords", nargs="+", help="One or more keywords to search for")
    parser.add_argument(
        "-n",
        "--max-results",
        type=int,
        default=DEFAULT_RESULTS_PER_KEYWORD,
        help=f"Max results per keyword (default: {DEFAULT_RESULTS_PER_KEYWORD}, max: {MAX_RESULTS_PER_KEYWORD})",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Save JSON results to file (default: print summary to stdout)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of formatted summary",
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
    parser.add_argument(
        "--visible",
        action="store_true",
        help="Show browser window during search (useful for debugging or handling login prompts)",
    )

    args = parser.parse_args()
    filters = _parse_filters(args)

    filter_desc = []
    if filters.sort_by != "relevance":
        filter_desc.append(f"sort={filters.sort_by}")
    if filters.time_range != "all":
        filter_desc.append(f"time={filters.time_range}")
    if filters.duration != "all":
        filter_desc.append(f"duration={filters.duration}")

    filter_str = f" ({', '.join(filter_desc)})" if filter_desc else ""
    print(f"Searching TikTok for {len(args.keywords)} keyword(s){filter_str}...")

    try:
        results = search_multiple_keywords(
            args.keywords,
            max_results_per_keyword=args.max_results,
            filters=filters,
            headless=not args.visible,
        )
    except LoginRequiredError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        from pathlib import Path

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nResults saved to: {output_path}")
    elif args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(format_results_summary(results))

    total = sum(len(v) for v in results.values())
    print(f"\nTotal: {total} videos found across {len(args.keywords)} keyword(s)")


if __name__ == "__main__":
    main()
