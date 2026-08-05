#!/usr/bin/env python3
"""
Meta Ad Library Browse - AI-powered competitive ad research using browser-use.

Uses a persistent Chrome profile with CDP (Chrome DevTools Protocol).
No login required — Meta Ad Library is publicly accessible.

Usage:
  uv run --project runtime runtime/browse.py "keyword1" "keyword2"
  uv run --project runtime runtime/browse.py "Example Finance" --platform instagram --media-type video
  uv run --project runtime runtime/browse.py "fintech app" -n 30 -o output/ads_research.json
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
    AD_LIBRARY_SEARCH_URL,
    DEFAULT_RESULTS_PER_KEYWORD,
    LONGEVITY_ESTABLISHED,
    LONGEVITY_PROVEN,
    LONGEVITY_TESTING,
    MAX_RESULTS_PER_KEYWORD,
    MEDIA_TYPE_FILTERS,
    PLATFORM_FILTERS,
    SearchError,
    ValidationError,
)

CDP_PORT = 9335  # Different from TikTok (9333) and Instagram (9334)
_runtime_data_dir = os.environ.get("ADANT_SOCIAL_DATA_DIR")
CDP_PROFILE_DIR = (
    Path(_runtime_data_dir) / "browse-meta-ads-library"
    if _runtime_data_dir
    else _skill_dir / "data"
) / "research-profile"
_research_chrome_process = None


# ---------------------------------------------------------------------------
# Chrome CDP management
# ---------------------------------------------------------------------------


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
    """Launch a SEPARATE headless research browser. NEVER touches user's Chrome.

    - Uses port 9335 (unique to this skill)
    - Uses a dedicated profile directory
    - Runs headless — invisible, no window, no dock icon, no focus stealing
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
            "--window-size=1440,900",
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
    # Clean up lock files
    for lock_file in ["SingletonLock", "SingletonSocket", "SingletonCookie"]:
        (CDP_PROFILE_DIR / lock_file).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# JavaScript extraction for Meta Ad Library ad cards
# ---------------------------------------------------------------------------

