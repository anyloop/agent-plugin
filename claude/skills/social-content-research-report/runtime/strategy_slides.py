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
import textwrap

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
    """Build the copy-paste message body for one strategy (plain text).

    One idea per line, each short enough never to wrap. The url sits alone so a
    long TikTok permalink can never push the avatar onto a second line.

    `avatar` names a TYPE and a look — the reference video decides which, so an
    animated reference never yields a "UGC avatar". `keep` names WHAT is being
    reused (hook, viral format, visual style, structure, pacing) rather than
    always the hook. Legacy keys still render so older report_data keeps working.
    """
    overlays = [line for line in strategy.get("overlays", []) if line][:3]
    avatar = strategy.get("avatar", "")
    keep = strategy.get("keep") or strategy.get("hook_to_keep", "")
    change = strategy.get("change") or strategy.get("what_to_change", "")
    lines = [
        f"analyze {strategy.get('url', '')}",
        "",
        f"Avatar: {avatar}",
        "",
        f"Keep: {keep}",
        "",
        f"Change: {change}",
    ]
    if strategy.get("style"):
        lines += ["", f"Style: {strategy['style']}"]
    lines += ["", "Overlay:", *overlays]
    return "\n".join(lines)


# Characters that fit one line of the message block: ~838px of usable width at
# 10.5px JetBrains Mono (0.6em advance = 6.3px), with margin. Wrapping happens
# HERE, at spaces, never in the browser — see message_lines. A message whose
# lines all fit pastes as the exact text the author wrote, with no wrap points
# at all; build_deck warns when one does not.
MSG_WRAP_COLS = 130


def overlong_message_lines(strategy: dict) -> list[str]:
    """Logical lines that will have to wrap — the caller warns so they get cut.

    A wrapped line still copies correctly, but it lands in the paste with a line
    break the author did not write. Keeping every line inside MSG_WRAP_COLS is
    what makes the pasted message byte-identical to the intended one.
    """
    return [
        line
        for line in strategy_message(strategy).split("\n")
        if len(line) > MSG_WRAP_COLS
    ]


def message_lines(strategy: dict) -> list[str]:
    """Physical lines of the copy-paste message, ready to render one-per-element.

    Soft-wrapping this text in CSS makes the PDF uncopyable. Chrome's printToPDF
    turns a `white-space: pre-wrap` block into fragmented text runs that extract
    OUT OF ORDER, and `overflow-wrap: anywhere` splits words mid-character — a
    real copy came back as "analyze https://www.youtub / music / b / ed / long
    takes / e.com/shorts/..." with the avatar text interleaved into the URL.

    Wrapping in Python instead means every visual line is a known string that
    becomes its own element, so the PDF holds one text run per line in document
    order and a copy round-trips. Words are never broken: `break_long_words` is
    off, so a long URL overflows its line rather than being cut in half.
    """
    out: list[str] = []
    for logical in strategy_message(strategy).split("\n"):
        if not logical:
            out.append("")
            continue
        out.extend(
            textwrap.wrap(
                logical,
                width=MSG_WRAP_COLS,
                break_long_words=False,
                break_on_hyphens=False,
            )
            or [""]
        )
    return out


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
    # One element per visual line: keeps PDF text runs in document order and
    # lets a copy round-trip. Blank lines need a non-breaking space to hold height.
    # Blank separators carry NO text: a &nbsp; spacer copies out of the PDF as an
    # invisible U+00A0, which then pastes into a prompt box as hidden garbage.
    # An empty div sized by CSS keeps the rhythm without entering the text layer.
    message = "".join(
        f'<div class="msg-line">{html.escape(line)}</div>' if line
        else '<div class="msg-gap"></div>'
        for line in message_lines(strategy)
    )
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
