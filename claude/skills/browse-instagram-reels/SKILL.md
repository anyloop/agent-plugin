---
name: browse-instagram-reels
description: Browse Instagram Reels by keywords to find visible trend and partnership evidence. Prefer the authenticated in-app Browser; use adant-local research tools as the portable fallback.
---

# Browse Instagram Reels

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
available; the runtime prefers the persistent in-app Browser. Reuse the existing
Instagram session and never inspect cookies, storage, passwords, or profiles.

Freeze visible Reel URLs before opening results. Keep one search tab and inspect
each Reel in a separate temporary tab. Close every workflow-owned tab immediately
after use; never close a user-created tab.

If Browser is unavailable or blocked, use the Chrome/CDP fallback through
`research_run` phase `platform-instagram` with queries, limits, and an output
artifact. Use public pages or an existing session; do not request social login.
If blocked, report the observed browsing gap and continue on accessible platforms.
Zero results alone do not prove session blocking.

Return visible evidence only: URL, account, caption, hashtags, engagement,
thumbnail, query, and `browser_backend`. Mark unavailable fields null and never
fabricate metrics. For partnership research, record brand attribution,
relationship evidence, creator-profile evidence, and promotion strength.
