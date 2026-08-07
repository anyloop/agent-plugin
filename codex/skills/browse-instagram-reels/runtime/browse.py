#!/usr/bin/env python3
"""
Instagram Reels Browse - deterministic Instagram Reels research through Chrome CDP.

Uses a persistent Chrome profile with CDP (Chrome DevTools Protocol).
On first run, you log into Instagram once. Subsequent runs reuse the session.

Two-phase approach:
  Phase 1: Collect Reel URLs from Instagram search results page
  Phase 2: Visit individual Reel pages to get views, likes, comments, follower count

Usage:
  uv run --project runtime runtime/browse.py "keyword1" "keyword2"
  uv run --project runtime runtime/browse.py --login  # Re-login to Instagram
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

# Load env files - check skill dir, then project root
_skill_dir = Path(__file__).resolve().parent.parent
_project_root = _skill_dir.parent.parent
for env_file in [_skill_dir / ".env", _project_root / ".env", _project_root / ".env.production"]:
    if env_file.exists():
        load_dotenv(env_file)

from config import (
    DEFAULT_MIN_VIEW_FOLLOWER_RATIO,
    DEFAULT_MIN_VIEWS,
    DEFAULT_RESULTS_PER_KEYWORD,
    MAX_RESULTS_PER_KEYWORD,
)

CDP_PORT = 9334  # Different port — never conflicts with user's Chrome or TikTok skill (9333)
_runtime_data_dir = os.environ.get("ADANT_SOCIAL_DATA_DIR")
CDP_PROFILE_DIR = (
    Path(_runtime_data_dir) / "browse-instagram-reels"
    if _runtime_data_dir
    else _skill_dir / "data"
) / "research-profile"
_research_chrome_process = None


def _is_research_browser_running() -> bool:
    """Check if the research browser is running on CDP_PORT."""
    try:
        urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/version", timeout=2)
        return True
    except Exception:
        return False


async def _import_cookies_via_cdp() -> None:
    """Import Instagram cookies from user's Chrome into the research browser via CDP.

    Reads cookies from Chrome's sqlite DB to verify Instagram session exists.
    The research browser shares the imported profile for actual cookie usage.
    """
    import shutil
    import sqlite3
    import tempfile

    user_cookies_db = Path.home() / "Library" / "Application Support" / "Google" / "Chrome" / "Default" / "Cookies"
    if not user_cookies_db.exists():
        print("  No Chrome cookies found — you may need to log in manually.", file=sys.stderr)
        return

    # Copy the DB to a temp file (Chrome locks the original)
    tmp_db = Path(tempfile.mktemp(suffix=".db"))
    shutil.copy2(user_cookies_db, tmp_db)

    try:
        conn = sqlite3.connect(str(tmp_db))
        cursor = conn.execute(
            "SELECT COUNT(*) FROM cookies WHERE host_key LIKE '%instagram%'"
        )
        count = cursor.fetchone()[0]
        conn.close()

        if count > 0:
            print(f"  Found {count} Instagram cookies in your Chrome.")
        else:
            print("  No Instagram cookies found in Chrome — run with --login first.", file=sys.stderr)
    except Exception as e:
        print(f"  Could not read cookies: {e}", file=sys.stderr)
    finally:
        tmp_db.unlink(missing_ok=True)


def _ensure_chrome_with_cdp() -> bool:
    """
    Launch a SEPARATE headless research browser. NEVER touches user's Chrome.

    - Uses port 9334 (user's Chrome uses default or 9222, TikTok skill uses 9333)
    - Uses a FRESH temporary profile (no shared files, no lock conflicts)
    - Runs headless — invisible, no window, no dock icon, no focus stealing
    - User must run --login once to sign into Instagram in the research browser
    """
    global _research_chrome_process

    if _is_research_browser_running():
        print("Research browser already running.")
        return True

    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up any stale lock files from previous crashed sessions
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
    # Clean up lock files so user's Chrome is never blocked
    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        (CDP_PROFILE_DIR / lock_file).unlink(missing_ok=True)


def _check_instagram_login() -> bool:
    """Check if cookies file exists in the CDP profile (rough login check)."""
    cookies_file = CDP_PROFILE_DIR / "Default" / "Cookies"
    return cookies_file.exists()


def login_to_instagram() -> None:
    """Open a VISIBLE research browser for Instagram login.

    Launches a separate Chrome window (not headless) using the research profile
    so the user can log into Instagram. The session persists in the research profile
    for future headless runs. The user's main Chrome is NOT affected.
    """
    chrome_bin = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    CDP_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up stale locks
    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        (CDP_PROFILE_DIR / lock_file).unlink(missing_ok=True)

    print("Opening research browser for Instagram login...")
    print("(This is a SEPARATE browser — your main Chrome is not affected)")
    print("Log in to Instagram, then close this browser window.")

    subprocess.Popen(
        [
            chrome_bin,
            f"--user-data-dir={CDP_PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "https://www.instagram.com/accounts/login/",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print("\nOnce logged in, close the research browser and run searches:")
    print('  uv run --project runtime runtime/browse.py "your keyword"')


# ---------------------------------------------------------------------------
# Phase 1: Search and collect basic Reel info from search results
# ---------------------------------------------------------------------------

def _build_search_task(
    keywords: list[str],
    max_results: int,
) -> str:
    """Build a task prompt for Phase 1 - collecting Reels from Instagram search."""
    keywords_list = "\n".join(f'  - "{k}"' for k in keywords)

    js_extract = r"""(function() {
  var reels = [];
  var seen = new Set();
  document.querySelectorAll('a[href*="/reel/"]').forEach(function(a) {
    var href = a.href;
    var m = href.match(/(https:\/\/www\.instagram\.com\/reel\/[A-Za-z0-9_-]+)/);
    if (!m) return;
    var url = m[1] + '/';
    if (seen.has(url)) return;
    seen.add(url);
    var card = a.closest('div') || a.parentElement;
    var viewCount = 0;
    if (card) {
      var spans = card.querySelectorAll('span, li');
      for (var i = 0; i < spans.length; i++) {
        var txt = spans[i].textContent.trim();
        if (txt.match(/^\d+(\.\d+)?[KMBkmb]?\s*(views?|plays?)?$/i)) {
          var clean = txt.replace(/\s*(views?|plays?)/i, '');
          var pm = clean.match(/^([\d.]+)\s*([KkMmBb]?)$/);
          if (pm) {
            var n = parseFloat(pm[1]);
            var u = (pm[2] || '').toUpperCase();
            if (u === 'K') n = Math.round(n * 1000);
            else if (u === 'M') n = Math.round(n * 1000000);
            else if (u === 'B') n = Math.round(n * 1000000000);
            else n = Math.round(n);
            if (n > viewCount) viewCount = n;
          }
        }
      }
    }
    reels.push({url: url, view_count: viewCount});
  });
  return JSON.stringify(reels);
})()"""

    return f"""You are an Instagram Reels research assistant. For each keyword, search Instagram and collect Reel URLs.

KEYWORDS TO SEARCH (one at a time):
{keywords_list}

STEPS FOR EACH KEYWORD:
1. Navigate to https://www.instagram.com/
2. Click the Search icon (magnifying glass) in the left sidebar
3. Type the keyword in the search input field that appears
4. Wait 3 seconds for the search suggestions dropdown
5. Look for a "Reels" tab or filter. If you see tabs like "Top", "Accounts", "Audio", "Tags", "Reels", click "Reels"
   - If there's no Reels tab in the dropdown, look for "See all results" or similar, click it, then look for a Reels filter
   - Alternatively try navigating to: https://www.instagram.com/explore/search/keyword/?q=<keyword> and switch to Reels tab
6. Wait 5 seconds for Reel results to load
7. Scroll down 3-4 times slowly (window.scrollBy(0, 800)) with 2-second pauses to load more results
8. Run this JavaScript using the `evaluate` action to extract all Reel data:

{js_extract}

9. The JavaScript returns a JSON array of Reels. Parse it.
10. Keep up to {max_results} Reels per keyword.
11. Move to the next keyword and repeat from step 1.

AFTER ALL KEYWORDS:
Save the combined results to a file called "results.json" using write_file with this format:
{{
  "results": {{
    "keyword1": [
      {{"url": "https://www.instagram.com/reel/ABC123/", "view_count": 12345}}
    ]
  }}
}}
Then call done.

IMPORTANT:
- Use the EXACT JavaScript above with `evaluate` — do not try to read the DOM manually.
- If the JavaScript returns an empty array, scroll down more and run it again.
- If Instagram shows a login wall, close it or dismiss it.
- If you cannot find a Reels tab, try clicking on any reel-like video content and extract links from the page.
- BE FAST. Do not over-analyze. Extract and move on.
"""


# ---------------------------------------------------------------------------
# Phase 2: Visit individual Reel pages for detailed metrics
# ---------------------------------------------------------------------------

def _build_detail_task(reel_urls: list[str]) -> str:
    """Build a task prompt for Phase 2 - getting detailed metrics from Reel pages."""
    url_list = "\n".join(f"  {i+1}. {url}" for i, url in enumerate(reel_urls))

    js_detail = r"""(function() {
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
  // Caption
  var captionEl = document.querySelector('h1, [class*="Caption"], span[class*="_a9zs"]');
  d.caption = captionEl ? captionEl.textContent.trim().substring(0, 500) : null;
  // Username — look for links in the header area
  var headerLinks = document.querySelectorAll('header a[href*="/"], a[role="link"][href*="/"]');
  for (var i = 0; i < headerLinks.length; i++) {
    var href = headerLinks[i].getAttribute('href') || '';
    var um = href.match(/^\/([A-Za-z0-9._]+)\/?$/);
    if (um && um[1] !== 'explore' && um[1] !== 'reel' && um[1] !== 'p' && um[1] !== 'accounts') {
      d.username = um[1];
      break;
    }
  }
  if (!d.username) {
    var userSpan = document.querySelector('header a span, a[role="link"] span');
    if (userSpan) d.username = userSpan.textContent.trim();
  }
  // Engagement metrics — Instagram uses section elements with spans
  var sections = document.querySelectorAll('section');
  sections.forEach(function(sec) {
    var spans = sec.querySelectorAll('span');
    spans.forEach(function(span) {
      var txt = span.textContent.trim();
      var val = parseCount(txt);
      if (val === null) return;
      // Check nearby text/aria labels for context
      var parent = span.parentElement;
      var context = (parent ? parent.textContent : '').toLowerCase();
      var ariaLabel = (span.getAttribute('aria-label') || parent?.getAttribute('aria-label') || '').toLowerCase();
      if (ariaLabel.includes('like') || context.includes('like')) {
        if (!d.like_count || val > d.like_count) d.like_count = val;
      } else if (ariaLabel.includes('comment') || context.includes('comment')) {
        if (!d.comment_count) d.comment_count = val;
      } else if (ariaLabel.includes('view') || ariaLabel.includes('play') || context.includes('view') || context.includes('play')) {
        if (!d.view_count || val > d.view_count) d.view_count = val;
      }
    });
  });
  // Also check for view/play counts in other elements
  var allSpans = document.querySelectorAll('span[class]');
  allSpans.forEach(function(span) {
    var ariaLabel = (span.getAttribute('aria-label') || '').toLowerCase();
    if (ariaLabel.includes('play') || ariaLabel.includes('view')) {
      var val = parseCount(span.textContent.trim());
      if (val && (!d.view_count || val > d.view_count)) d.view_count = val;
    }
    if (ariaLabel.includes('like')) {
      var val = parseCount(span.textContent.trim());
      if (val && (!d.like_count || val > d.like_count)) d.like_count = val;
    }
  });
  // Follower count — visit the profile link area
  var metaEls = document.querySelectorAll('meta[name="description"], meta[property="og:description"]');
  metaEls.forEach(function(meta) {
    var content = meta.getAttribute('content') || '';
    var fm = content.match(/([\d,.]+[KMBkmb]?)\s*[Ff]ollowers/);
    if (fm) d.follower_count = parseCount(fm[1].replace(/,/g, ''));
  });
  return JSON.stringify(d);
})()"""

    return f"""You are an Instagram data collector. Visit each Reel page and extract metrics using JavaScript.

REELS TO VISIT:
{url_list}

STEPS FOR EACH REEL:
1. Navigate to the Reel URL
2. Wait 3 seconds for the page to load
3. If a login modal appears, close it (click X or press Escape)
4. Run this JavaScript using `evaluate`:

{js_detail}

5. Parse the returned JSON — it contains caption, username, view_count, like_count, comment_count, follower_count.
6. Store the result keyed by the Reel URL.
7. Move to the next Reel immediately.

AFTER ALL REELS:
Save results to "details.json" using write_file:
{{
  "video_details": {{
    "https://www.instagram.com/reel/ABC123/": {{
      "caption": "...",
      "username": "creator",
      "view_count": 12345,
      "like_count": 1200,
      "comment_count": 45,
      "follower_count": 50000
    }}
  }}
}}
Then call done.

IMPORTANT: Use the JavaScript above — do not try to read metrics manually. BE FAST.
"""


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
                for kw, reels in parsed["results"].items():
                    if kw not in merged_results:
                        merged_results[kw] = reels
                        print(f"Recovered '{kw}' results from: {fpath}", file=sys.stderr)
                        found_any = True

            if "video_details" in parsed:
                merged_details.update(parsed["video_details"])
                print(f"Recovered reel details from: {fpath}", file=sys.stderr)
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


def _parse_markdown_reel_list(text: str) -> list[dict]:
    """Parse markdown-formatted Reel list from extract tool output."""
    import re
    reels = []
    current: dict = {}

    for line in text.split("\n"):
        line = line.strip().lstrip("- ")
        # Match Reel URL
        url_match = re.search(r'(?:Reel |URL)[:\s]*`?(https://www\.instagram\.com/reel/[A-Za-z0-9_-]+/?)`?', line)
        if url_match:
            if current.get("url"):
                reels.append(current)
            current = {"url": url_match.group(1)}
            continue
        # Match Caption
        caption_match = re.search(r'(?:Caption|Description)[:\s]*`?(.+?)`?$', line)
        if caption_match and current:
            current["caption"] = caption_match.group(1).strip()
            continue
        # Match Creator/Username
        creator_match = re.search(r"(?:Creator|Username|@username)[:\s]*@?`?(\S+?)`?$", line)
        if creator_match and current:
            current["username"] = creator_match.group(1).strip()
            continue
        # Match View Count
        view_match = re.search(r'(?:View|Play)\s*[Cc]ount[:\s]*`?(\d+)`?', line)
        if view_match and current:
            current["view_count"] = int(view_match.group(1))
            continue

    if current.get("url"):
        reels.append(current)

    return reels


def _recover_from_agent_history(result, keywords: list[str] | None = None) -> dict | None:
    """Scan agent history for JSON blocks or markdown-formatted Reel data."""
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
        all_reels: list[dict] = []
        for entry in result.history:
            if not hasattr(entry, "result") or not entry.result:
                continue
            for r in entry.result:
                if hasattr(r, "extracted_content") and r.extracted_content:
                    reels = _parse_markdown_reel_list(r.extracted_content)
                    if len(reels) >= 3:  # Only use substantial extractions
                        all_reels.extend(reels)

        if all_reels:
            # Deduplicate by URL
            seen: set[str] = set()
            unique = []
            for v in all_reels:
                if v["url"] not in seen:
                    seen.add(v["url"])
                    unique.append(v)

            # Put all reels under first keyword (best effort)
            print(f"Recovered {len(unique)} reels from agent history (markdown)", file=sys.stderr)
            return {"results": {keywords[0]: unique}}

    return None


# ---------------------------------------------------------------------------
# Direct CDP extraction (no browser-use, no screenshots, fast)
# ---------------------------------------------------------------------------

JS_EXTRACT_REELS = r"""
(function() {
  var reels = [];
  var seen = new Set();
  // Instagram's keyword-search grid links every post as /p/<shortcode>/, including
  // video posts; /reel/<shortcode>/ only appears in some surfaces. Match both and
  // normalise to the /reel/ permalink, which redirects correctly either way.
  document.querySelectorAll('a[href*="/reel/"], a[href*="/p/"]').forEach(function(a) {
    var href = a.href;
    var m = href.match(/instagram\.com\/(?:reel|p)\/([A-Za-z0-9_-]+)/);
    if (!m) return;
    var url = 'https://www.instagram.com/reel/' + m[1] + '/';
    if (seen.has(url)) return;
    seen.add(url);
    var card = a.closest('div') || a.parentElement;
    var viewCount = 0;
    if (card) {
      // Instagram overlays play counts on thumbnails
      var spans = card.querySelectorAll('span, li');
      for (var i = 0; i < spans.length; i++) {
        var txt = spans[i].textContent.trim();
        // Match patterns like "1.2M", "45.3K", "1,234", "500K views"
        var clean = txt.replace(/\s*(views?|plays?|likes?)/gi, '').trim();
        var pm = clean.match(/^([\d,.]+)\s*([KkMmBb]?)$/);
        if (pm) {
          var n = parseFloat(pm[1].replace(/,/g, ''));
          var u = (pm[2] || '').toUpperCase();
          if (u === 'K') n = Math.round(n * 1000);
          else if (u === 'M') n = Math.round(n * 1000000);
          else if (u === 'B') n = Math.round(n * 1000000000);
          else n = Math.round(n);
          if (n > viewCount) viewCount = n;
        }
      }
    }
    reels.push({url: url, view_count: viewCount});
  });
  return JSON.stringify(reels);
})()
""".strip()


async def _cdp_search_keyword(
    keyword: str,
    max_results: int,
) -> list[dict]:
    """Search Instagram for a keyword using direct CDP commands (no browser-use).

    Opens a new tab, navigates to Instagram search, scrolls, runs JS to extract Reels.
    Fast and reliable — no screenshots or AI agent overhead.
    """
    import websockets  # type: ignore

    encoded_kw = urllib.parse.quote(keyword)
    # Instagram's explore search URL — will redirect to search results
    search_url = f"https://www.instagram.com/explore/search/keyword/?q={encoded_kw}"
    print(f"    URL: {search_url}")

    # Close any existing Instagram search tabs to avoid stale data
    try:
        targets_raw = urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/list", timeout=5).read()
        targets = json.loads(targets_raw)
        for tab in targets:
            tab_url = tab.get("url", "")
            if "instagram.com/explore/search" in tab_url or "instagram.com/search" in tab_url:
                try:
                    urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/close/{tab['id']}", timeout=3)
                except Exception:
                    pass
        await asyncio.sleep(1)
    except Exception:
        pass

    # Create a new tab via PUT
    req = urllib.request.Request(
        f"http://localhost:{CDP_PORT}/json/new?{urllib.parse.quote(search_url, safe='')}",
        method="PUT",
    )
    new_tab_raw = urllib.request.urlopen(req, timeout=10).read()
    new_tab = json.loads(new_tab_raw)
    ws_url = new_tab["webSocketDebuggerUrl"]
    tab_id = new_tab["id"]

    all_reels: list[dict] = []
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

            # Only click a Reels *tab* that belongs to the search results. Matching
            # any element whose text is "reels" also matches the global nav link,
            # which navigates to the single-reel viewer and destroys the result
            # grid we are about to read (the grid is where the posts actually are).
            click_reels_js = """
(function() {
  var tabs = document.querySelectorAll('[role="tab"], [role="tablist"] a, [role="tablist"] button');
  for (var i = 0; i < tabs.length; i++) {
    if (tabs[i].textContent.trim().toLowerCase() === 'reels') {
      tabs[i].click();
      return 'clicked_reels_tab';
    }
  }
  return 'no_reels_tab';
})()
""".strip()
            reels_tab_result = await send_cmd("Runtime.evaluate", {"expression": click_reels_js})
            reels_tab_val = reels_tab_result.get("result", {}).get("result", {}).get("value", "")
            print(f"    Reels tab: {reels_tab_val}")

            if "clicked" in str(reels_tab_val):
                await asyncio.sleep(4)  # Wait for Reels results to load

            # Scroll and extract in rounds
            for scroll_round in range(6):
                # Scroll down
                await send_cmd("Runtime.evaluate", {
                    "expression": "window.scrollBy(0, 1200)",
                })
                await asyncio.sleep(2)

                # Extract reels
                result = await send_cmd("Runtime.evaluate", {
                    "expression": JS_EXTRACT_REELS,
                    "returnByValue": True,
                })
                value = result.get("result", {}).get("result", {}).get("value", "[]")
                try:
                    reels = json.loads(value) if isinstance(value, str) else value
                    if isinstance(reels, list) and len(reels) > len(all_reels):
                        all_reels = reels
                        print(f"    Round {scroll_round + 1}: {len(all_reels)} reels found")
                except (json.JSONDecodeError, TypeError):
                    pass

                if len(all_reels) >= max_results:
                    break

    except Exception as e:
        print(f"    CDP error for '{keyword}': {e}", file=sys.stderr)
    finally:
        # Close the tab
        try:
            urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json/close/{tab_id}", timeout=5)
        except Exception:
            pass

    return all_reels[:max_results]


def _merge_reel_data(file_data: dict, history_reels: list[dict]) -> dict:
    """Merge reel data from file (has URLs) with history extract data (has captions/views)."""
    if not file_data or "results" not in file_data or not history_reels:
        return file_data

    # Build a lookup by URL for history reels
    history_by_url = {}
    for v in history_reels:
        url = v.get("url", "")
        if url:
            history_by_url[url] = v

    # Merge: for each reel in file results, fill in missing data from history
    for _kw, reels in file_data["results"].items():
        for reel in reels:
            url = reel.get("url", "")
            hist = history_by_url.get(url)
            if hist:
                if not reel.get("caption") and hist.get("caption"):
                    reel["caption"] = hist["caption"]
                if not reel.get("view_count") and hist.get("view_count"):
                    reel["view_count"] = hist["view_count"]
                if not reel.get("username") and hist.get("username"):
                    reel["username"] = hist["username"]

    return file_data


async def browse_instagram_reels(
    keywords: list[str],
    max_results: int = DEFAULT_RESULTS_PER_KEYWORD,
    min_views_for_details: int = DEFAULT_MIN_VIEWS,
    max_total_seconds: int = 180,
    skip_details: bool = False,
) -> dict[str, list[dict]]:
    """
    Two-phase Instagram Reels search via CDP connection to Chrome.

    Phase 1: Collect Reel URLs and view counts from search results
    Phase 2: Visit individual Reel pages for likes, comments, follower count

    Total runtime is capped at max_total_seconds (default 180 = 3 minutes).
    """
    if not _ensure_chrome_with_cdp():
        print("Cannot start research browser. Please ensure Chrome is installed.", file=sys.stderr)
        return {k: [] for k in keywords}

    global_start = time.time()

    def time_remaining() -> float:
        return max(0, max_total_seconds - (time.time() - global_start))

    # --- Phase 1: Direct CDP search (fast, no browser-use overhead) ---
    print(f"Phase 1: Searching Instagram for {len(keywords)} keyword(s)... (max {max_total_seconds}s total)")
    results: dict[str, list[dict]] = {}

    cdp_failed = False
    for kw in keywords:
        remaining = time_remaining()
        if remaining < 10:
            print("    Time limit reached, skipping remaining keywords.", file=sys.stderr)
            results[kw] = []
            continue

        # A fixed 45s cap made --max-time inert: raising the total budget could not
        # give a slow keyword more time. Share the remaining budget across the
        # keywords still to run, with 45s as the floor rather than the ceiling.
        keywords_left = max(1, len(keywords) - list(keywords).index(kw))
        per_keyword_timeout = min(max(45.0, remaining / keywords_left), remaining)
        try:
            reels = await asyncio.wait_for(
                _cdp_search_keyword(kw, max_results),
                timeout=per_keyword_timeout,
            )
            results[kw] = reels
            if not reels:
                cdp_failed = True
        except asyncio.TimeoutError:
            print(f"    Timeout searching '{kw}', skipping.", file=sys.stderr)
            results[kw] = []
            cdp_failed = True
        except Exception as e:
            print(f"    Error searching '{kw}': {e}", file=sys.stderr)
            results[kw] = []
            cdp_failed = True

    total = sum(len(v) for v in results.values())

    # The documented fallback is discover_reels.py, which uses public search
    # indexes and does not require a third-party model credential.
    if total == 0 and cdp_failed:
        print(
            "Phase 1 CDP found no results. Use discover_reels.py for keyless indexed discovery.",
            file=sys.stderr,
        )

    if total == 0:
        print("Phase 1: No results found.", file=sys.stderr)
        return {k: [] for k in keywords}

    print(f"Phase 1 complete: {total} reels collected")

    if skip_details:
        for reels in results.values():
            for reel in reels:
                reel.setdefault("username", None)
                reel.setdefault("caption", None)
                reel.setdefault("like_count", None)
                reel.setdefault("comment_count", None)
                reel.setdefault("follower_count", None)
        return results

    # --- Phase 2: Get detailed metrics for reels ---
    all_urls = []
    has_view_data = False
    for reels in results.values():
        for reel in reels:
            view_count = reel.get("view_count")
            if isinstance(view_count, (int, float)) and view_count > 0:
                has_view_data = True
            url = reel.get("url", "")
            if url and "/reel/" in url:
                all_urls.append(url)

    if has_view_data:
        # Only enrich high-view reels
        high_view_urls = [
            v.get("url", "") for reels in results.values() for v in reels
            if isinstance(v.get("view_count"), (int, float)) and v["view_count"] >= min_views_for_details
            and "/reel/" in v.get("url", "")
        ]
    else:
        # View data is missing, enrich all reels
        high_view_urls = all_urls
        print("Phase 2: View counts missing from search results, enriching all reels...")

    if not high_view_urls:
        print("Phase 2: No reels to enrich, skipping detail collection.")
        for reels in results.values():
            for reel in reels:
                reel.setdefault("username", None)
                reel.setdefault("caption", None)
                reel.setdefault("like_count", None)
                reel.setdefault("comment_count", None)
                reel.setdefault("follower_count", None)
        return results

    # Cap Phase 2 to 10 reels max, bounded by remaining time
    remaining = time_remaining()
    if remaining < 15:
        print("Phase 2: Skipping detail collection (time limit reached).")
        for reels in results.values():
            for reel in reels:
                reel.setdefault("username", None)
                reel.setdefault("caption", None)
                reel.setdefault("like_count", None)
                reel.setdefault("comment_count", None)
                reel.setdefault("follower_count", None)
        return results

    capped_urls = high_view_urls[:10]
    print(f"Phase 2: Getting public page metadata for {len(capped_urls)} reels...")
    from discover_reels import fetch_reel

    fetched = await asyncio.gather(
        *(asyncio.to_thread(fetch_reel, url) for url in capped_urls)
    )
    video_details = {
        url: {
            "caption": detail.get("caption"),
            "username": detail.get("handle", "").lstrip("@"),
            "like_count": detail.get("likes"),
            "comment_count": detail.get("comments"),
        }
        for url, detail in zip(capped_urls, fetched, strict=True)
        if detail
    }
    print(f"Phase 2 complete: got details for {len(video_details)} reels")

    for reels in results.values():
        for reel in reels:
            url = reel.get("url", "")
            details = video_details.get(url, {})
            # Also try matching without trailing slash or with normalized URL
            if not details:
                for detail_url, detail_val in video_details.items():
                    if url.rstrip("/") == detail_url.rstrip("/"):
                        details = detail_val
                        break
            if not details:
                for detail_url, detail_val in video_details.items():
                    if url in detail_url or detail_url in url:
                        details = detail_val
                        break
            # Fill in all available detail fields
            if details.get("caption") and not reel.get("caption"):
                reel["caption"] = details["caption"]
            if details.get("username") and not reel.get("username"):
                reel["username"] = details["username"]
            if details.get("view_count") and not reel.get("view_count"):
                reel["view_count"] = details["view_count"]
            reel["like_count"] = details.get("like_count")
            reel["comment_count"] = details.get("comment_count")
            reel["follower_count"] = details.get("follower_count")

    return results


def filter_outliers(
    results: dict[str, list[dict]],
    min_views: int = DEFAULT_MIN_VIEWS,
    min_view_follower_ratio: float = DEFAULT_MIN_VIEW_FOLLOWER_RATIO,
) -> dict[str, list[dict]]:
    """
    Filter results to only include outlier reels.

    An outlier reel has:
    - At least `min_views` views (default 50k)
    - A view-to-follower ratio of at least `min_view_follower_ratio` (default 5x)

    Instagram no longer exposes a play count on the surfaces this skill reads, so
    `view_count` is routinely 0 while `like_count` is present. Scoring those reels
    on views alone rejects every one of them and reports "0 outliers" for a niche
    that is actually busy. Fall back to likes (at a tenth of the view floor, the
    usual like-to-view order of magnitude) whenever views are missing.
    """
    filtered = {}
    for keyword, reels in results.items():
        outliers = []
        for reel in reels:
            views = reel.get("view_count")
            followers = reel.get("follower_count")
            if not isinstance(views, (int, float)) or views <= 0:
                likes = reel.get("like_count")
                if not isinstance(likes, (int, float)) or likes < max(1, min_views // 10):
                    continue
                outliers.append({**reel, "outlier_basis": "likes"})
                continue
            if views < min_views:
                continue
            # If follower count is available, check ratio
            if isinstance(followers, (int, float)) and followers > 0:
                ratio = views / followers
                if ratio < min_view_follower_ratio:
                    continue
                reel = {**reel, "view_follower_ratio": round(ratio, 1)}
            outliers.append(reel)
        filtered[keyword] = outliers
    return filtered


def format_results(results: dict[str, list[dict]]) -> str:
    """Format search results into a readable summary."""
    lines = []
    for keyword, reels in results.items():
        lines.append(f"\n## Keyword: \"{keyword}\" ({len(reels)} results)")
        lines.append("-" * 60)
        if not reels:
            lines.append("  No results found.")
            continue
        for i, reel in enumerate(reels, 1):
            caption = str(reel.get("caption", ""))[:80]
            username = reel.get("username", "unknown")
            views = reel.get("view_count")
            likes = reel.get("like_count")
            comments = reel.get("comment_count")
            url = reel.get("url", "")

            followers = reel.get("follower_count")
            ratio = reel.get("view_follower_ratio")

            views_str = f" | {views:,} views" if isinstance(views, int) else ""
            likes_str = f" | {likes:,} likes" if isinstance(likes, int) else ""
            comments_str = f" | {comments:,} comments" if isinstance(comments, int) else ""
            followers_str = f" | {followers:,} followers" if isinstance(followers, int) else ""
            ratio_str = f" | {ratio}x ratio" if ratio else ""

            lines.append(f"  {i}. {caption}")
            lines.append(f"     @{username}{followers_str}{views_str}{likes_str}{comments_str}{ratio_str}")
            if url:
                lines.append(f"     {url}")
            lines.append("")

    return "\n".join(lines)


def build_summary_report(
    results: dict[str, list[dict]],
    keywords: list[str],
    outlier_results: dict[str, list[dict]] | None = None,
    min_views: int = DEFAULT_MIN_VIEWS,
    min_view_follower_ratio: float = DEFAULT_MIN_VIEW_FOLLOWER_RATIO,
) -> dict:
    """Build a structured summary report from results."""
    total_reels = sum(len(v) for v in results.values())

    all_reels = []
    for keyword, reels in results.items():
        for reel in reels:
            all_reels.append({**reel, "search_keyword": keyword})

    top_by_views = sorted(
        [v for v in all_reels if isinstance(v.get("view_count"), int)],
        key=lambda v: v.get("view_count", 0),
        reverse=True,
    )[:10]

    top_by_likes = sorted(
        [v for v in all_reels if isinstance(v.get("like_count"), int)],
        key=lambda v: v.get("like_count", 0),
        reverse=True,
    )[:10]

    keyword_breakdown = {}
    for keyword, reels in results.items():
        views = [v.get("view_count", 0) for v in reels if isinstance(v.get("view_count"), int)]
        likes = [v.get("like_count", 0) for v in reels if isinstance(v.get("like_count"), int)]
        outlier_count = len(outlier_results.get(keyword, [])) if outlier_results else 0
        keyword_breakdown[keyword] = {
            "reel_count": len(reels),
            "outlier_count": outlier_count,
            "total_views": sum(views),
            "total_likes": sum(likes),
            "avg_views": sum(views) // len(views) if views else 0,
            "avg_likes": sum(likes) // len(likes) if likes else 0,
        }

    report = {
        "search_keywords": keywords,
        "outlier_criteria": {
            "min_views": min_views,
            "min_view_follower_ratio": min_view_follower_ratio,
        },
        "summary": {
            "total_reels_found": total_reels,
            "keywords_searched": len(keywords),
            "keyword_breakdown": keyword_breakdown,
        },
        "top_reels_by_views": top_by_views,
        "top_reels_by_likes": top_by_likes,
        "all_results": results,
    }

    if outlier_results is not None:
        total_outliers = sum(len(v) for v in outlier_results.values())
        report["outliers"] = {
            "total_outliers": total_outliers,
            "reels": outlier_results,
        }

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Browse Instagram Reels using AI-powered search via CDP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  uv run --project runtime runtime/browse.py --login                    # Login first
  uv run --project runtime runtime/browse.py "skincare routine"         # Search
  uv run --project runtime runtime/browse.py "protein shake" "gym tips"
  uv run --project runtime runtime/browse.py "AI tools" -n 20 -o output/results.json
        """,
    )
    parser.add_argument("keywords", nargs="*", help="Keywords to search for")
    parser.add_argument("--login", action="store_true", help="Open Instagram login page to sign in")
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
        help="Skip Phase 2 (don't visit individual Reel pages for detailed metrics)",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=180,
        help="Maximum total runtime in seconds (default: 180 = 3 minutes)",
    )

    args = parser.parse_args()

    if args.login:
        login_to_instagram()
        return

    if not args.keywords:
        parser.error("keywords are required (or use --login to sign in first)")

    max_results = min(args.max_results, MAX_RESULTS_PER_KEYWORD)

    # Prompt to login if no CDP profile exists yet
    if not _check_instagram_login():
        print("No Instagram session found. Run with --login first to sign in:")
        print("  uv run --project runtime runtime/browse.py --login")
        return

    print(f"Instagram Reels Browse: {len(args.keywords)} keyword(s)")
    print("Connecting to Chrome via CDP...\n")

    results = asyncio.run(
        browse_instagram_reels(
            keywords=args.keywords,
            max_results=max_results,
            min_views_for_details=args.min_views,
            max_total_seconds=args.max_time,
            skip_details=args.no_details,
        )
    )

    # Apply outlier filtering by default
    outlier_results = None
    if not args.no_outliers:
        outlier_results = filter_outliers(results, args.min_views, args.min_ratio)
        outlier_total = sum(len(v) for v in outlier_results.values())
        print(f"\nOutlier criteria: {args.min_views:,}+ views, {args.min_ratio}x+ view/follower ratio")
        print(f"Outliers found: {outlier_total}")

    report = build_summary_report(
        results, args.keywords,
        outlier_results=outlier_results,
        min_views=args.min_views,
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
            print("\n=== OUTLIER REELS ===")
            print(format_results(outlier_results))
            print("\n=== ALL RESULTS ===")
        print(format_results(results))

    total = sum(len(v) for v in results.values())
    print(f"\nTotal: {total} reels found across {len(args.keywords)} keyword(s)")


if __name__ == "__main__":
    main()
