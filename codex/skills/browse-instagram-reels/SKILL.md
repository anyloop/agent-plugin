---
name: browse-instagram-reels
description: Browse Instagram Reels by keywords to find visible trend and partnership evidence. Prefer the authenticated in-app Browser; use adant-local research tools as the portable fallback.
---

# Browse Instagram Reels

Use the `control-in-app-browser` skill and its browser-client selection flow when
available; the runtime prefers the persistent in-app Browser. Reuse the existing
Instagram session and never inspect cookies, storage, passwords, or profiles.

Freeze visible Reel URLs before opening results. Keep one search tab and inspect
each Reel in a separate temporary tab. Close every workflow-owned tab immediately
after use; never close a user-created tab.

If Browser is unavailable or blocked, use the Chrome/CDP fallback through
`platform_session("instagram",
"check")`, ask before one `open`, then re-run `check`. Execute the fallback only
through `research_run` phase `platform-instagram` with queries, limits, and an
output artifact. Do not retry login more than once.

Return visible evidence only: URL, account, caption, hashtags, engagement,
thumbnail, query, and `browser_backend`. Mark unavailable fields null and never
fabricate metrics. For partnership research, record brand attribution,
relationship evidence, creator-profile evidence, and promotion strength.
