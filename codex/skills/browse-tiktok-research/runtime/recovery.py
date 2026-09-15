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


def parse_markdown_video_list(text: str) -> list[dict]:
    """Parse markdown-formatted video list from extract tool output."""
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
        # Match View/Like Count (search results show likes, not views).
        # The capture takes the abbreviation with the digits — "Like Count:
        # 1.2M" read as 1 under a bare \d+ and still looked like a finding.
        view_match = re.search(r'(?:View|Like) [Cc]ount[:\s]*`?([\d,.]+\s*[KMB]?)`?', line, re.IGNORECASE)
        if view_match and current:
            count = parse_count(view_match.group(1))
            if count is not None:
                current["like_count"] = count
            continue

    if current.get("url"):
        videos.append(current)

    return videos
