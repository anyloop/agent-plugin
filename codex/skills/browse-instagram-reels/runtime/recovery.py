#!/usr/bin/env python3
"""Reading structured rows back out of the agent's own transcript.

The fallback for when the page-side extraction returns nothing: the agent
narrated what it saw in markdown, and these parsers recover the rows from that
narration. Kept out of `browse.py` deliberately — that module pulls in the
whole browser runtime (dotenv, playwright, websockets), and this parsing is
pure text work that has to stay testable on a bare interpreter, which is
exactly what the plugin runtime check runs.
"""

import re

from counts import parse_count


def parse_markdown_reel_list(text: str) -> list[dict]:
    """Parse markdown-formatted Reel list from extract tool output."""
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
        # Match View Count — the abbreviation belongs to the number, so it is
        # captured with it: "View Count: 1.2M" is 1_200_000, not 1.
        view_match = re.search(r'(?:View|Play)\s*[Cc]ount[:\s]*`?([\d,.]+\s*[KMB]?)`?', line, re.IGNORECASE)
        if view_match and current:
            count = parse_count(view_match.group(1))
            if count is not None:
                current["view_count"] = count
            continue

    if current.get("url"):
        reels.append(current)

    return reels
