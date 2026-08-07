#!/usr/bin/env python3
"""
Instagram Reels discovery WITHOUT login — search-indexed reels + og-tag metrics,
with hashtag-driven keyword expansion.

The CDP browse path needs an Instagram session. This fallback needs none:
  1. Search the web (DuckDuckGo HTML endpoint) for indexed instagram.com/reel/ URLs
     matching each keyword.
  2. Fetch every candidate reel's og-tags with a bot User-Agent: real like count,
     caption, handle, thumbnail.
  3. Keep reels at or above --min-likes (default 10K; pass 50000 for the preferred
     tier of the minimum-engagement rule).
  4. If fewer than --target reels qualify, EXPAND: mine the hashtags from the
     accepted reels' captions and run another search round with them (up to
     --rounds rounds).

Usage:
  uv run --project skills/browse-instagram-reels/runtime \
    skills/browse-instagram-reels/runtime/discover_reels.py \
    "food scanner app" "yuka app" "grocery swap" \
    --min-likes 10000 --target 8 --rounds 3 \
    -o browse_instagram_discovered.json
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

BOT_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
GENERIC_TAGS = {"fyp", "fypage", "foryou", "foryoupage", "viral", "trending", "reels",
                "reelsinstagram", "instagram", "explore", "explorepage", "instagood"}


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_count(text: str) -> int:
    """'12.3K' / '1,234' / '2M' -> int."""
    m = re.match(r"([\d.,]+)\s*([KM]?)", text.strip(), re.IGNORECASE)
    if not m:
        return 0
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return 0
    unit = m.group(2).upper()
    return int(n * (1_000_000 if unit == "M" else 1_000 if unit == "K" else 1))


def _extract_reel_urls(hrefs: list[str], max_results: int) -> list[str]:
    urls = []
    for h in hrefs:
        if "uddg=" in h:
            h = urllib.parse.unquote(h.split("uddg=", 1)[1].split("&", 1)[0])
        m = re.search(r"(https://www\.instagram\.com/(?:[\w.]+/)?reel/[A-Za-z0-9_-]+)", h)
        if m:
            u = m.group(1) + "/"
            if u not in urls:
                urls.append(u)
    return urls[:max_results]


def ddg_search_reels(query: str, max_results: int = 12) -> list[str]:
    """Find indexed Reel URLs through public DuckDuckGo and Bing results."""
    q = urllib.parse.quote(f"site:instagram.com/reel {query}")
    for name, url, pause in (
        ("ddg", f"https://html.duckduckgo.com/html/?q={q}", 2.5),
        ("bing", f"https://www.bing.com/search?q={q}&count=20", 2.0),
    ):
        req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA,
                                                   "Accept-Language": "en-US,en;q=0.9"})
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                page = r.read().decode("utf-8", errors="replace")
            found = _extract_reel_urls(re.findall(r'href="([^"]+)"', page), max_results)
            time.sleep(pause)
            if found:
                return found
        except Exception as e:
            log(f"    {name} search failed for '{query}': {e}")
            time.sleep(pause)
    return []


def fetch_reel(url: str) -> dict | None:
    """Fetch a reel page's og-tags: likes, caption, handle, thumbnail."""
    req = urllib.request.Request(url, headers={"User-Agent": BOT_UA})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            page = r.read().decode("utf-8", errors="replace")
    except Exception:
        return None

    def og(prop):
        m = re.search(f'<meta property="og:{prop}" content="([^"]*)"', page)
        return html_mod.unescape(m.group(1)) if m else ""

    desc = og("description")
    title = og("title")
    if not desc and not title:
        return None
    likes = comments = 0
    m = re.match(r"([\d.,KM]+) likes, ([\d.,KM]+) comments", desc or "")
    if m:
        likes, comments = parse_count(m.group(1)), parse_count(m.group(2))
    handle = ""
    m = re.search(r"instagram\.com/([\w.]+)/reel/", og("url") or url)
    if m and m.group(1) != "www":
        handle = m.group(1)
    if not handle:
        m = re.search(r"- (@?[\w.]+) on ", title or "") or re.search(r"\(@([\w.]+)\)", title or "")
        if m:
            handle = m.group(1).lstrip("@")
    caption = ""
    m = re.search(r'on [A-Z][a-z]+ \d+, \d{4}: "(.*)"?$', desc or "", re.DOTALL)
    if m:
        caption = m.group(1)[:300]
    elif title:
        m = re.search(r':\s*"(.*)"?$', title, re.DOTALL)
        caption = (m.group(1) if m else title)[:300]
    sc = re.search(r"/reel/([A-Za-z0-9_-]+)", url)
    return {
        "url": url,
        "shortcode": sc.group(1) if sc else "",
        "handle": f"@{handle}" if handle else "",
        "likes": likes,
        "comments": comments,
        "caption": caption,
        "thumbnail": og("image"),
        "hashtags": [t.lower() for t in re.findall(r"#(\w+)", caption)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Login-less Instagram Reels discovery with hashtag expansion")
    parser.add_argument("keywords", nargs="+", help="Seed search keywords")
    parser.add_argument("--min-likes", type=int, default=10_000,
                        help="Keep reels at/above this like count (default 10000; the hard floor)")
    parser.add_argument("--target", type=int, default=8, help="Stop once this many reels qualify")
    parser.add_argument("--rounds", type=int, default=3,
                        help="Max search rounds (round 2+ uses hashtags mined from accepted reels)")
    parser.add_argument("--per-query", type=int, default=10, help="Reel URLs to check per query")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    seen: set[str] = set()
    accepted: list[dict] = []
    rejected = 0
    queries = list(args.keywords)
    used_queries: set[str] = set()

    for rnd in range(1, args.rounds + 1):
        round_queries = [q for q in queries if q not in used_queries]
        if not round_queries:
            log(f"round {rnd}: no new queries to run, stopping")
            break
        log(f"── round {rnd}: {len(round_queries)} queries ──")
        for q in round_queries:
            used_queries.add(q)
            urls = ddg_search_reels(q, args.per_query)
            log(f"  '{q}': {len(urls)} indexed reels")
            for u in urls:
                key = re.search(r"/reel/([A-Za-z0-9_-]+)", u).group(1)
                if key in seen:
                    continue
                seen.add(key)
                reel = fetch_reel(u)
                time.sleep(1.2)
                if not reel:
                    continue
                if reel["likes"] >= args.min_likes:
                    reel["found_via"] = q
                    accepted.append(reel)
                    log(f"    + {reel['handle']} {reel['likes']:,} likes  {reel['caption'][:40]!r}")
                else:
                    rejected += 1
            if len(accepted) >= args.target:
                break
        if len(accepted) >= args.target:
            log(f"target reached: {len(accepted)} reels >= {args.min_likes:,} likes")
            break
        # EXPAND: mine hashtags from accepted reels for the next round
        tags = Counter()
        for r in accepted:
            for t in r["hashtags"]:
                if t not in GENERIC_TAGS and len(t) > 2:
                    tags[t] += 1
        expansion = [f"#{t}" for t, _ in tags.most_common(8) if f"#{t}" not in used_queries]
        if expansion:
            log(f"  expanding with mined hashtags: {expansion}")
            queries += expansion
        else:
            log("  no new hashtags to expand with")

    accepted.sort(key=lambda r: r["likes"], reverse=True)
    out = {
        "source": "search-discovery (DuckDuckGo-indexed reels + og-tags, no login)",
        "min_likes": args.min_likes,
        "queries_used": sorted(used_queries),
        "accepted": accepted,
        "rejected_below_threshold": rejected,
    }
    with open(args.output, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    log(f"Saved {len(accepted)} reels >= {args.min_likes:,} likes ({rejected} below) -> {args.output}")
    if not accepted:
        sys.exit(2)


if __name__ == "__main__":
    main()
