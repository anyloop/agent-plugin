---
name: browse-meta-ads-library
description: Browse Meta Ad Library by keywords and advertisers for active Facebook and Instagram ad evidence. Prefer the in-app Browser; use adant-local research tools as fallback.
---

# Browse Meta Ads Library

> **Deprecated (2026-09-20).** Use the server content-research workflow for normal research. This browser skill is retained only for explicitly requested browser investigation; it is not automatic gap-fill for server jobs.

Before work, follow the [authentication preflight](../adant/references/authentication.md);
return early with its recovery instructions if a required check fails.

Use the `control-in-app-browser` skill and its browser-client selection flow when
available; the runtime prefers the persistent in-app Browser. The library is
public and normally needs no login. Never inspect browser secrets.

Reuse one workflow-owned tab for every query and close it immediately when done;
never close user-created tabs. If Browser is unavailable or blocked, use the
Chrome/CDP fallback by calling
`research_run` phase `platform-meta-ads` with keyword queries and/or advertisers,
country/platform/media filters, limits, and an output artifact.

Capture only visible evidence: advertiser, copy, CTA, platforms, media type,
start date/longevity, landing page, creative preview, query, and backend. Prefer
currently active ads; label missing fields rather than guessing. Summarize
repeated hooks, offers, formats, and landing-page patterns separately from facts.