JS_EXTRACT_ADS = r"""
(function() {
  var ads = [];
  var seen = new Set();

  // ── Strategy: anchor on "Library ID:" spans to locate each ad card ──
  // Every ad in the Meta Ad Library contains a span with "Library ID: <number>".
  // We walk up from that span to find the card container, then extract data
  // from within that boundary. This avoids picking up page navigation/header.

  var libraryIdSpans = [];
  document.querySelectorAll('span').forEach(function(span) {
    if (/Library ID:\s*\d+/.test(span.textContent)) {
      libraryIdSpans.push(span);
    }
  });

  // For each Library ID span, walk up to find the card boundary
  var cardElements = [];
  libraryIdSpans.forEach(function(span) {
    var el = span;
    // Walk up until we find a container that is big enough to be a card
    // (typically 4-8 levels up from the Library ID span)
    for (var i = 0; i < 10; i++) {
      if (!el.parentElement || el.parentElement === document.body) break;
      el = el.parentElement;
      // A card is typically >300px wide and >200px tall
      var rect = el.getBoundingClientRect();
      if (rect.width > 300 && rect.height > 200) {
        // Check this element contains at least one link — cards always do
        if (el.querySelector('a[href]')) {
          cardElements.push(el);
          break;
        }
      }
    }
  });

  // Deduplicate cards (a parent card might contain child cards)
  var uniqueCards = [];
  cardElements.forEach(function(card) {
    var dominated = false;
    for (var i = 0; i < uniqueCards.length; i++) {
      if (uniqueCards[i].contains(card)) { dominated = true; break; }
      if (card.contains(uniqueCards[i])) { uniqueCards[i] = card; dominated = true; break; }
    }
    if (!dominated) uniqueCards.push(card);
  });

  uniqueCards.forEach(function(card) {
    var ad = {};

    // Extract Library ID directly from the anchor span
    var idSpan = null;
    card.querySelectorAll('span').forEach(function(s) {
      var m = s.textContent.match(/Library ID:\s*(\d+)/);
      if (m) { ad.ad_id = m[1]; idSpan = s; }
    });

    // Advertiser name — first link to a facebook.com page (not ads/library)
    var pageLinks = card.querySelectorAll('a[href*="facebook.com/"]:not([href*="ads/library"])');
    for (var i = 0; i < pageLinks.length; i++) {
      var linkText = pageLinks[i].textContent.trim();
      // Skip empty or very short link text, and skip "Ad Library Report" etc.
      if (linkText.length > 1 && !linkText.toLowerCase().includes('ad library')) {
        ad.advertiser = linkText;
        ad.advertiser_page_url = pageLinks[i].href;
        break;
      }
    }

    // Start date — "Started running on ..." text
    card.querySelectorAll('span').forEach(function(span) {
      var text = span.textContent.trim();
      var dateMatch = text.match(/Started running on\s+(\w{3}\s+\d{1,2},?\s+\d{4})/);
      if (dateMatch) ad.start_date = dateMatch[1];
      if (text === 'Active' || text === 'Inactive') ad.status = text.toLowerCase();
    });

    // Ad text / copy — look for the actual ad creative text
    // Skip metadata spans (Library ID, Started running, Active, platform names)
    var metadataPatterns = /^(Active|Inactive|Library ID|Started running|Platforms|Categories|See ad|Open Dropdown|All|About|Issues|Ad Library|Report|Branded|Housing|Employment|Financial|Political)/i;
    var textParts = [];
    var seenText = new Set();
    card.querySelectorAll('div[dir="auto"] span, div[style*="white-space"] span').forEach(function(e) {
      var t = e.textContent.trim();
      if (t && t.length > 10 && !seenText.has(t) && !metadataPatterns.test(t)) {
        seenText.add(t);
        textParts.push(t);
      }
    });
    if (textParts.length) {
      ad.ad_text = textParts.join(' ').substring(0, 500);
    }

    // CTA button text
    var ctaKeywords = ['Learn More', 'Shop Now', 'Sign Up', 'Download', 'Get Offer',
                       'Book Now', 'Contact Us', 'Apply Now', 'Subscribe', 'Watch More',
                       'Get Started', 'Order Now', 'See More', 'Install Now', 'Use App',
                       'Send Message', 'Get Quote', 'Listen Now', 'Open Link'];
    card.querySelectorAll('a span, div[role="button"] span, button span').forEach(function(el) {
      if (ad.cta) return;
      var txt = el.textContent.trim();
      for (var i = 0; i < ctaKeywords.length; i++) {
        if (txt.toLowerCase().includes(ctaKeywords[i].toLowerCase())) {
          ad.cta = ctaKeywords[i];
          return;
        }
      }
    });

    // Platform badges
    ad.platforms = [];
    card.querySelectorAll('img[alt], span').forEach(function(el) {
      var alt = (el.alt || el.textContent || '').toLowerCase();
      if (alt.includes('facebook') && ad.platforms.indexOf('facebook') === -1) ad.platforms.push('facebook');
      if (alt.includes('instagram') && ad.platforms.indexOf('instagram') === -1) ad.platforms.push('instagram');
      if (alt.includes('messenger') && ad.platforms.indexOf('messenger') === -1) ad.platforms.push('messenger');
      if (alt.includes('audience network') && ad.platforms.indexOf('audience_network') === -1) ad.platforms.push('audience_network');
    });

    // ── Creative URLs extraction ──
    ad.creative_urls = [];

    // Video sources
    card.querySelectorAll('video').forEach(function(v) {
      var src = v.src || (v.querySelector('source') ? v.querySelector('source').src : '');
      if (src && src.startsWith('http')) ad.creative_urls.push({type: 'video', url: src});
      if (v.poster && v.poster.startsWith('http')) ad.creative_urls.push({type: 'video_thumbnail', url: v.poster});
    });

    // Image sources — scontent/fbcdn CDN images are ad creatives
    card.querySelectorAll('img[src*="scontent"], img[src*="fbcdn"]').forEach(function(img) {
      var src = img.src;
      // Skip tiny icons (<80px) — profile pics, platform badges
      if (src && src.startsWith('http') && (img.naturalWidth > 80 || img.width > 80 || !img.complete)) {
        ad.creative_urls.push({type: 'image', url: src});
      }
    });

    // Deduplicate creative URLs
    var seenUrls = new Set();
    ad.creative_urls = ad.creative_urls.filter(function(c) {
      if (seenUrls.has(c.url)) return false;
      seenUrls.add(c.url);
      return true;
    });

    // Media type detection
    var videoCreatives = ad.creative_urls.filter(function(c) { return c.type === 'video'; });
    var imageCreatives = ad.creative_urls.filter(function(c) { return c.type === 'image'; });
    if (videoCreatives.length > 0) {
      ad.media_type = 'video';
    } else if (imageCreatives.length > 2) {
      ad.media_type = 'carousel';
    } else if (imageCreatives.length > 0) {
      ad.media_type = 'image';
    } else {
      ad.media_type = 'unknown';
    }

    // Landing page URL — external links (not facebook/instagram)
    card.querySelectorAll('a[href]').forEach(function(a) {
      var href = a.href;
      if (href && !href.includes('facebook.com') && !href.includes('instagram.com') &&
          href.startsWith('http') && !ad.landing_url) {
        ad.landing_url = href;
      }
    });

    // Ad library URL
    var linkEl = card.querySelector('a[href*="ads/library/?id="], a[href*="library/?id="]');
    if (linkEl) {
      ad.ad_library_url = linkEl.href;
      if (!ad.ad_id) {
        var idMatch = linkEl.href.match(/[?&]id=(\d+)/);
        if (idMatch) ad.ad_id = idMatch[1];
      }
    }

    // "See ad details" link — useful for getting full ad page
    card.querySelectorAll('a[href*="ads/library/?id="], span').forEach(function(el) {
      if (el.textContent.trim().toLowerCase().includes('see ad details')) {
        var detailLink = el.closest('a');
        if (detailLink) ad.detail_url = detailLink.href;
      }
    });

    // Only include if we have a Library ID (confirms this is a real ad card)
    var uniqueKey = ad.ad_id || ((ad.advertiser || '') + '|' + (ad.ad_text || '').substring(0, 100));
    if (ad.ad_id && !seen.has(uniqueKey)) {
      seen.add(uniqueKey);
      ads.push(ad);
    }
  });

  return JSON.stringify(ads);
})()
""".strip()


