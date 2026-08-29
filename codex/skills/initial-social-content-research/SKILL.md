---
name: initial-social-content-research
description: >-
  Run end-to-end initial social research for a product: profile, competitors,
  platform trends, creator partnerships, curation, 13-slide report, and
  optional AdAnt save. Uses only MCP tools.
---

# Initial Social Content Research

Use `production-complete` unless the user explicitly asks for `fast-draft`.
Open `research_progress_open` first. If `doctor` lacks auth, call
`device_identity`, pass its fields to `adant_mint_local_token` with scope
`research` (and `report` when saving), then call `auth_bootstrap` without showing
the token. If the inline panel does not
render, give the user its `fallbackUrl` or call `research_progress_fallback`.

## Setup and login

For TikTok/Instagram call `platform_session(platform, "check")`. If false,
ask before `platform_session(platform, "open")`; open at most once per platform
per workflow, then re-run `platform_session(platform, "check")`. Continue when
the user declines or asks to skip. Treat `logged_in: null` as unknown. If every
TikTok or Instagram query returns zero, report likely session blocking once.

## Phase plan

Parallelism is the expected shape for independent inference, but browser work
uses at most one workflow-owned research tab. Run it one platform at a time and
close it immediately; never wait for the agent turn to end.
Use the `control-in-app-browser` skill and its browser-client selection flow;
the runtime prefers the persistent in-app Browser, with Chrome/CDP fallback.

1. Launch `research_run(...)` with the selected mode, `product-profile`,
   `competitors`, and both `keywords` variants. Preserve their artifacts.
2. Call `research_workflow(action="stage_start", stage="discovery")`, then
   browse TikTok, Instagram, Meta Ads, and YouTube using Browser or the matching
   `platform-*` phase. Use brand, competitor, pain, and product-use queries.
3. For TikTok/Instagram/YouTube add a branded partnership set. Search brand-name
   text, brand hashtags (for example `#WisprFlow`), `{brand} review`, `{brand}
   demo`, and at least two product-use queries. A tag enters discovery but does
   not confirm a relationship; verify video and creator-profile evidence.
4. Store partnership artifacts as `keywords_<platform>_partnerships.json` and
   `browse_<platform>_partnerships.json`. Record `relationship_evidence`,
   `creator_profile_evidence`, and relationship class (`confirmed_paid`,
   `commercial_affiliate`, `potential_collaboration`, `brand_attributed`).
5. Run `curation` variant `plan`, fill evidence gaps, then variant `validate`.
   Curate diverse brand/competitor, creator, partnership, and paid-ad examples.
6. Analyze selected videos with `strategy` in batches of at most two. Record
   `promotion_strength` (`none`, `incidental`, `integrated`, `direct`).
7. Select five primary strategies and three reserves. Run `report` variant
   `build` in strict mode for the 13-slide HTML and markdown research preview,
   then `report` variant `pdf`.

Use `research_status(wait: true, timeout_s: 45)` for bounded waits. If work takes
more than 60 seconds, update the user with “Found so far” and current counts.
Before another discovery or strategy batch, call
`research_workflow(action="stage_check", stage=<stage>)`; if exhausted, curate
current evidence instead of retrying.

## Delivery gate

`production-complete` requires validated curation, five primary + three reserves,
the report artifacts, and no silent platform failure. `fast-draft` must label all
missing evidence.

To save, call `report_local` manifest → remote `adant_prepare_uploads` →
`report_local` upload → remote `adant_complete_uploads` → `report_local` payload
→ `adant_save_product_report`. Never report save success without the returned
report id/URL. Otherwise deliver local report artifacts and state that AdAnt was
not updated. Finally call `research_workflow(action="complete")`.
