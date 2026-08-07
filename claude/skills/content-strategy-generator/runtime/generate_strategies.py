#!/usr/bin/env python3
"""
Content Strategy Generator — Turn analyzed trend videos into copy-paste-ready content strategies.

Part of the social-content-strategist workflow. Inputs: the initial social content
research report (md or pdf), a batch of inspiration-video candidates already analyzed by
trend-video-understanding, and the strategy history (past batches + user-provided past
inspiration videos). Output: a markdown strategy report where every strategy block can be
copied and pasted straight into Adant (https://adant.ai), plus an updated history file.

Core rules:
- Past inspiration videos (history) are hard-excluded by URL.
- Concepts too similar to past strategies are excluded through authenticated AdAnt comparison.
- Adapted scripts / text overlays keep the source hook and viral format - small changes only.

Usage:
  uv run --project skills/content-strategy-generator/runtime \
    skills/content-strategy-generator/runtime/generate_strategies.py \
    --report example-product/example-product_social_content_research_YYYY-MM-DD.md \
    --candidates strategy_workspace/candidates.json \
    --product-name "Example Product" --product-url "https://example.com/" \
    --history example-product_strategy_history.json \
    --count 8 \
    -o example-product_content_strategies_YYYY-MM-DD.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

_skill_dir = Path(__file__).resolve().parent.parent
_plugin_root = _skill_dir.parent.parent
sys.path.insert(0, str(_plugin_root / "runtime"))

from adant_agent import ask_adant  # noqa: E402

GENERAL_INSTRUCTIONS = """Analyze [INSPIRATION VIDEO URL]
with character as [YOUR AVATAR IMAGE], no text overlay. Only regenerate the first frame for review. You can ask to change character cloth, background setting and anything.
Review the first frame. If it looks good, proceed to rewrite the script to promote the product instead.
When the script is good, proceed with video generation.
Video generation: now clone the video with below model choice:
use Seedance 2.0
Just mention in the instruction using natural language"""


def log(msg: str) -> None:
    print(msg, flush=True)


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


def read_report(path: Path) -> str:
    """Read the initial research report - markdown directly, PDF via pymupdf."""
    if path.suffix.lower() == ".pdf":
        import fitz  # pymupdf

        doc = fitz.open(str(path))
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
        return text
    return path.read_text()


def load_history(path: Path | None) -> dict:
    if path and path.exists():
        return json.loads(path.read_text())
    return {"strategies": [], "excluded_urls": []}


def past_urls(history: dict) -> set[str]:
    urls = {s.get("inspiration_url", "") for s in history.get("strategies", [])}
    urls |= set(history.get("excluded_urls", []))
    return {u.rstrip("/") for u in urls if u}


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate copy-paste content strategies from analyzed trend videos")
    parser.add_argument("--report", help="Initial research report (.md or .pdf). Optional when --product-description is given.")
    parser.add_argument("--product-description", default="",
                        help="Standalone mode: product description used as context instead of a report.")
    parser.add_argument("--candidates", required=True,
                        help="JSON list of candidates: [{url, platform, handle, metric, posted, analysis_path}]")
    parser.add_argument("--product-name", required=True)
    parser.add_argument("--product-url", required=True)
    parser.add_argument("--history", help="Strategy history JSON (past batches / user-provided past inspiration videos)")
    parser.add_argument("--history-out", help="Where to write the updated history (default: --history path, or {product}_strategy_history.json next to output)")
    parser.add_argument("--count", type=int, default=8, help="Target number of strategies (5-10)")
    parser.add_argument("-o", "--output", required=True, help="Output markdown path")
    args = parser.parse_args()

    count = max(5, min(10, args.count))
    if args.report:
        report_text = read_report(Path(args.report))[:24000]
    elif args.product_description:
        report_text = f"(No initial research report - standalone mode.)\nProduct description: {args.product_description}"
    else:
        print("Provide --report or --product-description", file=sys.stderr)
        sys.exit(1)
    history_path = Path(args.history) if args.history else None
    history = load_history(history_path)
    excluded = past_urls(history)

    candidates = json.loads(Path(args.candidates).read_text())
    usable = []
    for c in candidates:
        if c["url"].rstrip("/") in excluded:
            log(f"  skip (in history): {c['url']}")
            continue
        apath = Path(c["analysis_path"])
        if not apath.exists():
            log(f"  skip (no analysis): {c['url']}")
            continue
        analysis = json.loads(apath.read_text())
        if analysis.get("status") != "ok":
            log(f"  skip ({analysis.get('status')}): {c['url']}")
            continue
        usable.append({**c, "fingerprint": analysis.get("fingerprint", {}),
                       "narrative": analysis.get("narrative_analysis", "")[:2500]})
    log(f"{len(usable)} usable candidates after URL exclusion ({len(candidates) - len(usable)} dropped)")

    # ── Minimum-engagement rule: >=50K preferred, >=10K hard floor ──────
    above_floor = [c for c in usable if parse_metric(c.get("metric", "")) >= MIN_VIEWS_FLOOR]
    for c in usable:
        if c not in above_floor:
            log(f"  drop (<10K views hard floor): {c['url']} ({c.get('metric')})")
    preferred = [c for c in above_floor if parse_metric(c.get("metric", "")) >= MIN_VIEWS_PREFERRED]
    if len(preferred) >= count:
        for c in above_floor:
            if c not in preferred:
                log(f"  drop (<50K, enough >=50K candidates): {c['url']} ({c.get('metric')})")
        usable = preferred
    else:
        if len(above_floor) < len(usable):
            log(f"  only {len(preferred)} candidates >=50K - falling back to the 10K floor")
        usable = above_floor
    log(f"{len(usable)} candidates after minimum-engagement rule")
    if not usable:
        print("No usable candidates - nothing to do", file=sys.stderr)
        sys.exit(2)

    # ── Novelty filter vs past strategy concepts ────────────────────────
    if history.get("strategies"):
        past_concepts = [
            {"inspiration_url": s.get("inspiration_url"), "viral_format": s.get("viral_format"),
             "concept_summary": s.get("concept_summary")}
            for s in history["strategies"]
        ]
        novelty_prompt = f"""You are deduplicating content concepts for a short-form content strategist.