# ---------------------------------------------------------------------------
# URL building
# ---------------------------------------------------------------------------


def _build_search_url(
    query: str,
    country: str = "US",
    platform: str = "all",
    media_type: str = "all",
    search_type: str = "keyword",
) -> str:
    """Build a Meta Ad Library search URL with filters.

    Args:
        query: Keyword or advertiser name.
        country: 2-letter country code.
        platform: Platform filter.
        media_type: Media type filter.
        search_type: "keyword" for text search, "advertiser_and_keyword" for
                     combined search that also surfaces the advertiser's page ads.
    """
    encoded_query = urllib.parse.quote(query)

    # Base URL — always active ads, is_targeted_country=false for global results
    url = f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country={country}&is_targeted_country=false"

    # Always use keyword_unordered for broader match (finds ads where query words
    # appear in any order in the advertiser name or ad content)
    url += f"&q={encoded_query}&search_type=keyword_unordered"

    if media_type != "all":
        media_map = {"image": "image", "video": "video", "carousel": "meme"}
        url += f"&media_type={media_map.get(media_type, 'all')}"
    else:
        url += "&media_type=all"

    if platform != "all":
        platform_map = {
            "facebook": "facebook",
            "instagram": "instagram",
            "audience_network": "audience_network",
            "messenger": "messenger",
        }
        url += f"&publisher_platforms={platform_map.get(platform, '')}"

    return url


