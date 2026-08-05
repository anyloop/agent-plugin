#!/usr/bin/env python3
"""
Mine Report Keywords — Expand trend research from the initial report's example videos.

The initial social content research report showcases real winning videos. This script
extracts those example-video URLs, collects their captions/descriptions (from the
initial-research browse JSONs when provided, else via oEmbed / og-tags), pulls the
hashtags and phrasing the winning videos actually use, and synthesizes an expanded
per-platform keyword list for the social-content-strategist trend browse.

Usage:
  uv run --project skills/content-strategy-generator/runtime \
    skills/content-strategy-generator/runtime/mine_report_keywords.py \
    --report {brandFolder}/{product}_social_content_research_{date}.md \
    --captions-from {initialBrandFolder}/browse_tiktok.json \
    --captions-from {initialBrandFolder}/browse_instagram.json \
    --product-name "Example Product" --niche "food scanner apps" \
    -o {workspace}/expanded_keywords.json
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

_skill_dir = Path(__file__).resolve().parent.parent
_project_root = _skill_dir.parent.parent
for env_file in [_skill_dir / ".env", _project_root / ".env", _project_root / ".env.production"]:
    if env_file.exists():
        load_dotenv(env_file)

GENERIC_TAGS = {
    "fyp", "fypage", "foryou", "foryoupage", "viral", "trending", "shorts", "reels",
    "tiktok", "instagram", "youtube", "creatorsearchinsights", "xyzbca", "explore",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def extract_urls(report_path: Path) -> list[str]:
    if report_path.suffix.lower() == ".pdf":
        import fitz

        doc = fitz.open(str(report_path))
        text = "\n".join(page.get_text() for page in doc)
        links = []
        for page in doc:
            links += [l.get("uri", "") for l in page.get_links()]
        doc.close()
        text += "\n" + "\n".join(links)
    else:
        text = report_path.read_text()
    urls = re.findall(r"https?://(?:www\.)?(?:tiktok\.com|instagram\.com|youtube\.com|youtu\.be)/\S+?(?=[)\s\]|]|$)", text)
    seen, out = set(), []
    for u in urls:
        u = u.rstrip(").,")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def video_id(url: str) -> str:
    m = re.search(r"/video/(\d+)", url) or re.search(r"/reel/([A-Za-z0-9_-]+)", url) \
        or re.search(r"/shorts/([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else url


def captions_from_files(urls: list[str], files: list[Path]) -> dict[str, str]:
    """Search initial-research browse JSONs for captions/descs matching the URLs' video ids."""
    ids = {video_id(u): u for u in urls}
    found: dict[str, str] = {}

    def walk(node):
        if isinstance(node, dict):
            nid = str(node.get("id") or node.get("shortcode") or node.get("video_id") or "")
            text = node.get("desc") or node.get("caption") or node.get("title") or ""
            if nid in ids and text:
                found.setdefault(ids[nid], str(text))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for f in files:
        try:
            walk(json.loads(f.read_text()))
        except Exception as e:  # noqa: BLE001
            log(f"  warn: could not read {f}: {e}")
    return found