PAST STRATEGY CONCEPTS (already delivered to the client - must NOT be repeated):
{json.dumps(past_concepts, indent=1, ensure_ascii=False)}

NEW CANDIDATES:
{json.dumps([{"url": c["url"], "viral_format": c["fingerprint"].get("viral_format"), "hook": c["fingerprint"].get("hook"), "concept_summary": c["fingerprint"].get("concept_summary")} for c in usable], indent=1, ensure_ascii=False)}

For each candidate, decide if its CONCEPT is essentially the same as a past strategy concept
(same viral format AND same core idea - e.g. two "scan a product in a store and react to the score"
videos are the same concept even if the creator differs). A shared broad format with a genuinely
different angle/hook/story is NOT a duplicate.

Return JSON: {{"verdicts": [{{"url": "...", "too_similar": true/false, "reason": "one line"}}]}}"""
        verdicts = ask_adant(novelty_prompt, title=f"Strategy dedupe: {args.product_name}")
        similar = {v["url"] for v in verdicts.get("verdicts", []) if v.get("too_similar")}
        for v in verdicts.get("verdicts", []):
            if v.get("too_similar"):
                log(f"  drop (concept overlap): {v['url']} - {v.get('reason', '')}")
        usable = [c for c in usable if c["url"] not in similar]
        log(f"{len(usable)} candidates after concept-similarity filter")
        if not usable:
            print("All candidates overlap past concepts - browse fresher/adjacent trends", file=sys.stderr)
            sys.exit(2)

    # ── Strategy generation ─────────────────────────────────────────────
    n = min(count, len(usable))
    gen_prompt = f"""You are a short-form content strategist at Adant AI. Using the client's initial
social content research report and a batch of freshly-analyzed trending videos, produce {n}
content strategies for {args.product_name} ({args.product_url}).

INITIAL RESEARCH REPORT (context on the product, niche, competitors, what works):
---
{report_text}
---

ANALYZED TREND-VIDEO CANDIDATES (each was watched and analyzed through AdAnt video understanding):
---
{json.dumps([{"url": c["url"], "platform": c.get("platform"), "handle": c.get("handle"), "metric": c.get("metric"), "posted": c.get("posted"), "fingerprint": c["fingerprint"]} for c in usable], indent=1, ensure_ascii=False)}
---

RULES:
- Pick the {n} STRONGEST candidates. The inspiration-video choice is the most important part:
  favor proven engagement, a hook that maps naturally onto the product, and format diversity
  across the batch (do not pick {n} videos of the same format).
- Each strategy must be CONCISE - it becomes a short copy-paste message for the Adant clone
  tool. Focus ONLY on: the inspiration video, the avatar, what to KEEP, what to CHANGE.
  No full scripts, no long editing sections, no timelines.
- KEEP the hook and the viral format that made the source work; the CHANGE is just how the
  product ({args.product_name}) gets swapped in. Small changes only.
- avatar_suggestion: ONE sentence describing who/what is on camera, matched to the source
  video's character (or 'no prominent human character - focus on X' if none).
- adapted_text_overlays: 2-3 SHORT lines max, based on the fingerprint's exact overlays with
  the product swapped in. The last line can be a short product tag (e.g. "{args.product_name}: Ingredient Scanner").