# ---------------------------------------------------------------------------
# Direct CDP search (no browser-use agent, fast)
# ---------------------------------------------------------------------------


async def _cdp_search_keyword(
    keyword: str,
    max_results: int,
    country: str,
    platform: str,
    media_type: str,
    screenshot_dir: Path | None,
    search_type: str = "keyword",
) -> list[dict]:
    """Search Meta Ad Library for a keyword using direct CDP commands.

    Opens a new tab, navigates to the Ad Library search URL, scrolls to load
    results, and runs JS to extract ad card data. No AI agent overhead.
    """
    import websockets  # type: ignore

    search_url = _build_search_url(
        keyword,
        country=country,
        platform=platform,
        media_type=media_type,
        search_type=search_type,
    )
    print(f"    URL: {search_url}")

    # Close any existing Ad Library tabs to avoid stale data
    try:
        targets_raw = _cdp_http("/json/list", timeout=5)
        targets = json.loads(targets_raw)
        for tab in targets:
            tab_url = tab.get("url", "")
            if "facebook.com/ads/library" in tab_url:
                try:
                    _cdp_http(f"/json/close/{tab['id']}", timeout=3)
                except Exception:
                    pass
        await asyncio.sleep(1)
    except Exception:
        pass

    # Create a new tab
    new_tab_raw = _cdp_http(
        f"/json/new?{urllib.parse.quote(search_url, safe='')}", method="PUT"
    )
    new_tab = json.loads(new_tab_raw)
    ws_url = new_tab["webSocketDebuggerUrl"]
    tab_id = new_tab["id"]

    all_ads: list[dict] = []
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

            # Wait for initial page load — Meta Ad Library can be slow
            print(f"    Searching: {keyword}")
            await asyncio.sleep(10)

            # Dismiss any cookie consent or popup modals
            for _ in range(2):
                await send_cmd("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Escape", "code": "Escape",
                    "windowsVirtualKeyCode": 27, "nativeVirtualKeyCode": 27,
                })
                await asyncio.sleep(0.5)

            # Try clicking "Allow all cookies" or similar consent buttons
            consent_js = """
            (function() {
              var buttons = document.querySelectorAll('button, [role="button"]');
              for (var i = 0; i < buttons.length; i++) {
                var text = buttons[i].textContent.toLowerCase().trim();
                if (text.includes('allow') && text.includes('cookie')) {
                  buttons[i].click();
                  return 'clicked_consent';
                }
                if (text === 'accept all' || text === 'allow all' || text === 'allow essential and optional cookies') {
                  buttons[i].click();
                  return 'clicked_consent';
                }
              }
              return 'no_consent_needed';
            })()
            """.strip()
            await send_cmd("Runtime.evaluate", {"expression": consent_js})
            await asyncio.sleep(2)

            # Scroll and extract in rounds — progressive scroll with longer waits
            # for lazy-loaded content
            for scroll_round in range(10):
                # Progressive scroll: start small, go bigger to trigger lazy loads
                scroll_amount = 1200 + (scroll_round * 300)
                await send_cmd("Runtime.evaluate", {
                    "expression": f"window.scrollBy(0, {scroll_amount})",
                })
                # Longer waits on later rounds — Meta lazy-loads deeper results
                wait_time = 3 if scroll_round < 4 else 4
                await asyncio.sleep(wait_time)

                # Extract ads
                result = await send_cmd("Runtime.evaluate", {
                    "expression": JS_EXTRACT_ADS,
                    "returnByValue": True,
                })
                value = result.get("result", {}).get("result", {}).get("value", "[]")
                try:
                    ads = json.loads(value) if isinstance(value, str) else value
                    if isinstance(ads, list) and len(ads) > len(all_ads):
                        all_ads = ads
                        print(f"    Round {scroll_round + 1}: {len(all_ads)} ads found")
                except (json.JSONDecodeError, TypeError):
                    pass

                if len(all_ads) >= max_results:
                    break

            # Take screenshots if requested
            if screenshot_dir and all_ads:
                screenshot_dir.mkdir(parents=True, exist_ok=True)
                try:
                    screenshot_result = await send_cmd("Page.captureScreenshot", {
                        "format": "png",
                        "captureBeyondViewport": True,
                    })
                    if "result" in screenshot_result and "data" in screenshot_result["result"]:
                        import base64
                        screenshot_path = screenshot_dir / f"meta_ads_{keyword.replace(' ', '_')}.png"
                        screenshot_bytes = base64.b64decode(screenshot_result["result"]["data"])
                        screenshot_path.write_bytes(screenshot_bytes)
                        print(f"    Screenshot saved: {screenshot_path}")
                        # Tag ads with the screenshot path
                        for ad in all_ads:
                            ad["screenshot_path"] = str(screenshot_path)
                except Exception as e:
                    print(f"    Screenshot error: {e}", file=sys.stderr)

    except Exception as e:
        print(f"    CDP error for '{keyword}': {e}", file=sys.stderr)
    finally:
        # Close the tab
        try:
            _cdp_http(f"/json/close/{tab_id}", timeout=5)
        except Exception:
            pass

    # Ensure every ad has a direct, clickable Meta Ad Library URL derived from ad_id.
    # The in-page scrape is unreliable on newer Meta layouts — this guarantees coverage.
    for ad in all_ads:
        ad_id = ad.get("ad_id")
        if ad_id and not ad.get("ad_library_url"):
            ad["ad_library_url"] = f"https://www.facebook.com/ads/library/?id={ad_id}"

    return all_ads[:max_results]


