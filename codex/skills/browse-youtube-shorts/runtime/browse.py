#!/usr/bin/env python3
"""
YouTube Shorts Browse - headless Chrome research via CDP.

Public YouTube search, no login required. Extracts Shorts URLs, titles,
channels, view counts, and upload dates from YouTube's search results page.

Usage:
  uv run --project runtime runtime/browse.py "keyword1" "keyword2"
"""

import argparse
import asyncio
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

_skill_dir = Path(__file__).resolve().parent.parent
_project_root = _skill_dir.parent.parent
for env_file in [_skill_dir / ".env", _project_root / ".env", _project_root / ".env.production"]:
    if env_file.exists():
        load_dotenv(env_file)

from config import (
    CDP_PORT,
    DEFAULT_MIN_VIEWS,
    DEFAULT_RESULTS_PER_KEYWORD,
    DEFAULT_SORT_BY,
    DEFAULT_TIME_RANGE,
    MAX_RESULTS_PER_KEYWORD,
    SORT_BY_SP,
    SP_SHORTS_ONLY,
    TIME_RANGE_SP,
)

_runtime_data_dir = os.environ.get("ADANT_SOCIAL_DATA_DIR")
CDP_PROFILE_DIR = (
    Path(_runtime_data_dir) / "browse-youtube-shorts"
    if _runtime_data_dir
    else _skill_dir / "data"
) / "research-profile"
# Ad cards and Shorts are video-heavy, and headless Chrome still plays audio
# through the system output device. Mute every browser we launch and stop clips
# autoplaying at all, so research never makes noise over the user's work.
MUTED_ARGS = ("--mute-audio", "--autoplay-policy=document-user-activation-required")

_research_chrome_process = None


def _is_research_browser_running() -> bool:
    """Check if the research browser is running on CDP_PORT."""
    conn = http.client.HTTPConnection("127.0.0.1", CDP_PORT, timeout=2)
    try:
        conn.request("GET", "/json/version", headers={"Connection": "close"})
        response = conn.getresponse()
        response.read()
        return response.status == 200
    except Exception:
        return False
    finally:
        conn.close()


def _cdp_http(path: str, *, method: str = "GET", timeout: int = 10) -> bytes:
    """Call Chrome's local DevTools HTTP endpoint without urllib compatibility issues."""
    conn = http.client.HTTPConnection("127.0.0.1", CDP_PORT, timeout=timeout)
    try:
        conn.request(method, path, headers={"Connection": "close"})
        response = conn.getresponse()
        body = response.read()
        if response.status >= 400:
            raise RuntimeError(f"CDP HTTP {response.status}: {path}")
        return body
    finally:
        conn.close()


