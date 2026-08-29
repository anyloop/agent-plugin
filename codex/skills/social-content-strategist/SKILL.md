---
name: social-content-strategist
description: Turn an initial research report or product brief plus example videos into 5-10 product-specific social content strategies using AdAnt MCP tools.
---

# Social Content Strategist

Open the progress panel and call `doctor`. If needed, mint `research` and
bootstrap it without exposing the token.

For TikTok/Instagram call `platform_session(platform, "check")`. If false, ask
before one `platform_session(platform, "open")`; open at most once per platform
per workflow, then re-run `platform_session(platform, "check")`. Continue when
the user declines or asks to skip. `logged_in: null` is unknown; if every TikTok
or Instagram query returns zero, report likely session blocking once.

Use the `control-in-app-browser` skill and its browser-client selection flow when
available; the runtime prefers the persistent in-app Browser. Chrome/CDP fallback
must run only through platform phases. Keep one workflow-owned tab and close it.

Run `strategy-keywords`, browse one platform at a time, then analyze candidates
with phase `strategy` in batches of at most two. Use `content-strategies` to
produce 5-10 final concepts while excluding prior URLs and near-duplicates.

Each strategy needs evidence URL, hook, audience/pain, product angle, script,
shot sequence, overlays/audio, CTA, rationale, risk/claim notes, and a copy-ready
AdAnt prompt. Preserve the source mechanism but adapt product facts and brand
voice. Present a ranked primary set plus reserves and ask which concept to build.