# ---------------------------------------------------------------------------
# Result building and summary
# ---------------------------------------------------------------------------


def _build_summary(all_results: dict[str, list[dict]]) -> dict:
    """Build a summary of the search results with advertiser breakdown."""
    total_ads = sum(len(ads) for ads in all_results.values())

    keyword_breakdown = {}
    advertiser_counts: dict[str, dict] = {}

    for kw, ads in all_results.items():
        kw_advertisers = set()
        for ad in ads:
            advertiser = ad.get("advertiser", "Unknown")
            kw_advertisers.add(advertiser)
            if advertiser not in advertiser_counts:
                advertiser_counts[advertiser] = {"ad_count": 0, "platforms": set()}
            advertiser_counts[advertiser]["ad_count"] += 1
            for p in ad.get("platforms", []):
                advertiser_counts[advertiser]["platforms"].add(p)

        keyword_breakdown[kw] = {
            "ad_count": len(ads),
            "advertisers": sorted(kw_advertisers),
        }

    # Top advertisers sorted by ad count
    top_advertisers = sorted(
        [
            {
                "name": name,
                "ad_count": data["ad_count"],
                "platforms": sorted(data["platforms"]),
            }
            for name, data in advertiser_counts.items()
        ],
        key=lambda x: x["ad_count"],
        reverse=True,
    )[:20]

    return {
        "total_ads_found": total_ads,
        "keyword_breakdown": keyword_breakdown,
        "top_advertisers": top_advertisers,
    }


