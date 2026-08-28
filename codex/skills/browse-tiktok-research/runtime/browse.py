#!/usr/bin/env python3
"""
TikTok Browse - deterministic TikTok research through Chrome CDP.

Uses a persistent Chrome profile with CDP (Chrome DevTools Protocol).
On first run, you log into TikTok once. Subsequent runs reuse the session.

Two-phase approach:
  Phase 1: Collect video URLs and view counts from search results page
  Phase 2: Visit individual video pages to get likes, comments, duration, follower count

Usage:
  uv run --project runtime runtime/browse.py "keyword1" "keyword2"
  uv run --project runtime runtime/browse.py "keyword" --sort-by likes --time-range week
  uv run --project runtime runtime/browse.py --login  # Re-login to TikTok
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

# Load env files - check skill dir, then project root
_skill_dir = Path(__file__).resolve().parent.parent
_project_root = _skill_dir.parent.parent
for env_file in [_skill_dir / ".env", _project_root / ".env", _project_root / ".env.production"]:
    if env_file.exists():
        load_dotenv(env_file)

from config import (
    DEFAULT_DURATION,
    DEFAULT_MIN_LIKES,
    DEFAULT_MIN_VIEW_FOLLOWER_RATIO,
    DEFAULT_RESULTS_PER_KEYWORD,
    DEFAULT_SORT_BY,
    DEFAULT_TIME_RANGE,
    DURATION_FILTER,
    MAX_RESULTS_PER_KEYWORD,
    MAX_TOTAL_RESULTS,
    PUBLISH_TIME,
    SORT_TYPE,
    TOP_VIDEOS_LIMIT,
)

CDP_PORT = 9333  # Different port — never conflicts with user's Chrome
CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_runtime_data_dir = os.environ.get("ADANT_SOCIAL_DATA_DIR")
CDP_PROFILE_DIR = (
    Path(_runtime_data_dir) / "browse-tiktok-research"
    if _runtime_data_dir
    else _skill_dir / "data"
) / "research-profile"
TIKTOK_AUTH_COOKIES = ('sessionid', 'sessionid_ss', 'sid_tt')

# TikTok is wall-to-wall video and headless Chrome still plays audio
# through the system output device. Mute every browser we
# launch and stop clips autoplaying at all, so research never makes noise over
# the user's music, call or work.
MUTED_ARGS = ("--mute-audio", "--autoplay-policy=document-user-activation-required")

_research_chrome_process = None


def _foreground_visible_login_browser() -> None:
    """Bring the visible Chrome login window to the front on macOS."""
    if sys.platform != "darwin":
        return
    for _ in range(2):
        try:
            subprocess.run(
                ["osascript", "-e", 'tell application "Google Chrome" to activate'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass
        time.sleep(0.25)


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


async def _import_cookies_via_cdp() -> None:
    """Import TikTok cookies from user's Chrome into the research browser via CDP.

    Does NOT copy file — reads cookies from Chrome's sqlite DB and injects
    them via CDP Network.setCookie. This avoids file locking issues entirely.
    """
    import sqlite3
    import tempfile
    import shutil

    user_cookies_db = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "Cookies"
    if not user_cookies_db.exists():
        print("  No Chrome cookies found — you may need to log in manually.", file=sys.stderr)
        return

    # Copy the DB to a temp file (Chrome locks the original)
    tmp_db = Path(tempfile.mktemp(suffix=".db"))
    shutil.copy2(user_cookies_db, tmp_db)

    tiktok_cookies = []
    try:
        conn = sqlite3.connect(str(tmp_db))
        # Chrome encrypts cookie values on macOS, but we can get the metadata
        # The encrypted_value column needs Keychain access which is complex
        # Instead, just check if TikTok cookies exist — if not, user needs to login via --login
        cursor = conn.execute(
            "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%tiktok%'"
        )
        count = cursor.fetchone()[0]
        conn.close()

        if count > 0:
            print(f"  Found {count} TikTok cookies in your Chrome.")
        else:
            print("  No TikTok cookies found in Chrome — run with --login first.", file=sys.stderr)
    except Exception as e:
        print(f"  Could not read cookies: {e}", file=sys.stderr)
    finally:
        tmp_db.unlink(missing_ok=True)


def _ensure_chrome_with_cdp() -> bool:
    """
    Launch a SEPARATE headless research browser. NEVER touches user's Chrome.

    - Uses port 9333 (user's Chrome uses default or 9222)
    - Uses a FRESH temporary profile (no shared files, no lock conflicts)
    - Runs headless — invisible, no window, no dock icon, no focus stealing
    - User must run --login once to sign into TikTok in the research browser
    """
    global _research_chrome_process

    profile_owner_pid = _owned_research_browser_pid()
    if _is_research_browser_running():
        listener_pid = _cdp_listener_pid()
        if profile_owner_pid is None or listener_pid != profile_owner_pid:
            print(
                f"Port {CDP_PORT} is used by another browser; research was not started.",
                file=sys.stderr,
            )
            return False
        print("Research browser already running.")
        return True
    if profile_owner_pid is not None:
        print(
            "The TikTok sign-in browser is still open. Close it before starting research.",
            file=sys.stderr,
        )
        return False

    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up any stale lock files from previous crashed sessions
    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        (CDP_PROFILE_DIR / lock_file).unlink(missing_ok=True)

    print("Launching headless research browser (your Chrome is untouched)...")

    _research_chrome_process = subprocess.Popen(
        [
            CHROME_BIN,
            "--headless=new",
            f"--remote-debugging-port={CDP_PORT}",
            "--remote-allow-origins=*",
            f"--user-data-dir={CDP_PROFILE_DIR.resolve()}",
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
            if _cdp_listener_pid() == _research_chrome_process.pid:
                print("Research browser ready (headless).")
                return True
            print(
                f"Port {CDP_PORT} was claimed by another browser; research was not started.",
                file=sys.stderr,
            )
            _stop_research_browser()
            return False
        if i == 5:
            print("  Waiting for research browser...")

    print("Failed to start research browser.", file=sys.stderr)
    _stop_research_browser()
    return False


def _stop_research_browser() -> None:
    """Stop the research browser and clean up locks."""
    global _research_chrome_process
    process = _research_chrome_process
    if process is None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    _research_chrome_process = None
    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        (CDP_PROFILE_DIR / lock_file).unlink(missing_ok=True)


def _check_tiktok_login() -> bool | None:
    """True when the research profile holds a live TikTok session cookie.

    Reads only cookie names and expiries from Chrome's cookie DB; the values are
    encrypted and we never touch them. The previous check was "does the Cookies
    file exist", which is true after any browser launch, signed in or not, so a
    signed-out profile looked authenticated forever.
    """
    import shutil
    import sqlite3
    import tempfile

    source = CDP_PROFILE_DIR / "Default" / "Cookies"
    if not source.exists():
        return False
    tmp_dir = Path(tempfile.mkdtemp(prefix="tiktok-cookies-"))
    try:
        copy = tmp_dir / "Cookies"
        shutil.copy2(source, copy)  # Chrome keeps the original locked
        # Chrome stores expiry in microseconds since 1601-01-01.
        cutoff = int((time.time() + 11644473600) * 1_000_000)
        conn = sqlite3.connect(f"file:{copy}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT host_key FROM cookies WHERE name IN (?, ?, ?) "
                "AND length(encrypted_value) > 0 AND (is_persistent = 0 OR expires_utc > ?)",
                (*TIKTOK_AUTH_COOKIES, cutoff),
            ).fetchall()
        finally:
            conn.close()
        return any(host == "tiktok.com" or host.endswith(".tiktok.com") for (host,) in rows)
    except Exception:
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _command_has_exact_argument(command: str, argument: str) -> bool:
    """Match one complete process argument, not a profile or port prefix."""
    import re

    return re.search(rf"(?<!\S){re.escape(argument)}(?=\s|$)", command) is not None


def _owned_research_browser_pid() -> int | None:
    """Find Chrome only when it owns this skill's exact profile."""
    result = subprocess.run(
        ["ps", "-axo", "pid=,command="],
        capture_output=True,
        text=True,
        check=False,
    )
    expected_profile = f"--user-data-dir={CDP_PROFILE_DIR.resolve()}"
    for line in result.stdout.splitlines():
        value, separator, command = line.strip().partition(" ")
        if not separator:
            continue
        try:
            pid = int(value)
        except ValueError:
            continue
        if (
            command.startswith(f"{CHROME_BIN} ")
            and _command_has_exact_argument(command, expected_profile)
        ):
            return pid
    return None


def _cdp_listener_pid() -> int | None:
    """Return the PID listening on the fixed CDP port, if it can be verified."""
    result = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{CDP_PORT}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    for value in result.stdout.splitlines():
        try:
            return int(value.strip())
        except ValueError:
            continue
    return None


def _profile_is_available_for_login() -> bool:
    """Never interrupt an active research or sign-in browser."""
    return _owned_research_browser_pid() is None


def _launch_visible_login_browser(url: str) -> None:
    """Launch a foreground Chrome instance that cannot hide in an existing app."""
    browser_args = [
        f"--user-data-dir={CDP_PROFILE_DIR.resolve()}",
        "--no-first-run",
        "--no-default-browser-check",
        *MUTED_ARGS,
        "--new-window",
        "--start-maximized",
        url,
    ]
    if sys.platform == "darwin":
        subprocess.run(
            ["open", "-na", "Google Chrome", "--args", *browser_args],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _foreground_visible_login_browser()
        return

    subprocess.Popen(
        [CHROME_BIN, *browser_args],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def login_to_tiktok() -> None:
    """Open a VISIBLE research browser for TikTok login.

    Launches a separate Chrome window (not headless) using the research profile
    so the user can log into TikTok. The session persists in the research profile
    for future headless runs. The user's main Chrome is NOT affected.
    """
    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    if not _profile_is_available_for_login():
        print(
            "A TikTok research or sign-in browser is already open; close it before retrying.",
            file=sys.stderr,
        )
        return

    print("Opening research browser for TikTok login...")
    print("(This is a SEPARATE browser — your main Chrome is not affected)")
    print("The window is muted and should move to the foreground.")
    print("Log in to TikTok, then close this browser window.")

    _launch_visible_login_browser("https://www.tiktok.com/login")

    print("\nOnce logged in, close the research browser and run searches:")
    print('  uv run --project runtime runtime/browse.py "your keyword"')


# ---------------------------------------------------------------------------
# Phase 1: Search and collect basic video info from search results
# ---------------------------------------------------------------------------

def _build_search_task(
    keywords: list[str],
    max_results: int,
    sort_by: str = "relevance",
    time_range: str = "all",
    duration: str = "all",
) -> str:
    """Build a task prompt for Phase 1 - collecting videos from search results."""
    # Build URL query parameters for filters (avoid clicking UI buttons)
    from config import SORT_TYPE, PUBLISH_TIME, DURATION_FILTER

    url_params = []
    if sort_by != "relevance":
        url_params.append(f"sort_type={SORT_TYPE.get(sort_by, 0)}")
    if time_range != "all":
        url_params.append(f"publish_time={PUBLISH_TIME.get(time_range, 0)}")
    if duration != "all":
        url_params.append(f"duration={DURATION_FILTER.get(duration, 0)}")
    filter_query = "&" + "&".join(url_params) if url_params else ""

    keywords_list = "\n".join(f'  - "{k}"' for k in keywords)

    js_extract = r"""(function() {
  function parseCount(s) {
    if (!s) return 0;
    s = s.toString().trim().replace(/,/g, '');
    var m = s.match(/^([\d.]+)\s*([KkMmBb]?)$/);
    if (!m) return parseInt(s, 10) || 0;
    var n = parseFloat(m[1]);
    var u = (m[2] || '').toUpperCase();
    if (u === 'K') return Math.round(n * 1000);
    if (u === 'M') return Math.round(n * 1000000);
    if (u === 'B') return Math.round(n * 1000000000);
    return Math.round(n);
  }
  var videos = [];
  var seen = new Set();
  // Find all links that contain /video/ with a numeric ID
  document.querySelectorAll('a[href*="/video/"]').forEach(function(a) {
    var href = a.href;
    var m = href.match(/(https:\/\/www\.tiktok\.com\/@[^\/]+\/video\/\d+)/);
    if (!m) return;
    var url = m[1];
    if (seen.has(url)) return;
    seen.add(url);
    // Walk up to find the card container
    var card = a.closest('[class*="DivItemContainer"], [class*="video-feed-item"], [class*="search-card"], div[data-e2e]') || a.parentElement?.parentElement?.parentElement;
    var title = '';
    var uploader = '';
    var viewCount = 0;
    if (card) {
      // Try to find description text
      var descEl = card.querySelector('[data-e2e="search-card-desc"], [class*="SpanText"], [class*="video-desc"], a[title]');
      if (descEl) title = (descEl.textContent || descEl.getAttribute('title') || '').trim().substring(0, 200);
      // Like count from search results (TikTok shows likes on thumbnails, not views)
      var likeEl = card.querySelector('[data-e2e="search-card-like-container"] strong, [class*="video-count"], [class*="SpanCount"]');
      if (likeEl) viewCount = parseCount(likeEl.textContent);
    }
    // Extract uploader from URL
    var um = url.match(/@([^\/]+)/);
    if (um) uploader = um[1];
    if (!title) {
      var titleEl = a.querySelector('[title]') || a;
      title = (titleEl.getAttribute('title') || titleEl.textContent || '').trim().substring(0, 200);
    }
    videos.push({url: url, title: title, uploader: uploader, like_count: viewCount});
  });
  return JSON.stringify(videos);
})()"""

    return f"""You are a TikTok research assistant. For each keyword, navigate to the search page, run a JavaScript snippet to extract video data, and save results.

KEYWORDS TO SEARCH (one at a time):
{keywords_list}

STEPS FOR EACH KEYWORD:
1. Navigate to https://www.tiktok.com/search/video?q=<keyword>{filter_query} (URL-encode the keyword)
2. Wait 5 seconds for results to load
3. If a login modal or popup appears, close it (click X or press Escape)
4. Scroll down 2-3 times slowly (window.scrollBy(0, 800)) with 2-second pauses to load more results
5. Run this JavaScript using the `evaluate` action to extract all video data:

{js_extract}

6. The JavaScript returns a JSON array of videos. Parse it.
7. Keep up to {max_results} videos per keyword.
8. Move to the next keyword and repeat.

AFTER ALL KEYWORDS:
Save the combined results to a file called "results.json" using write_file with this format:
{{
  "results": {{
    "keyword1": [
      {{"url": "https://www.tiktok.com/@user/video/123", "title": "...", "uploader": "user", "like_count": 12345}}
    ]
  }}
}}
Then call done.

IMPORTANT:
- Use the EXACT JavaScript above with `evaluate` — do not try to read the DOM manually.
- If the JavaScript returns an empty array, scroll down more and run it again.
- BE FAST. Do not over-analyze. Extract and move on.
"""


# ---------------------------------------------------------------------------
# Phase 2: Visit individual video pages for detailed metrics
# ---------------------------------------------------------------------------

JS_EXTRACT_VIDEO_DETAIL = r"""
(function() {
  function parseCount(s) {
    if (!s) return null;
    s = s.toString().trim().replace(/,/g, '');
    var m = s.match(/^([\d.]+)\s*([KkMmBb]?)$/);
    if (!m) return parseInt(s, 10) || null;
    var n = parseFloat(m[1]);
    var u = (m[2] || '').toUpperCase();
    if (u === 'K') return Math.round(n * 1000);
    if (u === 'M') return Math.round(n * 1000000);
    if (u === 'B') return Math.round(n * 1000000000);
    return Math.round(n);
  }
  var d = {};
  // Title/description
  var descEl = document.querySelector('[data-e2e="browse-video-desc"], [data-e2e="video-desc"], h1[data-e2e], [class*="SpanText"]');
  d.title = descEl ? descEl.textContent.trim().substring(0, 300) : null;
  // Engagement metrics from strong[data-e2e] elements
  var strongs = document.querySelectorAll('strong[data-e2e]');
  strongs.forEach(function(el) {
    var key = el.getAttribute('data-e2e') || '';
    var val = parseCount(el.textContent);
    if (key.includes('like')) d.like_count = val;
    else if (key.includes('comment')) d.comment_count = val;
    else if (key.includes('share')) d.share_count = val;
    else if (key.includes('collect') || key.includes('save') || key.includes('undefined')) d.save_count = val;
  });
  // Also try spans with data-e2e for metrics (TikTok varies layout)
  document.querySelectorAll('span[data-e2e]').forEach(function(el) {
    var key = el.getAttribute('data-e2e') || '';
    var val = parseCount(el.textContent);
    if (val === null) return;
    if (key.includes('like') && !d.like_count) d.like_count = val;
    else if (key.includes('comment') && !d.comment_count) d.comment_count = val;
    else if (key.includes('share') && !d.share_count) d.share_count = val;
  });
  // Follower count — check author info section
  var followerEl = document.querySelector('[data-e2e="followers-count"]');
  if (followerEl) d.follower_count = parseCount(followerEl.textContent);
  // Also try the author link area for follower count
  if (!d.follower_count) {
    var authorInfo = document.querySelector('[class*="AuthorInfo"], [class*="author-card"], [data-e2e="browse-user-info"]');
    if (authorInfo) {
      var spans = authorInfo.querySelectorAll('strong, span');
      for (var i = 0; i < spans.length; i++) {
        var txt = spans[i].textContent.trim();
        var parent = spans[i].parentElement;
        var parentText = parent ? parent.textContent.toLowerCase() : '';
        if (parentText.includes('follower')) {
          d.follower_count = parseCount(txt);
          break;
        }
      }
    }
  }
  // View count — try multiple selectors
  var viewEl = document.querySelector('[data-e2e="video-view-count"], [data-e2e*="view"], [class*="view-count"]');
  if (viewEl) d.view_count = parseCount(viewEl.textContent);
  // Duration from video element
  var videoEl = document.querySelector('video');
  if (videoEl && videoEl.duration && isFinite(videoEl.duration)) {
    d.duration = Math.round(videoEl.duration);
  }
  // Music/sound info
  var musicEl = document.querySelector('[data-e2e="browse-music"], [data-e2e="video-music"], a[href*="/music/"]');
  if (musicEl) d.music = musicEl.textContent.trim().substring(0, 100);
  // Hashtags
  var tags = [];
  document.querySelectorAll('a[href*="/tag/"], a[data-e2e="search-common-link"]').forEach(function(a) {
    var tag = a.textContent.trim();
    if (tag && tag.startsWith('#')) tags.push(tag);
  });
  if (tags.length > 0) d.hashtags = tags;
  // Upload date from page (often in a span or time element)
  var dateEl = document.querySelector('span[data-e2e="browser-nickname"] + span, time, [class*="SpanOtherInfos"]');
  if (dateEl) {
    var dateText = dateEl.textContent.trim();
    if (dateText.match(/\d{1,2}[-\/]\d{1,2}|\d{4}/)) d.upload_date = dateText;
  }
  // Try SIGI_STATE / rehydration data for accurate metrics
  try {
    var scripts = document.querySelectorAll('script[id="__UNIVERSAL_DATA_FOR_REHYDRATION__"], script[id="SIGI_STATE"]');
    for (var si = 0; si < scripts.length; si++) {
      var raw = JSON.parse(scripts[si].textContent);
      // Navigate to video detail data
      var itemModule = raw.__DEFAULT_SCOPE__ && raw.__DEFAULT_SCOPE__['webapp.video-detail'];
      var itemInfo = itemModule && itemModule.itemInfo && itemModule.itemInfo.itemStruct;
      if (!itemInfo) {
        // Try alternate path
        var keys = Object.keys(raw);
        for (var ki = 0; ki < keys.length; ki++) {
          var val = raw[keys[ki]];
          if (val && val.itemInfo && val.itemInfo.itemStruct) {
            itemInfo = val.itemInfo.itemStruct;
            break;
          }
        }
      }
      if (itemInfo) {
        var stats = itemInfo.stats || {};
        if (stats.playCount) d.view_count = stats.playCount;
        if (stats.diggCount) d.like_count = stats.diggCount;
        if (stats.commentCount) d.comment_count = stats.commentCount;
        if (stats.shareCount) d.share_count = stats.shareCount;
        if (stats.collectCount) d.save_count = stats.collectCount;
        var author = itemInfo.author || {};
        if (author.followerCount) d.follower_count = author.followerCount;
        if (author.heartCount) d.author_total_likes = author.heartCount;
        if (author.videoCount) d.author_video_count = author.videoCount;
        var videoData = itemInfo.video || {};
        if (videoData.duration) d.duration = videoData.duration;
        if (itemInfo.desc) d.title = itemInfo.desc.substring(0, 300);
        if (itemInfo.createTime) d.upload_timestamp = itemInfo.createTime;
        break;
      }
    }
  } catch(e) {}
  return JSON.stringify(d);
})()
""".strip()


async def _cdp_get_video_detail(video_url: str) -> dict:
    """Visit a single video page via CDP and extract all available metrics."""
    import websockets  # type: ignore

    # Create a new tab
    try:
        new_tab_raw = _cdp_http(
            f"/json/new?{urllib.parse.quote(video_url, safe='')}", method="PUT"
        )
    except Exception as e:
        return {"error": str(e)}

    new_tab = json.loads(new_tab_raw)
    ws_url = new_tab["webSocketDebuggerUrl"]
    tab_id = new_tab["id"]
    detail = {}

    try:
        async with websockets.connect(ws_url, max_size=10_000_000) as ws:
            msg_id = 1

            async def send_cmd(method: str, params: dict | None = None) -> dict:
                nonlocal msg_id
                msg = {"id": msg_id, "method": method}
                if params:
                    msg["params"] = params
                msg_id += 1
                await ws.send(json.dumps(msg))
                while True:
                    resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                    if resp.get("id") == msg["id"]:
                        return resp

            # Wait for page to load
            await asyncio.sleep(5)

            # Close any modals
            for _ in range(2):
                await send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Escape", "code": "Escape",
                    "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27,
                })
                await asyncio.sleep(0.3)

            await asyncio.sleep(1)

            # Extract metrics
            result = await send_cmd("Runtime.evaluate", {
                "expression": JS_EXTRACT_VIDEO_DETAIL,
                "returnByValue": True,
            })
            value = result.get("result", {}).get("result", {}).get("value", "{}")
            try:
                detail = json.loads(value) if isinstance(value, str) else (value or {})
            except (json.JSONDecodeError, TypeError):
                detail = {}

    except Exception as e:
        detail = {"error": str(e)}
    finally:
        try:
            _cdp_http(f"/json/close/{tab_id}", timeout=5)
        except Exception:
            pass

    return detail


async def _cdp_collect_details(
    video_urls: list[str],
    max_total_seconds: float = 90,
) -> dict[str, dict]:
    """Collect detailed metrics for multiple videos via CDP (fast, no AI agent)."""
    details: dict[str, dict] = {}
    start = time.time()

    for i, url in enumerate(video_urls):
        elapsed = time.time() - start
        if elapsed > max_total_seconds:
            print(f"    Phase 2 time limit ({max_total_seconds}s) reached after {i} videos.")
            break

        try:
            per_video_timeout = min(20, max_total_seconds - elapsed)
            detail = await asyncio.wait_for(
                _cdp_get_video_detail(url),
                timeout=per_video_timeout,
            )
            if detail and "error" not in detail:
                details[url] = detail
                likes = detail.get("like_count", "?")
                views = detail.get("view_count", "?")
                followers = detail.get("follower_count", "?")
                print(f"    [{i+1}/{len(video_urls)}] {likes} likes, {views} views, {followers} followers")
            else:
                print(f"    [{i+1}/{len(video_urls)}] Failed: {detail.get('error', 'no data')}")
        except asyncio.TimeoutError:
            print(f"    [{i+1}/{len(video_urls)}] Timeout")
        except Exception as e:
            print(f"    [{i+1}/{len(video_urls)}] Error: {e}")

        await asyncio.sleep(1)  # Brief pause between requests

    return details


def _try_parse_json_results(text: str) -> dict | None:
    """Try to parse JSON from text, handling markdown code blocks."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()

    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass
    return None


def _cleanup_old_agent_files() -> None:
    """Remove stale browser-use agent temp files from previous runs."""
    import glob as glob_mod
    import shutil
    import tempfile

    agent_dirs = glob_mod.glob(str(Path(tempfile.gettempdir()) / "browser_use_agent_*"))
    for d in agent_dirs:
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass


def _recover_results_from_files(since_timestamp: float = 0) -> dict | None:
    """Check agent temp files for saved JSON results, merging multiple keyword files."""
    import glob as glob_mod
    import tempfile

    agent_files = glob_mod.glob(
        str(Path(tempfile.gettempdir()) / "browser_use_agent_*" / "**" / "*.json"),
        recursive=True,
    )
    # STRICT: only files created AFTER this run started (with 2s buffer)
    cutoff = since_timestamp - 2 if since_timestamp > 0 else 0
    recent_files = [
        f for f in agent_files
        if Path(f).stat().st_mtime > cutoff
    ] if cutoff > 0 else agent_files

    # Collect all results and video_details from files, merging them
    merged_results = {}
    merged_details = {}
    found_any = False

    for fpath in sorted(recent_files, key=lambda f: Path(f).stat().st_mtime, reverse=True):
        try:
            content = Path(fpath).read_text()
            parsed = _try_parse_json_results(content)
            if parsed is None:
                continue

            if "results" in parsed:
                for kw, videos in parsed["results"].items():
                    if kw not in merged_results:
                        merged_results[kw] = videos
                        print(f"Recovered '{kw}' results from: {fpath}", file=sys.stderr)
                        found_any = True

            if "video_details" in parsed:
                merged_details.update(parsed["video_details"])
                print(f"Recovered video details from: {fpath}", file=sys.stderr)
                found_any = True
        except Exception:
            continue

    if not found_any:
        return None

    result = {}
    if merged_results:
        result["results"] = merged_results
    if merged_details:
        result["video_details"] = merged_details
    return result


def _parse_markdown_video_list(text: str) -> list[dict]:
    """Parse markdown-formatted video list from extract tool output."""
    import re
    videos = []
    current = {}

    for line in text.split("\n"):
        line = line.strip().lstrip("- ")
        # Match Video URL
        url_match = re.search(r'Video URL[:\s]*`?(https://www\.tiktok\.com/@[^`\s]+/video/\d+)`?', line)
        if url_match:
            if current.get("url"):
                videos.append(current)
            current = {"url": url_match.group(1)}
            continue
        # Match Caption
        caption_match = re.search(r'(?:Caption|Video Caption|Caption/[Dd]escription)[:\s]*`?(.+?)`?$', line)
        if caption_match and current:
            current["title"] = caption_match.group(1).strip()
            continue
        # Match Creator
        creator_match = re.search(r"(?:Creator|Creator's @username|@username)[:\s]*@?`?(\S+?)`?$", line)
        if creator_match and current:
            current["uploader"] = creator_match.group(1).strip()
            continue
        # Match View/Like Count (search results show likes, not views)
        view_match = re.search(r'(?:View|Like) [Cc]ount[:\s]*`?(\d+)`?', line)
        if view_match and current:
            current["like_count"] = int(view_match.group(1))
            continue

    if current.get("url"):
        videos.append(current)

    return videos


def _recover_from_agent_history(result, keywords: list[str] | None = None) -> dict | None:
    """Scan agent history for JSON blocks or markdown-formatted video data."""
    if not hasattr(result, "history") or not result.history:
        return None

    # First try: look for JSON
    for entry in reversed(result.history):
        if not hasattr(entry, "result") or not entry.result:
            continue
        for r in entry.result:
            if hasattr(r, "extracted_content") and r.extracted_content:
                parsed = _try_parse_json_results(r.extracted_content)
                if parsed is not None:
                    print("Recovered results from agent history (JSON)", file=sys.stderr)
                    return parsed

    # Second try: parse markdown-style extracted content
    if keywords:
        all_videos = []
        for entry in result.history:
            if not hasattr(entry, "result") or not entry.result:
                continue
            for r in entry.result:
                if hasattr(r, "extracted_content") and r.extracted_content:
                    videos = _parse_markdown_video_list(r.extracted_content)
                    if len(videos) >= 3:  # Only use substantial extractions
                        all_videos.extend(videos)

        if all_videos:
            # Deduplicate by URL
            seen = set()
            unique = []
            for v in all_videos:
                if v["url"] not in seen:
                    seen.add(v["url"])
                    unique.append(v)

            # Put all videos under first keyword (best effort)
            print(f"Recovered {len(unique)} videos from agent history (markdown)", file=sys.stderr)
            return {"results": {keywords[0]: unique}}

    return None


# ---------------------------------------------------------------------------
# Video date extraction from TikTok video IDs
# ---------------------------------------------------------------------------

def _video_id_to_timestamp(video_url: str) -> int | None:
    """Extract unix timestamp from TikTok video ID (encoded in high 32 bits)."""
    import re as _re
    m = _re.search(r"/video/(\d+)", video_url)
    if not m:
        return None
    try:
        return int(m.group(1)) >> 32
    except (ValueError, OverflowError):
        return None


def _get_time_range_cutoff(time_range: str) -> int:
    """Get unix timestamp cutoff for the given time range filter."""
    now = int(time.time())
    offsets = {
        "day": 86400,
        "week": 7 * 86400,
        "month": 30 * 86400,
        "3months": 90 * 86400,
        "6months": 180 * 86400,
        "all": 0,
    }
    offset = offsets.get(time_range, 0)
    return now - offset if offset > 0 else 0


def _filter_videos_by_date(videos: list[dict], time_range: str) -> list[dict]:
    """Post-filter videos by actual creation date extracted from video ID.

    TikTok's URL-based time filters are unreliable. This extracts the actual
    creation timestamp from the video ID and filters strictly.
    """
    if time_range == "all":
        return videos

    cutoff = _get_time_range_cutoff(time_range)
    if cutoff == 0:
        return videos

    filtered = []
    removed = 0
    for v in videos:
        ts = _video_id_to_timestamp(v.get("url", ""))
        if ts is None or ts >= cutoff:
            filtered.append(v)
        else:
            removed += 1

    if removed > 0:
        print(f"    Filtered out {removed} videos older than {time_range}")

    return filtered


# ---------------------------------------------------------------------------
# Direct CDP extraction (no browser-use, no screenshots, fast)
# ---------------------------------------------------------------------------

JS_EXTRACT_VIDEOS = r"""
(function() {
  function parseCount(s) {
    if (!s) return 0;
    s = s.toString().trim().replace(/,/g, '');
    var m = s.match(/^([\d.]+)\s*([KkMmBb]?)$/);
    if (!m) return parseInt(s, 10) || 0;
    var n = parseFloat(m[1]);
    var u = (m[2] || '').toUpperCase();
    if (u === 'K') return Math.round(n * 1000);
    if (u === 'M') return Math.round(n * 1000000);
    if (u === 'B') return Math.round(n * 1000000000);
    return Math.round(n);
  }
  var videos = [];
  var seen = new Set();
  // Scope to search results container only — avoid sidebar, recommendations, etc.
  var container = document.querySelector('[data-e2e="search_video-item-list"], [data-e2e="search-common-link"], #search-result-container, [class*="search-result"], main')
                  || document.body;
  container.querySelectorAll('a[href*="/video/"]').forEach(function(a) {
    var href = a.href;
    var m = href.match(/(https:\/\/www\.tiktok\.com\/@[^\/]+\/video\/\d+)/);
    if (!m) return;
    var url = m[1];
    if (seen.has(url)) return;
    seen.add(url);
    // Walk up to find the video card
    var card = a.closest('[data-e2e="search_video-item"], [class*="DivItemContainer"], [class*="search-card"]') || a.parentElement;
    var title = '';
    var uploader = '';
    var likeCount = 0;
    if (card) {
      // Description
      var descEl = card.querySelector('[data-e2e="search-card-desc"], [class*="SpanText"], a[title]');
      if (descEl) title = (descEl.textContent || descEl.getAttribute('title') || '').trim().substring(0, 200);
      // Like count - TikTok search results show likes on thumbnails (not views)
      var spans = card.querySelectorAll('strong, span');
      for (var i = 0; i < spans.length; i++) {
        var txt = spans[i].textContent.trim();
        if (txt.match(/^\d+(\.\d+)?[KMBkmb]?$/) && !txt.match(/^\d{1,2}:\d{2}$/)) {
          var count = parseCount(txt);
          if (count > likeCount) likeCount = count;
        }
      }
    }
    var um = url.match(/@([^\/]+)/);
    if (um) uploader = um[1];
    // Skip numeric-only usernames (usually means it's not a real search result)
    if (uploader && /^\d+$/.test(uploader)) return;
    videos.push({url: url, title: title || '', uploader: uploader, like_count: likeCount});
  });
  return JSON.stringify(videos);
})()
""".strip()

def _build_filter_click_js(sort_label: str, time_label: str) -> str:
    """Build JS that clicks TikTok search filter buttons by visible text."""
    return f"""
(function() {{
  var results = [];

  // Helper: find any clickable element containing exact text
  function clickByText(text, scope) {{
    if (!text) return false;
    var lowerText = text.toLowerCase();
    var root = scope || document;
    // Try all clickable elements
    var els = root.querySelectorAll('button, [role="tab"], [role="option"], [role="radio"], span, div[class*="filter"], div[class*="Filter"], a, label, p');
    for (var i = 0; i < els.length; i++) {{
      var elText = els[i].textContent.trim().toLowerCase();
      // Exact or close match
      if (elText === lowerText || elText.includes(lowerText)) {{
        els[i].click();
        return true;
      }}
    }}
    return false;
  }}

  // Step 1: Click sort filter
  var sortClicked = clickByText('{sort_label}');
  results.push('sort:' + sortClicked);

  // Step 2: Click date/time filter
  var timeClicked = clickByText('{time_label}');
  results.push('time:' + timeClicked);

  return results.join(',');
}})()
""".strip()


async def _cdp_search_keyword(
    keyword: str,
    max_results: int,
    sort_by: str,
    time_range: str,
    duration: str,
) -> list[dict]:
    """Search TikTok for a keyword using direct CDP commands (no browser-use).

    Opens a new tab, navigates to TikTok search, scrolls, runs JS to extract videos.
    Fast and reliable — no screenshots or AI agent overhead.
    """
    import websockets  # type: ignore

    from config import SORT_TYPE, PUBLISH_TIME, DURATION_FILTER

    # Always include sort and time filters explicitly
    url_params = [
        f"sort_type={SORT_TYPE.get(sort_by, 0)}",
        f"publish_time={PUBLISH_TIME.get(time_range, 0)}",
    ]
    if duration != "all":
        url_params.append(f"duration={DURATION_FILTER.get(duration, 0)}")
    filter_query = "&" + "&".join(url_params)

    encoded_kw = urllib.parse.quote(keyword)
    search_url = f"https://www.tiktok.com/search/video?q={encoded_kw}{filter_query}"
    print(f"    URL: {search_url}")

    # Close any existing TikTok search tabs to avoid stale data
    try:
        targets_raw = _cdp_http("/json/list", timeout=5)
        targets = json.loads(targets_raw)
        for tab in targets:
            tab_url = tab.get("url", "")
            if "tiktok.com/search" in tab_url:
                try:
                    _cdp_http(f"/json/close/{tab['id']}", timeout=3)
                except Exception:
                    pass
        await asyncio.sleep(1)
    except Exception:
        pass

    # Create a new tab via PUT
    new_tab_raw = _cdp_http(
        f"/json/new?{urllib.parse.quote(search_url, safe='')}", method="PUT"
    )
    new_tab = json.loads(new_tab_raw)
    ws_url = new_tab["webSocketDebuggerUrl"]
    tab_id = new_tab["id"]


    all_videos: list[dict] = []
    msg_id = 1

    # Map sort_by / time_range to TikTok filter UI labels
    sort_labels = {"relevance": "Relevance", "likes": "Most liked", "date": "Date posted"}
    time_labels = {"all": "", "day": "Last 24 hours", "week": "This week", "month": "This month", "3months": "Last 3 months", "6months": "Last 6 months"}

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
                    # Ignore events

            # Wait for page to load
            print(f"    Searching: {keyword}")
            await asyncio.sleep(8)

            # Close any modals (press Escape twice)
            for _ in range(2):
                await send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Escape", "code": "Escape",
                    "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27,
                })
                await asyncio.sleep(0.5)
            await asyncio.sleep(1)

            # Click filter buttons via JS to ensure they're applied
            sort_label = sort_labels.get(sort_by, "")
            time_label = time_labels.get(time_range, "")
            if sort_label or time_label:
                filter_js = _build_filter_click_js(sort_label, time_label)
                filter_result = await send_cmd("Runtime.evaluate", {"expression": filter_js})
                filter_val = filter_result.get("result", {}).get("result", {}).get("value", "")
                print(f"    Filters: {filter_val}")
                if "true" in str(filter_val):
                    await asyncio.sleep(4)  # Wait for filtered results to reload
                else:
                    # Filters didn't click — try navigating with URL params again
                    # Force reload to ensure TikTok applies the URL-based filters
                    await send_cmd("Runtime.evaluate", {"expression": "location.reload()"})
                    await asyncio.sleep(6)

            # Scroll and extract in rounds
            for scroll_round in range(6):
                # Scroll down
                await send_cmd("Runtime.evaluate", {
                    "expression": "window.scrollBy(0, 1200)",
                })
                await asyncio.sleep(2)

                # Extract videos
                result = await send_cmd("Runtime.evaluate", {
                    "expression": JS_EXTRACT_VIDEOS,
                    "returnByValue": True,
                })
                value = result.get("result", {}).get("result", {}).get("value", "[]")
                try:
                    videos = json.loads(value) if isinstance(value, str) else value
                    if isinstance(videos, list) and len(videos) > len(all_videos):
                        all_videos = videos
                        print(f"    Round {scroll_round + 1}: {len(all_videos)} videos found")
                except (json.JSONDecodeError, TypeError):
                    pass

                if len(all_videos) >= max_results:
                    break

    except Exception as e:
        print(f"    CDP error for '{keyword}': {e}", file=sys.stderr)
    finally:
        # Close the tab
        try:
            _cdp_http(f"/json/close/{tab_id}", timeout=5)
        except Exception:
            pass

    # Post-filter by actual video date (TikTok URL params are unreliable)
    all_videos = _filter_videos_by_date(all_videos, time_range)

    return all_videos[:max_results]


def _merge_video_data(file_data: dict, history_videos: list[dict]) -> dict:
    """Merge video data from file (has URLs) with history extract data (has titles/views)."""
    if not file_data or "results" not in file_data or not history_videos:
        return file_data

    # Build a lookup by URL for history videos
    history_by_url = {}
    for v in history_videos:
        url = v.get("url", "")
        if url:
            history_by_url[url] = v

    # Merge: for each video in file results, fill in missing title/like_count from history
    for kw, videos in file_data["results"].items():
        for video in videos:
            url = video.get("url", "")
            hist = history_by_url.get(url)
            if hist:
                if not video.get("title") and hist.get("title"):
                    video["title"] = hist["title"]
                if not video.get("like_count") and hist.get("like_count"):
                    video["like_count"] = hist["like_count"]
                if not video.get("uploader") and hist.get("uploader"):
                    video["uploader"] = hist["uploader"]

    return file_data


async def browse_tiktok(
    keywords: list[str],
    max_results: int = DEFAULT_RESULTS_PER_KEYWORD,
    sort_by: str = DEFAULT_SORT_BY,
    time_range: str = DEFAULT_TIME_RANGE,
    duration: str = DEFAULT_DURATION,
    min_likes_for_details: int = DEFAULT_MIN_LIKES,
    max_total_seconds: int = 300,
) -> dict[str, list[dict]]:
    """
    Two-phase TikTok search via CDP connection to Chrome.

    Phase 1: Collect video URLs and view counts from search results
    Phase 2: Visit high-view video pages for likes, comments, duration, followers

    Total runtime is capped at max_total_seconds (default 180 = 3 minutes).
    """
    if not _ensure_chrome_with_cdp():
        print("Cannot start research browser. Please ensure Chrome is installed.", file=sys.stderr)
        return {k: [] for k in keywords}

    global_start = time.time()

    def time_remaining() -> float:
        return max(0, max_total_seconds - (time.time() - global_start))

    # --- Phase 1: Direct CDP search (fast, no browser-use overhead) ---
    print(f"Phase 1: Searching TikTok for {len(keywords)} keyword(s)... (max {max_total_seconds}s, max {MAX_TOTAL_RESULTS} videos)")
    results: dict[str, list[dict]] = {}
    total_collected = 0

    for kw in keywords:
        remaining = time_remaining()
        if remaining < 10:
            print(f"    Time limit reached, skipping remaining keywords.", file=sys.stderr)
            results[kw] = []
            continue

        if total_collected >= MAX_TOTAL_RESULTS:
            print(f"    Total results cap ({MAX_TOTAL_RESULTS}) reached, skipping remaining keywords.", file=sys.stderr)
            results[kw] = []
            continue

        per_keyword_timeout = min(45, remaining)
        try:
            videos = await asyncio.wait_for(
                _cdp_search_keyword(kw, max_results, sort_by, time_range, duration),
                timeout=per_keyword_timeout,
            )
            results[kw] = videos
            total_collected += len(videos)
        except asyncio.TimeoutError:
            print(f"    Timeout searching '{kw}', skipping.", file=sys.stderr)
            results[kw] = []
        except Exception as e:
            print(f"    Error searching '{kw}': {e}", file=sys.stderr)
            results[kw] = []

    total = sum(len(v) for v in results.values())
    if total == 0:
        print("Phase 1: No results found.", file=sys.stderr)
        return {k: [] for k in keywords}

    print(f"Phase 1 complete: {total} videos collected")

    search_data = {"results": results}

    results = search_data["results"]
    total = sum(len(v) for v in results.values())
    print(f"Phase 1 complete: {total} videos collected")

    # --- Phase 2: Get detailed metrics for videos via CDP ---
    # Collect all video URLs, prioritize by like count
    all_video_entries = []
    has_like_data = False
    for videos in results.values():
        for video in videos:
            like_count = video.get("like_count")
            if isinstance(like_count, (int, float)) and like_count > 0:
                has_like_data = True
            url = video.get("url", "")
            if url and "/video/" in url:
                all_video_entries.append(video)

    if has_like_data:
        # Prioritize high-like videos, then fill in the rest
        sorted_entries = sorted(
            all_video_entries,
            key=lambda v: v.get("like_count", 0) if isinstance(v.get("like_count"), (int, float)) else 0,
            reverse=True,
        )
        # Filter: only enrich videos above threshold, or all if no like data
        urls_to_enrich = [
            v.get("url", "") for v in sorted_entries
            if isinstance(v.get("like_count"), (int, float)) and v["like_count"] >= min_likes_for_details
        ]
    else:
        urls_to_enrich = [v.get("url", "") for v in all_video_entries]
        print("Phase 2: Like counts missing from search results, enriching all videos...")

    if not urls_to_enrich:
        print("Phase 2: No videos to enrich, skipping detail collection.")
        for videos in results.values():
            for video in videos:
                video.setdefault("follower_count", None)
                video.setdefault("like_count", None)
                video.setdefault("comment_count", None)
                video.setdefault("duration", None)
        return results

    remaining = time_remaining()
    if remaining < 15:
        print("Phase 2: Skipping detail collection (time limit reached).")
        for videos in results.values():
            for video in videos:
                video.setdefault("follower_count", None)
                video.setdefault("like_count", None)
                video.setdefault("comment_count", None)
                video.setdefault("duration", None)
        return results

    # Cap to 15 videos, bounded by remaining time
    phase2_timeout = min(120, int(remaining) - 5)
    capped_urls = urls_to_enrich[:15]
    print(f"Phase 2: Collecting detailed metrics for {len(capped_urls)} videos via CDP... (timeout: {phase2_timeout}s)")

    video_details = await _cdp_collect_details(capped_urls, max_total_seconds=phase2_timeout)
    print(f"Phase 2 complete: got details for {len(video_details)} videos")

    # Merge detail data back into results
    for videos in results.values():
        for video in videos:
            url = video.get("url", "")
            details = video_details.get(url, {})
            # Also try matching without trailing slash or with normalized URL
            if not details:
                for detail_url, detail_val in video_details.items():
                    if url in detail_url or detail_url in url:
                        details = detail_val
                        break
            if not details:
                # No detail data — fill defaults
                video.setdefault("follower_count", None)
                video.setdefault("comment_count", None)
                video.setdefault("share_count", None)
                video.setdefault("save_count", None)
                video.setdefault("duration", None)
                video.setdefault("view_count", None)
                continue
            # Fill in all available detail fields
            if details.get("title") and not video.get("title"):
                video["title"] = details["title"]
            if details.get("view_count"):
                video["view_count"] = details["view_count"]
            # like_count from detail page overrides search-page count (more accurate)
            if details.get("like_count"):
                video["like_count"] = details["like_count"]
            video["follower_count"] = details.get("follower_count")
            video["comment_count"] = details.get("comment_count")
            video["share_count"] = details.get("share_count")
            video["save_count"] = details.get("save_count")
            video["duration"] = details.get("duration")
            if details.get("music"):
                video["music"] = details["music"]
            if details.get("hashtags"):
                video["hashtags"] = details["hashtags"]
            if details.get("upload_timestamp"):
                video["upload_timestamp"] = details["upload_timestamp"]
            if details.get("author_total_likes"):
                video["author_total_likes"] = details["author_total_likes"]
            if details.get("author_video_count"):
                video["author_video_count"] = details["author_video_count"]

    return results


def filter_outliers(
    results: dict[str, list[dict]],
    min_likes: int = DEFAULT_MIN_LIKES,
    min_view_follower_ratio: float = DEFAULT_MIN_VIEW_FOLLOWER_RATIO,
) -> dict[str, list[dict]]:
    """
    Filter results to only include outlier videos.

    An outlier video has:
    - At least `min_likes` likes (default 10k) — TikTok search shows likes, not views
    - If view_count is available (from detail page), use view-to-follower ratio
    """
    filtered = {}
    for keyword, videos in results.items():
        outliers = []
        for video in videos:
            likes = video.get("like_count")
            if not isinstance(likes, (int, float)):
                continue
            if likes < min_likes:
                continue
            # If follower count and view_count are available, check ratio
            views = video.get("view_count")
            followers = video.get("follower_count")
            if (
                isinstance(views, (int, float))
                and isinstance(followers, (int, float))
                and followers > 0
            ):
                ratio = views / followers
                if ratio < min_view_follower_ratio:
                    continue
                video = {**video, "view_follower_ratio": round(ratio, 1)}
            outliers.append(video)
        filtered[keyword] = outliers
    return filtered


def format_results(results: dict[str, list[dict]]) -> str:
    """Format search results into a readable summary."""
    lines = []
    for keyword, videos in results.items():
        lines.append(f"\n## Keyword: \"{keyword}\" ({len(videos)} results)")
        lines.append("-" * 60)
        if not videos:
            lines.append("  No results found.")
            continue
        for i, video in enumerate(videos, 1):
            title = str(video.get("title", ""))[:80]
            uploader = video.get("uploader", "unknown")
            views = video.get("view_count")
            likes = video.get("like_count")
            comments = video.get("comment_count")
            shares = video.get("share_count")
            saves = video.get("save_count")
            url = video.get("url", "")

            followers = video.get("follower_count")
            ratio = video.get("view_follower_ratio")
            dur = video.get("duration")
            music = video.get("music")

            likes_str = f" | {likes:,} likes" if isinstance(likes, int) else ""
            views_str = f" | {views:,} views" if isinstance(views, int) else ""
            comments_str = f" | {comments:,} comments" if isinstance(comments, int) else ""
            shares_str = f" | {shares:,} shares" if isinstance(shares, int) else ""
            saves_str = f" | {saves:,} saves" if isinstance(saves, int) else ""
            followers_str = f" | {followers:,} followers" if isinstance(followers, int) else ""
            ratio_str = f" | {ratio}x ratio" if ratio else ""
            dur_str = f" | {dur}s" if isinstance(dur, (int, float)) else ""
            music_str = f" | {music}" if music else ""

            lines.append(f"  {i}. {title}")
            lines.append(f"     @{uploader}{followers_str}{likes_str}{views_str}{comments_str}{shares_str}{saves_str}{dur_str}{ratio_str}{music_str}")
            if url:
                lines.append(f"     {url}")
            lines.append("")

    return "\n".join(lines)


def build_summary_report(
    results: dict[str, list[dict]],
    keywords: list[str],
    sort_by: str,
    time_range: str,
    duration: str,
    outlier_results: dict[str, list[dict]] | None = None,
    min_likes: int = DEFAULT_MIN_LIKES,
    min_view_follower_ratio: float = DEFAULT_MIN_VIEW_FOLLOWER_RATIO,
) -> dict:
    """Build a structured summary report from results."""
    total_videos = sum(len(v) for v in results.values())

    all_videos = []
    for keyword, videos in results.items():
        for video in videos:
            all_videos.append({**video, "search_keyword": keyword})

    # Primary sort: by likes (always available from search results)
    top_by_likes = sorted(
        [v for v in all_videos if isinstance(v.get("like_count"), int)],
        key=lambda v: v.get("like_count", 0),
        reverse=True,
    )[:TOP_VIDEOS_LIMIT]

    # Secondary sort: by views (only available if Phase 2 detail collection ran)
    top_by_views = sorted(
        [v for v in all_videos if isinstance(v.get("view_count"), int) and v["view_count"] > 0],
        key=lambda v: v.get("view_count", 0),
        reverse=True,
    )[:TOP_VIDEOS_LIMIT]

    keyword_breakdown = {}
    for keyword, videos in results.items():
        likes = [v.get("like_count", 0) for v in videos if isinstance(v.get("like_count"), int)]
        views = [v.get("view_count", 0) for v in videos if isinstance(v.get("view_count"), int) and v.get("view_count", 0) > 0]
        outlier_count = len(outlier_results.get(keyword, [])) if outlier_results else 0
        keyword_breakdown[keyword] = {
            "video_count": len(videos),
            "outlier_count": outlier_count,
            "total_likes": sum(likes),
            "avg_likes": sum(likes) // len(likes) if likes else 0,
            "total_views": sum(views),
            "avg_views": sum(views) // len(views) if views else 0,
        }

    report = {
        "search_keywords": keywords,
        "filters": {"sort_by": sort_by, "time_range": time_range, "duration": duration},
        "outlier_criteria": {
            "min_likes": min_likes,
            "min_view_follower_ratio": min_view_follower_ratio,
        },
        "summary": {
            "total_videos_found": total_videos,
            "keywords_searched": len(keywords),
            "keyword_breakdown": keyword_breakdown,
        },
        "top_videos_by_likes": top_by_likes,
        "top_videos_by_views": top_by_views,
        "all_results": results,
    }

    if outlier_results is not None:
        total_outliers = sum(len(v) for v in outlier_results.values())
        report["outliers"] = {
            "total_outliers": total_outliers,
            "videos": outlier_results,
        }

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Browse TikTok using AI-powered search via CDP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run --project runtime runtime/browse.py --login                    # Login first
  uv run --project runtime runtime/browse.py "skincare routine"         # Search
  uv run --project runtime runtime/browse.py "protein shake" --sort-by likes --time-range week
  uv run --project runtime runtime/browse.py "AI tools" -n 20 -o output/results.json
        """,
    )
    parser.add_argument("keywords", nargs="*", help="Keywords to search for")
    parser.add_argument("--login", action="store_true", help="Open TikTok login page to sign in")
    parser.add_argument(
        "--login-check",
        action="store_true",
        help="Print TikTok session state as JSON and exit; opens and launches nothing",
    )
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
        "--sort-by",
        choices=list(SORT_TYPE.keys()),
        default=DEFAULT_SORT_BY,
        help=f"Sort by: relevance, likes, or date (default: {DEFAULT_SORT_BY})",
    )
    parser.add_argument(
        "--time-range",
        choices=list(PUBLISH_TIME.keys()),
        default=DEFAULT_TIME_RANGE,
        help=f"Filter by publish time (default: {DEFAULT_TIME_RANGE})",
    )
    parser.add_argument(
        "--duration",
        choices=list(DURATION_FILTER.keys()),
        default=DEFAULT_DURATION,
        help=f"Filter by duration (default: {DEFAULT_DURATION})",
    )
    parser.add_argument(
        "--min-likes",
        type=int,
        default=DEFAULT_MIN_LIKES,
        help=f"Minimum likes for outlier detection (default: {DEFAULT_MIN_LIKES:,})",
    )
    parser.add_argument(
        "--min-ratio",
        type=float,
        default=DEFAULT_MIN_VIEW_FOLLOWER_RATIO,
        help=f"Minimum view/follower ratio for outlier detection (default: {DEFAULT_MIN_VIEW_FOLLOWER_RATIO}x)",
    )
    parser.add_argument(
        "--no-outliers",
        action="store_true",
        help="Disable outlier filtering (show all results)",
    )
    parser.add_argument(
        "--no-details",
        action="store_true",
        help="Skip Phase 2 (don't visit individual video pages for views, followers, comments, duration)",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=300,
        help="Maximum total runtime in seconds (default: 300 = 5 minutes)",
    )

    args = parser.parse_args()

    if args.login_check:
        print(json.dumps({"platform": "tiktok", "logged_in": _check_tiktok_login()}))
        return

    if args.login:
        login_to_tiktok()
        return

    if not args.keywords:
        parser.error("keywords are required (or use --login to sign in first)")

    max_results = min(args.max_results, MAX_RESULTS_PER_KEYWORD)

    # A missing session must not abort the run, and nothing may pop up on its
    # own. Say plainly that signing in is what makes this platform usable, and
    # let the caller relay that; only an explicit --login opens a window.
    login_state = _check_tiktok_login()
    if login_state is False:
        print("No TikTok session. TikTok search returns very little signed out, so this capture will be thin.")
        print("  Sign in once for real results:")
        print("  uv run --project runtime runtime/browse.py --login")
    elif login_state is None:
        print("Could not read TikTok session state; continuing without opening a sign-in window.")

    filter_desc = []
    if args.sort_by != "relevance":
        filter_desc.append(f"sort={args.sort_by}")
    if args.time_range != "all":
        filter_desc.append(f"time={args.time_range}")
    if args.duration != "all":
        filter_desc.append(f"duration={args.duration}")
    filter_str = f" ({', '.join(filter_desc)})" if filter_desc else ""

    print(f"TikTok Browse: {len(args.keywords)} keyword(s){filter_str}")
    print("Connecting to Chrome via CDP...\n")

    # Use a very high threshold to skip Phase 2 if --no-details
    detail_threshold = 999_999_999 if args.no_details else args.min_likes

    results = asyncio.run(
        browse_tiktok(
            keywords=args.keywords,
            max_results=max_results,
            sort_by=args.sort_by,
            time_range=args.time_range,
            duration=args.duration,
            min_likes_for_details=detail_threshold,
            max_total_seconds=args.max_time,
        )
    )

    # Apply outlier filtering by default
    outlier_results = None
    if not args.no_outliers:
        outlier_results = filter_outliers(results, args.min_likes, args.min_ratio)
        outlier_total = sum(len(v) for v in outlier_results.values())
        print(f"\nOutlier criteria: {args.min_likes:,}+ likes, {args.min_ratio}x+ view/follower ratio")
        print(f"Outliers found: {outlier_total}")

    report = build_summary_report(
        results, args.keywords, args.sort_by, args.time_range, args.duration,
        outlier_results=outlier_results,
        min_likes=args.min_likes,
        min_view_follower_ratio=args.min_ratio,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nReport saved to: {output_path}")
    elif args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        # Show outlier results if available, otherwise show all
        if outlier_results is not None and sum(len(v) for v in outlier_results.values()) > 0:
            print("\n=== OUTLIER VIDEOS ===")
            print(format_results(outlier_results))
            print("\n=== ALL RESULTS ===")
        print(format_results(results))

    total = sum(len(v) for v in results.values())
    print(f"\nTotal: {total} videos found across {len(args.keywords)} keyword(s)")


if __name__ == "__main__":
    try:
        main()
    finally:
        _stop_research_browser()