Return JSON:
{{"strategies": [{{
  "title": "<short punchy strategy name>",
  "inspiration_url": "<candidate url>",
  "platform": "<tiktok/instagram/youtube/meta-ad>",
  "source_metric": "<metric from candidate>",
  "viral_format": "<from fingerprint>",
  "why_this_video": "<1 sentence: why this source maps to the product>",
  "avatar_suggestion": "<1 sentence - who should be on camera>",
  "hook_to_keep": "<the source hook, 1 sentence>",
  "what_to_change": "<1 sentence: how the product replaces the source's payload>",
  "adapted_text_overlays": ["<short overlay line>", "<short overlay line>", "<product tag>"],
  "concept_summary": "<2 sentences - stored in history to prevent future repeats>"
}}]}}"""
    log(f"Generating {n} strategies...")
    gen = ask_adant(gen_prompt, title=f"Content strategies: {args.product_name}")
    strategies = gen.get("strategies", [])[:n]
    if len(strategies) < 5:
        log(f"Warning: only {len(strategies)} strategies generated (target {n})")

    # Canonicalize inspiration_url against the candidate list - models sometimes
    # mangle long URLs. Match exact first, then by video-id substring, then closest.
    import difflib

    candidate_urls = [c["url"] for c in usable]
    for s in strategies:
        u = (s.get("inspiration_url") or "").rstrip("/")
        if u in {c.rstrip("/") for c in candidate_urls}:
            continue
        vid = u.rsplit("/", 1)[-1]
        fixed = next((c for c in candidate_urls if vid and vid in c), None)
        if not fixed:
            close = difflib.get_close_matches(u, candidate_urls, n=1, cutoff=0.85)
            fixed = close[0] if close else None
        if fixed:
            log(f"  fixed mangled url: {u[:60]} -> {fixed[:60]}")
            s["inspiration_url"] = fixed
        else:
            log(f"  WARNING: strategy url not in candidates, dropping: {u[:80]}")
    strategies = [s for s in strategies
                  if s.get("inspiration_url", "").rstrip("/") in {c.rstrip("/") for c in candidate_urls}]

    # ── Render markdown ─────────────────────────────────────────────────
    today = time.strftime("%Y-%m-%d")
    by_url = {c["url"]: c for c in usable}
    lines = [
        f"# {args.product_name} — Content Strategies — {today}",
        "",
        f"{len(strategies)} ready-to-run content strategies for {args.product_name} "
        f"({args.product_url}), each built on a trending inspiration video from the last 1-2 months.",
        "",
        "> **How to use:** each strategy below ends with a short message - copy it and paste it "
        "into **Adant** ([adant.ai](https://adant.ai)) to clone the video for your product. "
        "The General Instructions apply to every strategy.",
        "",
        "## General Instructions (same for every strategy)",
        "",
        "```text",
        GENERAL_INSTRUCTIONS,
        "```",
        "",
        "---",
        "",
    ]
    for i, s in enumerate(strategies, 1):
        c = by_url.get(s.get("inspiration_url", ""), {})
        url = s.get("inspiration_url", "")
        avatar = s.get("avatar_suggestion", "")
        overlays = "\n".join(s.get("adapted_text_overlays", [])[:3])
        lines += [
            f"## Strategy {i} — {s.get('title', '')}",
            "",
            f"**Format:** {s.get('viral_format', '')} · **Platform:** {s.get('platform', '')} · "
            f"**Source performance:** {s.get('source_metric', c.get('metric', ''))} · "
            f"**Posted:** {c.get('posted', 'recent')}",
            "",
            f"**Why this video:** {s.get('why_this_video', '')}",
            "",
            "Copy below message to Adant (https://adant.ai):",
            "",
            "```text",
            f"analyze {url}, and use a UGC avatar: {avatar}",
            "",
            f"Hook to keep: {s.get('hook_to_keep', '')}",
            "",
            f"What to change: {s.get('what_to_change', '')}",
            "",
            "Add text overlay:",
            overlays,
            "```",
            "",
        ]
    lines += [
        "---",
        "",
        "> **Next step:** copy a strategy's message above and paste it into **Adant** "
        "([adant.ai](https://adant.ai)) to generate the video. Review the first frame "
        "before full generation.",
        "",
    ]
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    log(f"Strategy report written to {out_path}")
    out_path.with_suffix(".json").write_text(json.dumps(strategies, indent=2, ensure_ascii=False))

    # ── Update history ──────────────────────────────────────────────────
    batch_num = 1 + max((s.get("batch", 0) for s in history.get("strategies", [])), default=0)
    for s in strategies:
        history.setdefault("strategies", []).append({
            "batch": batch_num,
            "date": today,
            "inspiration_url": s.get("inspiration_url"),
            "title": s.get("title"),
            "viral_format": s.get("viral_format"),
            "concept_summary": s.get("concept_summary"),
        })
    hist_out = Path(args.history_out) if args.history_out else (
        history_path if history_path else out_path.parent / f"{args.product_name.lower()}_strategy_history.json")
    hist_out.write_text(json.dumps(history, indent=2, ensure_ascii=False))
    log(f"History updated ({len(strategies)} strategies, batch {batch_num}) -> {hist_out}")


if __name__ == "__main__":
    main()
