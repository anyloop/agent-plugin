---
name: browse-tiktok-research
description: Search TikTok by keywords and filters for visible trend and partnership evidence. Prefer the authenticated in-app Browser; use adant-local research tools as fallback.
---

# Browse TikTok

Use the `control-in-app-browser` skill and its browser-client selection flow when
available; the runtime prefers the persistent in-app Browser. Reuse an existing
TikTok session and never inspect cookies, storage, passwords, or profiles.

Use at most one workflow-owned research tab, close it immediately when complete,
and never close a user-created tab. If Browser is unavailable or blocked, use
the Chrome/CDP fallback through
`platform_session("tiktok", "check")`, ask before one `open`, then re-run
`check`. Execute fallback browsing only through `research_run` phase
`platform-tiktok` with queries, sort/time/like filters, limits, and an output
artifact.

Return URL, author, caption, hashtags, likes/views/comments when visible,
thumbnail, query, and backend. Preserve zero/missing values honestly. For
partnership research, include relationship and profile evidence plus promotion
strength; a brand hashtag alone is discovery evidence, not confirmation.
