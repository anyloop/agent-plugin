---
name: browse-youtube-shorts
description: Browse YouTube Shorts by keywords for visible trend and creator evidence. Prefer the in-app Browser; use adant-local research tools as fallback.
---

# Browse YouTube Shorts

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
