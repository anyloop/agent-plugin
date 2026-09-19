---
name: browse-tiktok-research
description: Search TikTok by keywords and filters for visible trend and partnership evidence. Prefer the authenticated in-app Browser; use adant-local research tools as fallback.
---

# Browse TikTok

> **Deprecated (2026-09-16).** Platform search already runs on AdAnt's
> servers through supplier APIs (`adant_research_collect`: no browser, no
> social login), and video analysis and the rest of the research path move
> there next. This skill stays as the gap-fill step of
> `initial-social-content-research` and as the fallback where the server tool
> is not available; it goes away once the server path is the only one. Do not
> build new flows on it.

Before work, follow the [authentication preflight](../adant/references/authentication.md);
return early with its recovery instructions if a required check fails.

Use the `control-in-app-browser` skill and its browser-client selection flow when
available; the runtime prefers the persistent in-app Browser. Reuse an existing
TikTok session and never inspect cookies, storage, passwords, or profiles.

Use at most one workflow-owned research tab, close it immediately when complete,
and never close a user-created tab. If Browser is unavailable or blocked, use
the Chrome/CDP fallback through
`research_run` phase `platform-tiktok` with queries, limits, and an output
artifact. Use public pages or an existing session; do not request social login.
If blocked, report the observed browsing gap and continue on accessible platforms.
Zero results alone do not prove session blocking.

Return URL, author, caption, hashtags, likes/views/comments when visible,
thumbnail, query, and backend. Preserve zero/missing values honestly. For
partnership research, include relationship and profile evidence plus promotion
strength; a brand hashtag alone is discovery evidence, not confirmation.