def fetch_caption(url: str) -> str:
    """Network fallback: oEmbed for TikTok/YouTube, og-tags for Instagram."""
    try:
        if "tiktok.com" in url:
            api = f"https://www.tiktok.com/oembed?url={urllib.parse.quote(url, safe='')}"
            with urllib.request.urlopen(urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
                return json.loads(r.read().decode()).get("title", "")
        if "youtube.com" in url or "youtu.be" in url:
            api = f"https://www.youtube.com/oembed?url={urllib.parse.quote(url, safe='')}&format=json"
            with urllib.request.urlopen(urllib.request.Request(api, headers={"User-Agent": "Mozilla/5.0"}), timeout=20) as r:
                return json.loads(r.read().decode()).get("title", "")
        if "instagram.com" in url:
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"})
            with urllib.request.urlopen(req, timeout=25) as r:
                page = r.read().decode("utf-8", errors="replace")
            m = re.search(r'<meta property="og:title" content="([^"]*)"', page)
            return html_mod.unescape(m.group(1)) if m else ""
    except Exception as e:  # noqa: BLE001
        log(f"  warn: caption fetch failed for {url[:60]}: {e}")
    return ""


def call_gemini(prompt: str, api_key: str, model: str = "gemini-2.5-flash") -> dict:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 8192,
                             "response_mime_type": "application/json"},
    }
    req = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        result = json.loads(resp.read().decode())
    text = "".join(p["text"] for p in result["candidates"][0]["content"]["parts"] if "text" in p)
    if "```" in text:
        text = text.split("```json" if "```json" in text else "```", 1)[1].split("```", 1)[0]
    return json.loads(re.sub(r",\s*([}\]])", r"\1", text.strip()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Mine keywords/hashtags from example videos (report-driven or standalone)")
    parser.add_argument("--report", help="Initial research report (.md or .pdf). Optional in standalone mode.")
    parser.add_argument("--video", action="append", default=[],
                        help="Example video URL the client likes (repeatable). Mined alongside/instead of the report's examples.")
    parser.add_argument("--description", default="",
                        help="Product description - grounds the keyword synthesis when no report is given.")
    parser.add_argument("--profile", help="product_profile.json from the product-research skill; enables the app-keyword rule and competitor app variants")
    parser.add_argument("--captions-from", action="append", default=[],
                        help="Initial-research browse JSONs to harvest captions from (repeatable)")
    parser.add_argument("--product-name", required=True)
    parser.add_argument("--niche", required=True, help="Niche label, e.g. 'food scanner apps'")
    parser.add_argument("--base-keywords", help="Existing trend_keywords.json to avoid duplicating")
    parser.add_argument("--model", default="gemini-2.5-flash")
    parser.add_argument("-o", "--output", required=True, help="Output expanded_keywords.json")
    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    urls = []
    if args.report:
        urls = extract_urls(Path(args.report))
        log(f"{len(urls)} example-video URLs found in the report")
    for u in args.video:
        u = u.strip().rstrip(")").rstrip(",")
        if u and u not in urls:
            urls.append(u)
    if args.video:
        log(f"{len(args.video)} user-provided example videos added")
    if not urls and not args.description:
        print("Provide --report, --video URLs, or --description", file=sys.stderr)
        sys.exit(1)

    captions = captions_from_files(urls, [Path(f) for f in args.captions_from])
    log(f"{len(captions)} captions found in provided browse files")
    for u in urls:
        if u not in captions:
            cap = fetch_caption(u)
            if cap:
                captions[u] = cap
    log(f"{len(captions)}/{len(urls)} captions total after network fallback")

    tag_counts: Counter[str] = Counter()
    for cap in captions.values():
        for t in re.findall(r"#(\w+)", cap):
            t = t.lower()
            if t not in GENERIC_TAGS and len(t) > 2:
                tag_counts[t] += 1
    top_tags = [t for t, _ in tag_counts.most_common(40)]
    log(f"hashtags mined: {top_tags[:15]}...")

    base = {}
    if args.base_keywords and Path(args.base_keywords).exists():
        base = json.loads(Path(args.base_keywords).read_text())

    # App-keyword rule (same as initial-social-content-research): when the product
    # is an app, plain names drown in social search - "xxx app" variants are required.
    app_rule = ""
    if args.profile and Path(args.profile).exists():
        profile = json.loads(Path(args.profile).read_text())
        if profile.get("is_app"):
            comp_names = [c.get("name", "") for c in profile.get("known_competitor_candidates", [])][:6]
            app_rule = (
                "\nAPP-KEYWORD RULE (MANDATORY): this product is an APP. Every platform list MUST "
                "include 'xxx app' variants so app-related content surfaces: the category as an app "
                f"('{profile.get('niche_label', 'the niche')} app', 'best ... apps', '... app review'), "
                f"competitor app names with the word app ({', '.join(n + ' app' for n in comp_names if n)}), "
                "and app-review/comparison phrasings. At least half of each platform's keywords must "
                "be app-related; lifestyle/adjacent keywords fill the rest.\n"
            )

    context = f"Product description: {args.description}\n" if args.description else ""
    prompt = f"""You are expanding trend-research keywords for {args.product_name} ({args.niche}).
{context}
These winning example videos anchor the niche (from the initial report and/or provided by the client as videos they like). Their captions:
{json.dumps([{"url": u[:80], "caption": c[:200]} for u, c in captions.items()], indent=1, ensure_ascii=False)}

Hashtags mined from those captions (by frequency): {top_tags}

Existing keyword lists (do NOT repeat these):
{json.dumps(base, indent=1, ensure_ascii=False)[:2000]}

Produce NEW search keywords that ride the language the winning videos actually use:
- Turn strong hashtags into natural search phrases (e.g. #seedoilfree -> "seed oil free swaps")
- Capture recurring caption phrasings and series formats ("what i eat in a day", "shop with me")
- Stay relevant to the niche; prefer phrases a trend browse would surface fresh content for
- 8-12 per platform; TikTok/Instagram phrasing can differ from YouTube (YouTube favors questions/how-to)

{app_rule}
Return JSON:
{{"mined_hashtags": {json.dumps(top_tags[:25])},
 "tiktok": ["..."], "instagram": ["..."], "youtube": ["..."]}}"""
    log("Synthesizing expanded keywords with Gemini...")
    expanded = call_gemini(prompt, api_key, args.model)
    expanded["source"] = "mined from initial report example videos"
    expanded["captions_found"] = len(captions)

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(expanded, indent=2, ensure_ascii=False))
    log(f"Expanded keywords written to {out}")
    for plat in ("tiktok", "instagram", "youtube"):
        log(f"  {plat}: {expanded.get(plat, [])}")


if __name__ == "__main__":
    main()
