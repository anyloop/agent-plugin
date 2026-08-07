#!/usr/bin/env python3
"""Render the deck's Sample Content Strategy section.

The section turns the top inspiration videos already curated for the research
slides into copy-paste messages for Adant, using the exact block shape that
`content-strategy-generator/runtime/generate_strategies.py` emits so a reader
who later runs the full `social-content-strategist` batch sees the same format:

    analyze <url>, and use a UGC avatar: <avatar>

    Hook to keep: <hook>

    What to change: <what changes for this product>

    Add text overlay:
    <overlay lines>

The General Instructions block is shown once on the section opener, never per
strategy, matching the strategy report.
"""

from __future__ import annotations

import html

# Verbatim from content-strategy-generator/runtime/generate_strategies.py so the
# deck and the strategy report hand the reader the same instructions.
GENERAL_INSTRUCTIONS = """Analyze [INSPIRATION VIDEO URL]
with character as [YOUR AVATAR IMAGE], no text overlay. Only regenerate the first frame for review. You can ask to change character cloth, background setting and anything.
Review the first frame. If it looks good, proceed to rewrite the script to promote the product instead.
When the script is good, proceed with video generation.
Video generation: now clone the video with below model choice:
use Seedance 2.0
Just mention in the instruction using natural language"""


def strategy_message(strategy: dict) -> str:
    """Build the copy-paste message body for one strategy (plain text)."""
    overlays = [line for line in strategy.get("overlays", []) if line][:3]
    return "\n".join([
        f"analyze {strategy.get('url', '')}, and use a UGC avatar: {strategy.get('avatar', '')}",
        "",
        f"Hook to keep: {strategy.get('hook_to_keep', '')}",
        "",
        f"What to change: {strategy.get('what_to_change', '')}",
        "",
        "Add text overlay:",
        *overlays,
    ])


def _opener_slide(section: dict, page: int) -> str:
    headline = section.get("headline", "Five videos to clone. <em>Start here.</em>")
    intro = section.get(
        "intro",
        "Each card below pairs one proven video from this research with a message you can "
        "paste straight into Adant. The general instructions apply to all five.",
    )
    return f"""
<!-- ═══════════════════ SLIDE {page:02d} — SAMPLE CONTENT STRATEGY (OPENER) ═══════════════════ -->
<div class="slide slide--dark strat-open">
  <div class="aurora"><span class="a-core"></span><span class="a-peach"></span><span class="a-blue"></span></div>
  <div class="brand-mark"><div class="dot"></div>ADANT AI</div>
  <div class="strat-open-grid">
    <div>
      <div class="section-label">Sample content strategy</div>
      <div class="section-title">{headline}</div>
      <p class="strat-open-copy">{intro}</p>
    </div>
    <div class="gen-card">
      <div class="gen-label">General instructions · same for every strategy</div>
      <div class="gen-pre">{html.escape(GENERAL_INSTRUCTIONS)}</div>
    </div>
  </div>
  <div class="page-num">{page}</div>
</div>
"""


def _strategy_slide(strategy: dict, index: int, total: int, page: int, pill: str) -> str:
    message = html.escape(strategy_message(strategy))
    meta_bits = [
        strategy.get("format", ""),
        strategy.get("platform_label", pill),
        strategy.get("metric", ""),
        strategy.get("posted", ""),
    ]
    meta = " · ".join(html.escape(bit) for bit in meta_bits if bit)
    thumb = strategy.get("thumb", "")
    url = strategy.get("url", "")
    handle = html.escape(strategy.get("handle", ""))
    return f"""
<!-- ═══════════════════ SLIDE {page:02d} — STRATEGY {index} ═══════════════════ -->
<div class="slide strat-slide">
  <div class="brand-mark"><div class="dot"></div>ADANT AI</div>
  <div class="section-label">Sample content strategy · {index} of {total}</div>
  <div class="section-title">{strategy.get('title', '')}</div>
  <div class="strat-grid">
    <a class="vid-card" href="{url}" target="_blank">
      <div class="vid-thumb"><div class="pf">{pill}</div><img src="{thumb}" alt="{handle}"></div>
      <div class="vid-meta"><div class="h">{handle}</div><div class="v">{html.escape(strategy.get('metric', ''))}</div></div>
    </a>
    <div>
      <div class="strat-meta-row">{meta}</div>
      <div class="strat-why">{strategy.get('why_this_video', '')}</div>
      <div class="msg-label">Copy this message into adant.ai</div>
      <div class="msg-block">{message}</div>
    </div>
  </div>
  <div class="page-num">{page}</div>
</div>
"""