def _ensure_chrome_with_cdp() -> bool:
    """
    Launch a SEPARATE headless research browser. NEVER touches user's Chrome.

    - Uses port 9336 (user's Chrome uses default or 9222; other skills use 9333-9335)
    - Uses a dedicated profile directory
    - Runs headless - invisible, no window, no dock icon, no focus stealing
    """
    global _research_chrome_process

    if _is_research_browser_running():
        print("Research browser already running.")
        return True

    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        (CDP_PROFILE_DIR / lock_file).unlink(missing_ok=True)

    print("Launching headless research browser (your Chrome is untouched)...")

    _research_chrome_process = subprocess.Popen(
        [
            chrome_bin,
            "--headless=new",
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={CDP_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-gpu",
            "--window-size=1280,720",
            *MUTED_ARGS,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for i in range(15):
        time.sleep(1)
        if _is_research_browser_running():
            print("Research browser ready (headless).")
            return True
        if i == 5:
            print("  Waiting for research browser...")

    print("Failed to start research browser.", file=sys.stderr)
    return False


def _stop_research_browser() -> None:
    """Stop the research browser and clean up locks."""
    global _research_chrome_process
    if _research_chrome_process:
        _research_chrome_process.terminate()
        _research_chrome_process = None
    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        (CDP_PROFILE_DIR / lock_file).unlink(missing_ok=True)


def _build_search_url(keyword: str, time_range: str, sort_by: str) -> str:
    """Build a YouTube search URL. Shorts appear in carousels on normal SERPs —
    our JS filter to a[href*='/shorts/'] picks them up. The sp=EgQQARgC filter
    restricts to short-duration long-form videos (under 4 min), which is NOT
    what we want. Sort/time params omitted — YouTube's default relevance ranking
    surfaces the Shorts carousel, and our JS handles the filtering."""
    encoded_kw = urllib.parse.quote(keyword)
    return f"https://www.youtube.com/results?search_query={encoded_kw}"


JS_EXTRACT_SHORTS = r"""
(function() {
  function parseViews(s) {
    if (!s) return 0;
    s = s.toString().trim().replace(/,/g, '');
    var m = s.match(/([\d.]+)\s*([KkMmBb]?)/);
    if (!m) return 0;
    var n = parseFloat(m[1]);
    var u = (m[2] || '').toUpperCase();
    if (u === 'K') return Math.round(n * 1000);
    if (u === 'M') return Math.round(n * 1000000);
    if (u === 'B') return Math.round(n * 1000000000);
    return Math.round(n);
  }

  var videos = [];
  var seen = new Set();

  // YouTube Shorts cards render as ytm-shorts-lockup-view-model or similar custom elements
  var anchors = document.querySelectorAll('a[href*="/shorts/"]');
  anchors.forEach(function(a) {
    var href = a.getAttribute('href') || '';
    var m = href.match(/\/shorts\/([A-Za-z0-9_-]+)/);
    if (!m) return;
    var videoId = m[1];
    if (seen.has(videoId)) return;

    var card = a.closest('ytm-shorts-lockup-view-model')
            || a.closest('[class*="shortsLockup"]')
            || a.closest('ytd-video-renderer')
            || a.closest('ytd-reel-item-renderer')
            || a.closest('div[class*="lockup"]')
            || a.parentElement;
    if (!card) return;

    // Title: try aria-label on link first, then any h3/span text
    var title = '';
    var ariaLabel = a.getAttribute('aria-label') || '';
    if (ariaLabel) {
      title = ariaLabel;
    } else {
      var titleEl = card.querySelector('h3, [class*="title"], span[class*="Title"]');
      if (titleEl) title = titleEl.textContent.trim();
    }

    // Thumbnail
    var thumbEl = card.querySelector('img');
    var thumbnailUrl = thumbEl ? (thumbEl.getAttribute('src') || '') : '';

    // View count and upload date text - usually in metadata spans
    var viewsText = '';
    var viewsNumber = 0;
    var uploadDateText = '';
    var metaSpans = card.querySelectorAll('span, div');
    for (var i = 0; i < metaSpans.length; i++) {
      var txt = metaSpans[i].textContent.trim();
      if (!txt || txt.length > 60) continue;
      if (!viewsText && /views?$/i.test(txt)) {
        viewsText = txt;
        viewsNumber = parseViews(txt.replace(/\s*views?/i, ''));
      } else if (!viewsText && /^[\d.,]+[KMB]?$/i.test(txt)) {
        // Shorts often show just "1.2M" without the word "views"
        var n = parseViews(txt);
        if (n > viewsNumber) {
          viewsText = txt;
          viewsNumber = n;
        }
      }
      if (!uploadDateText && /(ago|second|minute|hour|day|week|month|year)/i.test(txt) && txt.length < 30) {
        uploadDateText = txt;
      }
    }

    // Channel name and URL - look for a channel link in the card
    var channelName = '';
    var channelUrl = '';
    var channelLinks = card.querySelectorAll('a[href*="/@"], a[href*="/channel/"]');
    for (var j = 0; j < channelLinks.length; j++) {
      var ch = channelLinks[j].getAttribute('href') || '';
      var name = channelLinks[j].textContent.trim();
      if (ch && (ch.indexOf('/@') === 0 || ch.indexOf('/channel/') === 0)) {
        channelUrl = 'https://www.youtube.com' + ch.split('?')[0];
        if (name && name.length < 100) channelName = name;
        break;
      }
    }

    seen.add(videoId);
    videos.push({
      video_id: videoId,
      url: 'https://www.youtube.com/shorts/' + videoId,
      title: title,
      channel_name: channelName,
      channel_url: channelUrl,
      views_text: viewsText,
      views_number: viewsNumber,
      upload_date_text: uploadDateText,
      thumbnail_url: thumbnailUrl,
      is_shorts: true
    });
  });

  return JSON.stringify(videos);
})()
""".strip()


async def _cdp_search_keyword(
    keyword: str,
    max_results: int,
    time_range: str,
    sort_by: str,
    screenshot_dir: Path | None = None,
) -> list[dict]:
    """Search YouTube Shorts for a keyword via direct CDP commands."""
    import websockets  # type: ignore

    search_url = _build_search_url(keyword, time_range, sort_by)
    print(f"    URL: {search_url}")

    # Close any existing YouTube search tabs to avoid stale data
    try:
        targets_raw = _cdp_http("/json/list", timeout=5)
        targets = json.loads(targets_raw)
        for tab in targets:
            tab_url = tab.get("url", "")
            if "youtube.com/results" in tab_url or "youtube.com/shorts" in tab_url:
                try:
                    _cdp_http(f"/json/close/{tab['id']}", timeout=3)
                except Exception:
                    pass
        await asyncio.sleep(1)
    except Exception:
        pass

    new_tab_raw = _cdp_http(
        f"/json/new?{urllib.parse.quote(search_url, safe='')}", method="PUT"
    )
    new_tab = json.loads(new_tab_raw)
    ws_url = new_tab["webSocketDebuggerUrl"]
    tab_id = new_tab["id"]

    all_videos: list[dict] = []
    msg_id = 1

    try:
        async with websockets.connect(ws_url, max_size=10_000_000) as ws:
            async def send_cmd(method: str, params: dict | None = None) -> dict:
                nonlocal msg_id
                msg = {"id": msg_id, "method": method}
                if params:
                    msg["params"] = params
                msg_id += 1
                await ws.send(json.dumps(msg))
                while True:
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                    if resp.get("id") == msg["id"]:
                        return resp

            print(f"    Searching: {keyword}")
            await asyncio.sleep(5)

            # Dismiss consent/cookie dialogs if present
            for _ in range(2):
                await send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Escape", "code": "Escape",
                    "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27,
                })
                await asyncio.sleep(0.4)
            await asyncio.sleep(1)

            stale_rounds = 0
            for scroll_round in range(5):
                await send_cmd("Runtime.evaluate", {
                    "expression": "window.scrollBy(0, 800)",
                })
                await asyncio.sleep(1)

                result = await send_cmd("Runtime.evaluate", {
                    "expression": JS_EXTRACT_SHORTS,
                    "returnByValue": True,
                })
                value = result.get("result", {}).get("result", {}).get("value", "[]")
                try:
                    videos = json.loads(value) if isinstance(value, str) else value
                    if isinstance(videos, list):
                        if len(videos) > len(all_videos):
                            all_videos = videos
                            print(f"    Round {scroll_round + 1}: {len(all_videos)} shorts found")
                            stale_rounds = 0
                        else:
                            stale_rounds += 1
                except (json.JSONDecodeError, TypeError):
                    pass

                if len(all_videos) >= max_results:
                    break
                if stale_rounds >= 2:
                    break

            if screenshot_dir is not None:
                try:
                    shot_result = await send_cmd("Page.captureScreenshot", {"format": "png"})
                    b64_data = shot_result.get("result", {}).get("data", "")
                    if b64_data:
                        import base64
                        screenshot_dir.mkdir(parents=True, exist_ok=True)
                        safe_name = urllib.parse.quote(keyword, safe="")[:80]
                        shot_path = screenshot_dir / f"{safe_name}.png"
                        shot_path.write_bytes(base64.b64decode(b64_data))
                        print(f"    Screenshot: {shot_path}")
                except Exception as e:
                    print(f"    Screenshot failed: {e}", file=sys.stderr)

    except Exception as e:
        print(f"    CDP error for '{keyword}': {e}", file=sys.stderr)
    finally:
        try:
            _cdp_http(f"/json/close/{tab_id}", timeout=5)
        except Exception:
            pass

    # Stamp each video with the search keyword
    for v in all_videos[:max_results]:
        v["search_keyword"] = keyword
    return all_videos[:max_results]


async def browse_youtube_shorts(
    keywords: list[str],
    max_results: int = DEFAULT_RESULTS_PER_KEYWORD,
    time_range: str = DEFAULT_TIME_RANGE,
    sort_by: str = DEFAULT_SORT_BY,
    max_total_seconds: int = 180,
    screenshot_dir: Path | None = None,
) -> dict[str, list[dict]]:
    """Search YouTube Shorts for each keyword via CDP. Returns per-keyword results."""
    if not _ensure_chrome_with_cdp():
        print("Cannot start research browser. Please ensure Chrome is installed.", file=sys.stderr)
        return {k: [] for k in keywords}

    global_start = time.time()

    def time_remaining() -> float:
        return max(0, max_total_seconds - (time.time() - global_start))

    print(f"Searching YouTube Shorts for {len(keywords)} keyword(s)... (max {max_total_seconds}s total)")
    results: dict[str, list[dict]] = {}

    for kw in keywords:
        remaining = time_remaining()
        if remaining < 10:
            print("    Time limit reached, skipping remaining keywords.", file=sys.stderr)
            results[kw] = []
            continue

        per_keyword_timeout = min(45, remaining)
        try:
            videos = await asyncio.wait_for(
                _cdp_search_keyword(kw, max_results, time_range, sort_by, screenshot_dir),
                timeout=per_keyword_timeout,
            )
            results[kw] = videos
        except asyncio.TimeoutError:
            print(f"    Timeout searching '{kw}', skipping.", file=sys.stderr)
            results[kw] = []
        except Exception as e:
            print(f"    Error searching '{kw}': {e}", file=sys.stderr)
            results[kw] = []

    # Deduplicate across keywords by video_id (keep first occurrence)
    seen_ids: set[str] = set()
    for kw in keywords:
        unique_for_kw: list[dict] = []
        for v in results.get(kw, []):
            vid = v.get("video_id")
            if not vid or vid in seen_ids:
                continue
            seen_ids.add(vid)
            unique_for_kw.append(v)
        results[kw] = unique_for_kw

    total = sum(len(v) for v in results.values())
    print(f"Done: {total} shorts collected across {len(keywords)} keyword(s)")
    return results


def mark_outliers(
    results: dict[str, list[dict]],
    min_views: int = DEFAULT_MIN_VIEWS,
) -> dict[str, list[dict]]:
    """Flag videos with views >= min_views as outliers. Returns same shape, mutated copies."""
    marked: dict[str, list[dict]] = {}
    for keyword, videos in results.items():
        out: list[dict] = []
        for v in videos:
            views = v.get("views_number") or 0
            is_outlier = isinstance(views, (int, float)) and views >= min_views
            out.append({**v, "is_outlier": bool(is_outlier)})
        marked[keyword] = out
    return marked


def format_results(results: dict[str, list[dict]]) -> str:
    """Format search results into a readable summary."""
    lines = []
    for keyword, videos in results.items():
        lines.append(f"\n## Keyword: \"{keyword}\" ({len(videos)} results)")
        lines.append("-" * 60)
        if not videos:
            lines.append("  No results found.")
            continue
        for i, v in enumerate(videos, 1):
            title = str(v.get("title", ""))[:80]
            channel = v.get("channel_name") or "unknown"
            views_text = v.get("views_text") or ""
            upload = v.get("upload_date_text") or ""
            url = v.get("url", "")
            outlier = " [OUTLIER]" if v.get("is_outlier") else ""

            meta_parts = [p for p in [views_text, upload] if p]
            meta_str = " | ".join(meta_parts)

            lines.append(f"  {i}. {title}{outlier}")
            lines.append(f"     {channel} | {meta_str}")
            if url:
                lines.append(f"     {url}")
            lines.append("")

    return "\n".join(lines)


def build_summary_report(
    results: dict[str, list[dict]],
    keywords: list[str],
    time_range: str,
    sort_by: str,
    min_views: int,
) -> dict:
    """Build a structured summary report from results."""
    total_videos = sum(len(v) for v in results.values())

    all_videos: list[dict] = []
    for _kw, videos in results.items():
        all_videos.extend(videos)

    outliers_sorted = sorted(
        [v for v in all_videos if v.get("is_outlier")],
        key=lambda v: v.get("views_number") or 0,
        reverse=True,
    )

    keyword_breakdown: dict[str, dict] = {}
    for keyword, videos in results.items():
        views = [v.get("views_number", 0) for v in videos if isinstance(v.get("views_number"), (int, float))]
        outlier_count = sum(1 for v in videos if v.get("is_outlier"))
        keyword_breakdown[keyword] = {
            "video_count": len(videos),
            "total_views": sum(views),
            "avg_views": sum(views) // len(views) if views else 0,
            "outlier_count": outlier_count,
        }

    report = {
        "search_keywords": keywords,
        "filters": {
            "time_range": time_range,
            "sort_by": sort_by,
            "min_views": min_views,
        },
        "summary": {
            "total_videos_found": total_videos,
            "keywords_searched": len(keywords),
            "keyword_breakdown": keyword_breakdown,
            "outliers_count": len(outliers_sorted),
        },
        "all_results": results,
        "outliers": outliers_sorted,
    }
    return report


def main():
    parser = argparse.ArgumentParser(
        description="Browse YouTube Shorts by keywords via headless Chrome CDP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run --project runtime runtime/browse.py "short drama"
  uv run --project runtime runtime/browse.py "short drama" "mini series" -n 20
  uv run --project runtime runtime/browse.py "AI tools" --time-range month --sort-by views
  uv run --project runtime runtime/browse.py "kpop" -o output/results.json
        """,
    )
    parser.add_argument("keywords", nargs="*", help="Keywords to search for")
    parser.add_argument(
        "-n",
        "--max-results",
        type=int,
        default=DEFAULT_RESULTS_PER_KEYWORD,
        help=f"Max results per keyword (default: {DEFAULT_RESULTS_PER_KEYWORD}, max: {MAX_RESULTS_PER_KEYWORD})",
    )
    parser.add_argument("-o", "--output", default=None, help="Save JSON report to file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument(
        "--min-views",
        type=int,
        default=DEFAULT_MIN_VIEWS,
        help=f"Minimum views for outlier detection (default: {DEFAULT_MIN_VIEWS:,})",
    )
    parser.add_argument(
        "--time-range",
        choices=list(TIME_RANGE_SP.keys()),
        default=DEFAULT_TIME_RANGE,
        help=f"Time range filter (default: {DEFAULT_TIME_RANGE})",
    )
    parser.add_argument(
        "--sort-by",
        choices=list(SORT_BY_SP.keys()),
        default=DEFAULT_SORT_BY,
        help=f"Sort order (default: {DEFAULT_SORT_BY})",
    )
    parser.add_argument(
        "--screenshot-dir",
        default=None,
        help="Directory to save per-keyword screenshots",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=180,
        help="Maximum total runtime in seconds (default: 180 = 3 minutes)",
    )

    args = parser.parse_args()

    if not args.keywords:
        parser.error("keywords are required")

    max_results = min(args.max_results, MAX_RESULTS_PER_KEYWORD)
    screenshot_dir = Path(args.screenshot_dir) if args.screenshot_dir else None

    print(f"YouTube Shorts Browse: {len(args.keywords)} keyword(s)")
    print(f"Filters: time_range={args.time_range}, sort_by={args.sort_by}, min_views={args.min_views:,}")
    print("Connecting to headless research Chrome via CDP...\n")

    results = asyncio.run(
        browse_youtube_shorts(
            keywords=args.keywords,
            max_results=max_results,
            time_range=args.time_range,
            sort_by=args.sort_by,
            max_total_seconds=args.max_time,
            screenshot_dir=screenshot_dir,
        )
    )

    results = mark_outliers(results, min_views=args.min_views)

    report = build_summary_report(
        results,
        args.keywords,
        time_range=args.time_range,
        sort_by=args.sort_by,
        min_views=args.min_views,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport saved to: {output_path}")
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(format_results(results))

    total = sum(len(v) for v in results.values())
    outliers_total = sum(1 for vs in results.values() for v in vs if v.get("is_outlier"))
    print(f"\nTotal: {total} shorts found across {len(args.keywords)} keyword(s)")
    print(f"Outliers ({args.min_views:,}+ views): {outliers_total}")


if __name__ == "__main__":
    main()
