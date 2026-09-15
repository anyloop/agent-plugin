---
name: social-content-strategist
description: Turn an initial research report or product brief plus example videos into 5-10 product-specific social content strategies using AdAnt MCP tools.
---

# Social Content Strategist

Open the progress panel and call `doctor`. If needed, mint `research` and
bootstrap it without exposing the token.

Run `strategy-keywords`, then `adant_research_collect` with those keywords
across TikTok, Instagram, YouTube and Meta Ads: it searches from AdAnt's servers
and needs no browser or social account. Only platforms it reports as gaps (or
all of them when the tool is absent) go to the browser, one platform at a time
through the matching `platform-*` phase. Use the `control-in-app-browser` skill
and its browser-client selection flow when available; the runtime prefers the
persistent in-app Browser, with Chrome/CDP fallback only through platform
phases. Keep one workflow-owned tab and close it. Only then, and only for
TikTok/Instagram, call `platform_session(platform, "check")`; if false, ask
before one `platform_session(platform, "open")` per platform per workflow,
re-check, and continue if the user declines. `logged_in: null` is unknown; if
every query on that platform returns zero, report likely session blocking once.
Analyze candidates with phase `strategy` in batches of at most two. Use
`content-strategies` to produce 5-10 final concepts while excluding prior URLs
and near-duplicates.

Each strategy needs evidence URL, hook, audience/pain, product angle, script,
shot sequence, overlays/audio, CTA, rationale, risk/claim notes, and a copy-ready
AdAnt prompt. Preserve the source mechanism but adapt product facts and brand
voice. Present a ranked primary set plus reserves and ask which concept to build.