def _closing_slide(section: dict, connect: dict, page: int) -> str:
    url = connect.get("connectUrl", "https://adant.ai")
    link_text = connect.get("connectLinkText", "adant.ai")
    headline = section.get("closingHeadline", "Paste a message. <em>Get a video.</em>")
    copy = section.get(
        "closingCopy",
        "Open Adant, paste any of the five messages, review the first frame, then generate.",
    )
    return f"""
<!-- ═══════════════════ SLIDE {page:02d} — START CREATING ═══════════════════ -->
<div class="slide slide--dark strat-close">
  <div class="aurora"><span class="a-core"></span><span class="a-peach"></span><span class="a-blue"></span></div>
  <div class="brand-mark"><div class="dot"></div>ADANT AI</div>
  <div class="strat-close-inner">
    <div class="section-label">Start creating</div>
    <div class="section-title">{headline}</div>
    <p class="strat-close-copy">{copy}</p>
    <a class="cn-link" href="{url}" target="_blank">{link_text}</a>
    <div class="cn-contact">{connect.get('connectContact', '')}</div>
  </div>
  <div class="page-num">{page}</div>
</div>
"""


def build_strategy_section(data: dict, start_page: int, platform_pill: dict) -> tuple[str, int]:
    """Render opener + one slide per strategy + closing. Returns (html, page_count).

    Returns ("", 0) when the report carries no strategies, so decks generated
    from older report_data.json files keep their original page count.
    """
    section = data.get("strategies", {})
    items = section.get("items", [])
    if not items:
        return "", 0

    connect = data.get("connect", {})
    page = start_page
    blocks = [_opener_slide(section, page)]
    for index, strategy in enumerate(items, 1):
        page += 1
        pill = platform_pill.get(strategy.get("platform", ""), strategy.get("platform", "").upper())
        blocks.append(_strategy_slide(strategy, index, len(items), page, pill))
    page += 1
    blocks.append(_closing_slide(section, connect, page))
    return "\n".join(blocks), page - start_page + 1


def strategy_markdown(data: dict) -> list[str]:
    """Render the same section as markdown lines for the .md deck."""
    section = data.get("strategies", {})
    items = section.get("items", [])
    if not items:
        return []

    connect = data.get("connect", {})
    url = connect.get("connectUrl", "https://adant.ai")
    lines = [
        "## Sample Content Strategy",
        "",
        f"Copy any message below and paste it into Adant ({url}) to clone that video "
        "for this product. The general instructions apply to every strategy.",
        "",
        "### General Instructions (same for every strategy)",
        "",
        "```text",
        GENERAL_INSTRUCTIONS,
        "```",
        "",
    ]
    for index, strategy in enumerate(items, 1):
        meta = " · ".join(
            bit for bit in [
                strategy.get("format", ""),
                strategy.get("platform_label", strategy.get("platform", "").upper()),
                strategy.get("metric", ""),
                strategy.get("posted", ""),
            ] if bit
        )
        lines += [
            f"### Strategy {index} — {strategy.get('title', '')}",
            "",
            f"**{meta}** · {strategy.get('handle', '')} · [inspiration video]({strategy.get('url', '')})",
            "",
            f"**Why this video:** {strategy.get('why_this_video', '')}",
            "",
            f"Copy below message to Adant ({url}):",
            "",
            "```text",
            strategy_message(strategy),
            "```",
            "",
        ]
    lines += [f"Paste any message above into Adant ({url}) and review the first frame before generating.", ""]
    return lines
