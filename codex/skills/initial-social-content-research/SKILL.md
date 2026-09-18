---
name: initial-social-content-research
description: >-
  Run end-to-end initial social research for a product: profile, competitors,
  platform trends, creator partnerships, curation, 13-slide report, and
  optional AdAnt save. Uses only MCP tools.
---

# Initial Social Content Research

Use `production-complete` unless the user explicitly asks for `fast-draft`.
Open `research_progress_open` first. If `doctor` lacks auth, pass the fields
of its `device` to `adant_mint_local_token` with scope `research` (and `report`
when saving), then call `auth_bootstrap` without showing the token. If the
inline panel does not render, give the user its `fallbackUrl` or call
`research_progress_fallback`.

## Phase plan

Parallelism is the expected shape for independent inference, but browser work
uses at most one workflow-owned research tab. Run it one platform at a time and
close it immediately; never wait for the agent turn to end.
Use the `control-in-app-browser` skill and its browser-client selection flow;
the runtime prefers the persistent in-app Browser, with Chrome/CDP fallback.

1. Launch `research_run(...)` with the selected mode, `product-profile`,
   `competitors`, and both `keywords` variants. Preserve their artifacts.
2. Call `research_workflow(action="stage_start", stage="collect")`, then run
   `adant_research_collect` across TikTok, Instagram, Meta Ads, and YouTube
   with brand, competitor, pain, and product-use queries. It searches all
   four platforms from AdAnt's own servers: no browser, no social account
   of the user's, seconds rather than minutes. It returns posts already
   judged against the outlier thresholds and names any platform it could not
   reach instead of silently returning fewer. Pass a stable `idempotency_key` per
   search set (`collect-1`): a repeat replays; a failed key needs a new one. Close with `stage_complete`.
   Read the gaps before deciding what is left; a run that reaches every
   platform needs no browser at all.
3. Only if step 2 left something unreached or curation identifies a quality gap, call
   `research_workflow(action="stage_start", stage="discovery")` and fill those
   gaps with Browser or the matching `platform-*` phase: platforms named as a
   gap, anything needing the user's logged-in view, and every platform if the
   tool is not present at all — the plugin and the server ship separately, so
   a plugin can reach a deployment that predates the tool. Its absence is a
   reason to use the browser, never a reason to stop. Browser work stays one
   platform at a time; skip this stage when there is nothing to fill. Social
   sign-in belongs here and nowhere earlier: a user whose run never needs the
   browser is never asked to log in. Before a TikTok or Instagram browser
   phase call `platform_session(platform, "check")`; if false, ask before one
   `platform_session(platform, "open")` per platform per workflow, re-check,
   and continue if the user declines. `logged_in: null` is unknown; if every
   query on that platform returns zero, report likely session blocking once.
4. For TikTok/Instagram/YouTube add a branded partnership set. Search
   brand-name text, brand hashtags (for example `#WisprFlow`),
   `{brand} review`, `{brand} demo`, and at least two product-use queries.
   **Take the disclosed ones from the collection first.** TikTok and Instagram
   label these themselves and `adant_research_collect` returns the label:
   `partnership.disclosed` is `confirmed_paid`, and `partnership.sponsors`
   names the brand where the platform names it. `partnership.affiliate` is a
   different relationship — `commercial_affiliate`, the creator earning a
   commission — and must never be recorded as paid. Both are the platform's
   own statement rather than an inference off a caption, so do not open a
   browser to re-prove either. The browser is for the undisclosed tail and
   platforms publishing no label (`partnership` is null): a creator who never
   used the tool discloses nothing, so a missing label is not evidence of no
   relationship. A tag enters discovery but does not confirm a relationship.
5. Store partnership artifacts as `keywords_<platform>_partnerships.json` and
   `browse_<platform>_partnerships.json`. Record `relationship_evidence`,
   `creator_profile_evidence`, and relationship class (`confirmed_paid`,
   `commercial_affiliate`, `potential_collaboration`, `brand_attributed`).
6. Apply [selection policy](references/selection-policy.md) before curation and strategies.
   Run `curation` variant `plan`, fill evidence gaps, then variant `validate`.
   Curate diverse brand/competitor, creator, partnership, and paid-ad examples.
7. Analyze selected videos with `strategy` in batches of at most two. Record
   `promotion_strength` (`none`, `incidental`, `integrated`, `direct`).
8. Select five primary strategies and three reserves. Give every strategy an
   `avatar` and set `cover.clientName` (brand name or product URL): each brief
   renders as `analyze <url>` / `Recreate the video for <product>` / `Change
   the Avatar: <avatar>`, the wording that routes it to the clone flow. Keep
   `keep`/`change`/`overlays` as report context only, so the brief stays a
   close recreation. Re-run `curation validate` on the final selections and
   strategies, then run `report` variant `build` in strict mode for the
   13-slide HTML and markdown research preview, then `report` variant `pdf`.

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
