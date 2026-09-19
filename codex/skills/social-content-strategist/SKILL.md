---
name: social-content-strategist
description: Turn example videos, creators, a saved research report, or a product brief into 5-10 evidence-backed social content strategies built on fresh, relevant videos the user has not seen, delivered as a strategy brief — a PDF plus a saved AdAnt report with one-click Create in Studio — using AdAnt MCP tools.
---

# Social Content Strategist

Open the progress panel, then follow the mandatory [authentication preflight](../adant/references/authentication.md) before reading seeds.
Return early if required authentication fails; local work is not a workaround.

## Scope

The user's words set the scope. Platforms named in the request are the only
platforms searched and the only platform sections in the brief; with none
named, search TikTok, Instagram, YouTube and Meta Ads. Example videos, a
creator, a prior report, or keywords in the request are seeds: they shape the
queries and are excluded from the candidates, because a strategy built on a
video the user already has is not a new idea. Honor a requested strategy count;
default to five primary and three reserves. When the request weights a platform
or gives per-platform counts, plan queries in that proportion, collect the
weighted platform first in a call of its own so its searches never share a
request budget with the others, and fill each platform's count from its own
candidates; when one cannot reach its count, say so in the gaps rather than
filling it silently from another platform. A partial gap that names the request
budget means collect that platform again alone with fewer queries; a degraded
note saying a platform ran on the backup supplier means fewer outliers there,
not an outage.

## Read the seeds

Read every seed before searching; a guessed caption finds the wrong videos. A
prior report given as a Studio URL (`/home/reports/<id>`) or id: call
`adant_get_product_report`, write the result to `prior_report.json`, and treat
its `product`, `findings`, strategy titles, `whyThisVideo` notes and cited
videos' `format` labels as seed vocabulary; its `videoUrls` are videos this run
must not recommend again. Then run `strategy-keywords` with every example link
as `--video` (and `prior_report.json` as `--report`), the product name and
niche: it fetches each seed's caption, mines the hashtags the winning videos
use (feed tags dropped), and writes per-platform queries — the subject in the
caption's words, specific hashtags as plain words, the audience problem, and
the format applied to the category. A creator handle is not a query: seed with
two or three of their recent videos instead. Write `history.json` with
`excluded_urls` = every seed URL plus `videoUrls`.

## Discover and analyze

Run `adant_research_collect` with the mined queries on the in-scope platforms:
it searches from AdAnt's servers and needs no browser or social account. Give each call a stable `idempotency_key` per keyword set and platform group (`strategy-tiktok-1`, `strategy-youtube-1`), so a repeated call replays the saved result instead of spending again; a failed call's key cannot be reused, so retry with a new one. Fresh
content is the point: collect TikTok and Instagram in one call with
`postedWithinDays: 60` (or the user's window, at least 30), and YouTube and
Meta Ads in a second call without it — Shorts carry no publish date and an ad's
start date is not a post date, so asking would turn both into gaps; label their
freshness "unverified" in the brief. Only platforms it reports as gaps (or
every in-scope one when only the collector is absent after remote authentication) go to the browser, one platform at
a time through the matching `platform-*` phase. Use the
`control-in-app-browser` skill and its browser-client selection flow when
available; the runtime prefers the persistent in-app Browser, with Chrome/CDP
fallback only through platform phases. Keep one workflow-owned tab and close
it. Use public pages or an existing session; do not ask for TikTok/Instagram
login. An optional `platform_session(platform, "check")` diagnoses only that
browser session. Record blocked browsing as an evidence gap; zero results do
not establish a login requirement. Never use fallback to bypass a failed or
unverified AdAnt connection.

Judge relevance before engagement: a candidate must share the seeds' subject or
category, or their audience problem with the category clearly present; a
broadly related viral post is ineligible however high its numbers, and at most
two candidates per creator go forward. Drop any candidate whose platform id
matches a seed or a prior-report video. Prefer posts inside the window; older
ones are at most reserves labelled evergreen with their date, and no date means
unknown, not recent. Analyze candidates with phase `strategy` in batches of at
most two, then run `content-strategies` with `history.json` so the final
concepts exclude seed and prior URLs and near-duplicates. Each strategy carries
evidence URL, hook, audience, product angle, script, shots, overlays/audio,
CTA, rationale, risks, `avatar` and the three-line brief; keep the mechanism,
adapt product facts and brand voice.

## Deliver the strategy brief

Write `report_data.json` with `"layout": "strategy_brief"`: `cover`
(`clientName` as the brand name or product URL, `reportSubtitle`,
`clientContact`, `reportDate`), a `platforms` entry per in-scope platform
holding the collected videos as `brand_videos` and `creator_videos` (an empty
slot is dropped), `meta_ads` only when Meta was searched, and `strategies` with
the primaries in `items` and the reserves. The strategy intro names the seeds
and prior report (its URL in `sources`); `gaps` says how many already-seen
videos were excluded, the freshness window, and which platforms' dates are
unverified. Omit `exec`, `landscape`, `competitive`, `formats` and `connect`;
the research-report contract covers the rest. Run `research_run` phase `report`
variant `build` with strict validation, then variant `pdf`: the builder keeps
the cover, the platform slides that hold videos, Meta Ads when present, and the
strategies, renumbered. Save exactly as the research-report skill does:
`report_local` manifest → `adant_prepare_uploads` → `report_local` upload →
`adant_complete_uploads` → `report_local` payload →
`adant_save_product_report`. The brief lands in Studio's Social Strategy
library as its own report, every strategy with a one-click Create in Studio.
Never report success without the returned report id and URL; if a save stage
fails, deliver the local PDF/HTML/markdown, name the failed stage, and say
AdAnt Studio was not updated; then present the ranked primaries and reserves
with the report URL and ask which to build.
