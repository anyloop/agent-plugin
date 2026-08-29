---
name: browse-meta-ads-library
description: Browse Meta Ad Library by keywords and advertisers for active Facebook and Instagram ad evidence. Prefer the in-app Browser; use adant-local research tools as fallback.
---

# Browse Meta Ads Library

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
