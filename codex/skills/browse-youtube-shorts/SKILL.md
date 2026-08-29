---
name: browse-youtube-shorts
description: Browse YouTube Shorts by keywords for visible trend and creator evidence. Prefer the in-app Browser; use adant-local research tools as fallback.
---

# Browse YouTube Shorts

Use the `control-in-app-browser` skill and its browser-client selection flow when
available; the runtime prefers the persistent in-app Browser. Never inspect
browser secrets.

Reuse one workflow-owned tab and close it immediately after capture; never close
a user-created tab. If Browser is unavailable or blocked, use the Chrome/CDP
fallback by calling `research_run`
phase `platform-youtube` with queries, sort/time/view filters, limits, and an
output artifact.

Return visible URL, channel, title/description, hashtags, views/likes/comments,
publish date, thumbnail, query, and backend. Keep Shorts distinct from long-form
videos, label missing metrics, and separate observations from inferred patterns.