def _format_report(output: dict) -> str:
    """Format the output as a human-readable report."""
    lines = []
    summary = output.get("summary", {})
    lines.append("Meta Ad Library Research Report")
    lines.append("=" * 55)

    keywords = output.get("search_keywords", [])
    advertisers = output.get("advertisers", [])
    if keywords:
        lines.append(f"Keywords: {', '.join(keywords)}")
    if advertisers:
        lines.append(f"Competitors: {', '.join(advertisers)}")

    lines.append(f"Total ads found: {summary.get('total_ads_found', 0)}")
    proven_count = summary.get("proven_performers_count", 0)
    if proven_count:
        lines.append(f"Proven performers (90+ days): {proven_count}")
    lines.append("")

    # Keyword/query breakdown
    for kw, info in summary.get("keyword_breakdown", {}).items():
        lines.append(f"  [{kw}] {info['ad_count']} ads from {len(info.get('advertisers', []))} advertisers")

    lines.append("")
    lines.append("Top Advertisers:")
    for adv in summary.get("top_advertisers", [])[:10]:
        platforms = ", ".join(adv.get("platforms", []))
        lines.append(f"  - {adv['name']}: {adv['ad_count']} ads ({platforms})")

    # Proven performers section
    proven = output.get("proven_performers", [])
    if proven:
        lines.append("")
        lines.append("Proven Performers (running 90+ days):")
        lines.append("-" * 55)
        for i, ad in enumerate(proven[:10], 1):
            days = ad.get("days_running", "?")
            lines.append(f"  {i}. {ad.get('advertiser', 'Unknown')} ({days} days)")
            if ad.get("ad_text"):
                text_preview = ad["ad_text"][:100] + ("..." if len(ad.get("ad_text", "")) > 100 else "")
                lines.append(f"     Text: {text_preview}")
            if ad.get("media_type"):
                lines.append(f"     Media: {ad['media_type']}")
            if ad.get("ad_library_url"):
                lines.append(f"     URL: {ad['ad_library_url']}")
            lines.append("")

    # All ad details
    lines.append("")
    lines.append("All Ad Details:")
    lines.append("-" * 55)

    for kw, ads in output.get("all_results", {}).items():
        lines.append(f"\n  Query: {kw}")
        for i, ad in enumerate(ads, 1):
            longevity = ""
            if ad.get("days_running") is not None:
                longevity = f" [{ad['days_running']}d"
                tag = ad.get("longevity_tag", "")
                if tag:
                    longevity += f" - {tag}"
                longevity += "]"

            lines.append(f"  {i}. {ad.get('advertiser', 'Unknown')}{longevity}")
            if ad.get("ad_text"):
                text_preview = ad["ad_text"][:120] + ("..." if len(ad.get("ad_text", "")) > 120 else "")
                lines.append(f"     Text: {text_preview}")
            if ad.get("headline"):
                lines.append(f"     Headline: {ad['headline']}")
            if ad.get("cta"):
                lines.append(f"     CTA: {ad['cta']}")
            if ad.get("media_type"):
                lines.append(f"     Media: {ad['media_type']}")
            if ad.get("platforms"):
                lines.append(f"     Platforms: {', '.join(ad['platforms'])}")
            if ad.get("start_date"):
                lines.append(f"     Running since: {ad['start_date']}")
            if ad.get("landing_url"):
                lines.append(f"     Landing: {ad['landing_url']}")

            # Show creative URLs
            creatives = ad.get("creative_urls", [])
            if creatives:
                for c in creatives[:3]:
                    lines.append(f"     Creative ({c['type']}): {c['url'][:120]}")

            if ad.get("ad_library_url"):
                lines.append(f"     Ad Library: {ad['ad_library_url']}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main search flow
# ---------------------------------------------------------------------------


def _compute_ad_longevity(ads: list[dict]) -> list[dict]:
    """Add days_running and longevity_tag to each ad based on start_date.

    Long-running ads are likely high performers — tag them for easy filtering.
    Returns a new list (immutable pattern).
    """
    from datetime import datetime

    today = datetime.now()
    enriched = []

    for ad in ads:
        enriched_ad = {**ad}  # shallow copy — immutable
        start_date_str = ad.get("start_date")
        if start_date_str:
            try:
                # Parse "Mar 15, 2026" or "Mar 15 2026" formats
                cleaned = start_date_str.replace(",", "")
                parsed = datetime.strptime(cleaned, "%b %d %Y")
                days = (today - parsed).days
                enriched_ad["days_running"] = max(0, days)

                if days >= LONGEVITY_PROVEN:
                    enriched_ad["longevity_tag"] = "proven_performer"
                elif days >= LONGEVITY_ESTABLISHED:
                    enriched_ad["longevity_tag"] = "established"
                elif days >= LONGEVITY_TESTING:
                    enriched_ad["longevity_tag"] = "testing"
                else:
                    enriched_ad["longevity_tag"] = "new"
            except (ValueError, TypeError):
                enriched_ad["days_running"] = None
                enriched_ad["longevity_tag"] = "unknown"
        else:
            enriched_ad["days_running"] = None
            enriched_ad["longevity_tag"] = "unknown"

        enriched.append(enriched_ad)

    return enriched


async def browse_meta_ads(
    keywords: list[str],
    max_results: int = DEFAULT_RESULTS_PER_KEYWORD,
    country: str = "US",
    platform: str = "all",
    media_type: str = "all",
    screenshot_dir: Path | None = None,
    max_total_seconds: int = 300,
    search_type: str = "keyword",
    advertisers: list[str] | None = None,
) -> dict:
    """Search Meta Ad Library for ads matching keywords and/or advertiser names.

    Args:
        keywords: Keywords to search.
        max_results: Max ads to collect per keyword.
        country: Country code for ad targeting (default US).
        platform: Platform filter (all, facebook, instagram).
        media_type: Media type filter (all, image, video, carousel).
        screenshot_dir: Optional directory for saving screenshots.
        max_total_seconds: Hard time limit for the entire search.
        search_type: "keyword" or "advertiser_and_keyword".
        advertisers: Optional list of advertiser/competitor names to search
                     separately (always uses advertiser_and_keyword mode).

    Returns:
        Complete results dict with search_keywords, filters, summary, all_results.
    """
    if not _ensure_chrome_with_cdp():
        raise SearchError("Cannot start research browser. Please ensure Chrome is installed.")

    global_start = time.time()

    def time_remaining() -> float:
        return max(0, max_total_seconds - (time.time() - global_start))

    # Build the full search queue: keywords + advertisers
    # All searches use keyword_unordered for broadest match
    search_queue: list[tuple[str, str]] = []  # (query, search_type)
    for kw in keywords:
        search_queue.append((kw, "keyword"))
    for adv in (advertisers or []):
        search_queue.append((adv, "keyword"))

    all_queries = [q for q, _ in search_queue]
    print(f"Searching Meta Ad Library for {len(search_queue)} query(ies)... (max {max_total_seconds}s total)")
    all_results: dict[str, list[dict]] = {}

    for query, st in search_queue:
        remaining = time_remaining()
        if remaining < 10:
            print(f"    Time limit reached, skipping remaining queries.", file=sys.stderr)
            all_results[query] = []
            continue

        per_keyword_timeout = min(120, remaining)
        try:
            ads = await asyncio.wait_for(
                _cdp_search_keyword(
                    query, max_results, country, platform, media_type,
                    screenshot_dir, search_type=st,
                ),
                timeout=per_keyword_timeout,
            )
            # Enrich with longevity scoring
            all_results[query] = _compute_ad_longevity(ads)
        except asyncio.TimeoutError:
            print(f"    Timeout searching '{query}', skipping.", file=sys.stderr)
            all_results[query] = []
        except Exception as e:
            print(f"    Error searching '{query}': {e}", file=sys.stderr)
            all_results[query] = []

    total = sum(len(v) for v in all_results.values())
    print(f"Search complete: {total} ads collected across {len(search_queue)} query(ies)")

    # Build output
    summary = _build_summary(all_results)

    # Add proven performers list (ads running 90+ days)
    proven_performers = []
    for ads in all_results.values():
        for ad in ads:
            if ad.get("longevity_tag") == "proven_performer":
                proven_performers.append(ad)
    proven_performers.sort(key=lambda x: x.get("days_running", 0), reverse=True)
    summary["proven_performers_count"] = len(proven_performers)

    output = {
        "search_keywords": keywords,
        "advertisers": advertisers or [],
        "filters": {
            "platform": platform,
            "media_type": media_type,
            "country": country,
            "search_type": search_type,
        },
        "summary": summary,
        "proven_performers": proven_performers[:20],
        "all_results": all_results,
    }

    return output


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _validate_inputs(args: argparse.Namespace) -> None:
    """Validate CLI arguments."""
    if not args.keywords and not args.advertisers:
        raise ValidationError("At least one keyword or --advertiser is required.")

    if args.max_results < 1 or args.max_results > MAX_RESULTS_PER_KEYWORD:
        raise ValidationError(f"--max-results must be between 1 and {MAX_RESULTS_PER_KEYWORD}")

    if args.platform not in PLATFORM_FILTERS:
        raise ValidationError(f"--platform must be one of: {', '.join(PLATFORM_FILTERS)}")

    if args.media_type not in MEDIA_TYPE_FILTERS:
        raise ValidationError(f"--media-type must be one of: {', '.join(MEDIA_TYPE_FILTERS)}")

    if len(args.country) != 2:
        raise ValidationError("--country must be a 2-letter country code (e.g., US, UK, CA)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Browse Meta Ad Library by keywords and competitor names for ad research",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Search by keyword
  %(prog)s "credit building app"

  # Search by competitor names (advertiser search)
  %(prog)s --advertiser "Example Finance" --advertiser "Example Credit" --advertiser "Example Banking"

  # Combine keywords + competitors
  %(prog)s "credit building" --advertiser "Example Finance" --advertiser "Example Credit"

  # Filter by platform and media type
  %(prog)s "AI research tool" --platform instagram --media-type video

  # Save to file
  %(prog)s "fintech app" -n 30 -o output/ads_research.json
        """,
    )
    parser.add_argument("keywords", nargs="*", default=[], help="Keywords to search")
    parser.add_argument("--advertiser", "-a", action="append", default=[], dest="advertisers", help="Competitor/advertiser name to search (repeatable)")
    parser.add_argument("-n", "--max-results", type=int, default=DEFAULT_RESULTS_PER_KEYWORD, help=f"Max ads per keyword (default {DEFAULT_RESULTS_PER_KEYWORD})")
    parser.add_argument("-o", "--output", type=str, default=None, help="Save JSON report to file")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of formatted report")
    parser.add_argument("--platform", type=str, default="all", choices=PLATFORM_FILTERS, help="Platform filter (default: all)")
    parser.add_argument("--media-type", type=str, default="all", choices=MEDIA_TYPE_FILTERS, help="Media type filter (default: all)")
    parser.add_argument("--country", type=str, default="US", help="Country code for ad targeting (default: US)")
    parser.add_argument("--screenshot-dir", type=str, default=None, help="Directory to save ad screenshots")

    args = parser.parse_args()

    # Require at least one keyword or advertiser
    if not args.keywords and not args.advertisers:
        parser.error("At least one keyword or --advertiser is required.")

    try:
        _validate_inputs(args)
    except ValidationError as e:
        print(f"Validation error: {e}", file=sys.stderr)
        sys.exit(1)

    screenshot_path = Path(args.screenshot_dir) if args.screenshot_dir else None

    try:
        output = asyncio.run(
            browse_meta_ads(
                keywords=args.keywords,
                max_results=args.max_results,
                country=args.country,
                platform=args.platform,
                media_type=args.media_type,
                screenshot_dir=screenshot_path,
                advertisers=args.advertisers,
            )
        )
    except SearchError as e:
        print(f"Search error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    finally:
        _stop_research_browser()

    # Output results
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(output, indent=2, default=str))
        print(f"\nResults saved to: {output_path}")
    elif args.json:
        print(json.dumps(output, indent=2, default=str))
    else:
        report = _format_report(output)
        print(report)
        # Also print JSON summary to stderr for programmatic use
        print(f"\n(Use --json for machine-readable output, -o FILE to save)", file=sys.stderr)


if __name__ == "__main__":
    main()
