---
name: initial-social-content-research
description: >-
  Run end-to-end initial social content research from a product URL and brief:
  research the product and competitors, discover TikTok, Instagram Reels, Meta
  Ads, and YouTube Shorts content, curate cross-platform examples, and generate
  a 20-slide AdAnt research report that closes with copy-paste Adant messages
  for the top 5 inspiration videos. Use when an agent needs a first-pass social
  landscape, competitor/content audit, or research deck for a product or brand.
---

# Initial Social Content Research

Produce a source-labeled research workspace and a 20-page content research deck:
13 research pages, then a Sample Content Strategy section that turns the 5
strongest inspiration videos into copy-paste Adant messages. Treat this as
research, not a sales pitch: exclude pricing and deliverables.

## Resolve paths and inputs

1. Resolve `SKILL_DIR` as the directory containing this file and `PLUGIN_ROOT`
   as its grandparent (`SKILL_DIR/../..`). Never assume the caller's current
   directory contains `skills/`.
2. Choose a writable `WORKSPACE_ROOT` outside `PLUGIN_ROOT`. Put every generated
   artifact, browser profile, thumbnail, and report there.
   Set `ADANT_SOCIAL_DATA_DIR` to `WORKSPACE_ROOT/.runtime` before invoking any
   browser component so persistent profiles never land in the plugin install.
3. Obtain only missing required inputs: product website URL and natural-language
   product context. Default `preparedFor` to blank, `timeRange` to `3months`,
   and `targetCountry` to `US` unless the user specifies them.
4. Read [references/initial-social-content-research.anyt](references/initial-social-content-research.anyt)
   before execution for the exact CLI flags, intermediate schemas, curation
   thresholds, and report mapping. Translate every relative `skills/...` path
   in that reference to an absolute path below `PLUGIN_ROOT`.

## Preflight

- Require Python 3.11+, `uv`, Node.js/npm, and Google Chrome. Confirm AdAnt CLI
  authentication with a read-only command such as `npx @anyloop/adant-cli credit balance`;
  if missing, ask for `npx @anyloop/adant-cli auth login`. Never request a Gemini or other
  upstream model-provider key and never write credentials into the plugin or project.
- Browsing runs in headless research browsers: no windows, no focus stealing, and
  every browser muted with autoplay blocked, so a feed of short-form video never
  plays over the user's work.
- **Get the user signed in to TikTok and Instagram before browsing them.** Signed
  out, those two return almost nothing, so a session is the difference between
  research and an empty file. Check with each skill's `--login-check` (opens and
  launches nothing) and, when it reports `logged_in: false`, ask the user in chat
  to run that skill's `--login` once. Nothing opens a window on its own — only
  that deliberate command does. Do not copy, expose, or log cookie contents.
  YouTube Shorts and Meta Ads Library need no login.
- Read a component skill's `SKILL.md` before invoking its runtime. Model-backed
  components use authenticated AdAnt agent or media API calls; browsing and report
  components remain deterministic/local.
- Preserve raw source URLs and label fallbacks in JSON. Never present inferred
  or search-fallback metrics as directly browsed platform data.

## Run the workflow

1. **Product profile:** run `product-research` with the URL and notes. Read its
   `brand_folder`, create that folder below `WORKSPACE_ROOT`, and place the
   profile there.
2. **Competitors:** run `competitor-research`; derive confirmed competitors from
   Tier 1 and Tier 2. In autonomous mode, accept those tiers and record that
   choice. Otherwise, offer one concise review checkpoint.
3. **Keywords:** run the TikTok and Instagram keyword skills and derive a
   YouTube-native list. For apps, retain explicit `app`, `app review`, and
   category-app variants in organic searches. Then derive a second **product
   keyword set** per platform — competitor product names as users search them,
   the client name, and `apps like X` / `X alternative`. Browse both sets and
   merge the pools; the theme set alone reliably produces an off-category deck.
4. **Platform research:** run TikTok, Instagram Reels, Meta Ads Library, and
   YouTube Shorts research. Parallelize only independent processes and never
   launch two instances that compete for the same fixed CDP port. Use the
   documented fallbacks when login or indexing blocks a platform and record the
   fallback source. Check every browse's **per-query counts**, not just its
   total: a query returning zero while its siblings return dozens is a capture
   failure to retry one-per-invocation, never a finding. For Meta Ads, select
   competitors by their Facebook **Page name** (`Alarmy - My Daily Success
   Habits`, not `Alarmy`) and never report a category as running no ads on the
   strength of an empty keyword search.
5. **Curation:** select roughly five official brand/competitor examples and five
   organic creator examples per organic platform. Apply the reference's
   **relevance gate first** — a video stays only if it shows the client's or a
   named competitor's product, shows the job the product does, or states the
   problem it solves; sharing a technology, aesthetic, or topic is not enough.
   Rank on engagement only within what survives, since off-category posts
   routinely out-perform on-category ones several times over. Then apply the
   engagement floors to creators only, keep no more than three videos per
   account, and cover at least three formats per platform.
6. **Report data:** assemble `report_data.json` from evidence, not invented
   claims. Include direct platform/ad URLs, source labels, and local thumbnails.
   Tag every curated card with its **content type** — branded/owned IP,
   branded commercial, educational (story or animation), UGC testimonial, or a
   category-specific type the evidence justifies. The tag is cross-cutting: the
   platform slides keep their fixed order (brand/competitor, then organic
   creator, per platform), and the type distribution drives only the executive
   summary, the formats slide and the strategy section. An unoccupied type is
   the most actionable thing a research deck can report.
7. **Sample content strategy:** pick the 5 strongest inspiration videos from the
   curated set — rank by engagement, then cloneability and format diversity, at
   most one per account and at least two platforms. **Run
   `trend-video-understanding` on every pick before writing its strategy** and
   derive two things from the analysis rather than from habit: the **avatar
   type** (UGC / animation — naming the style / commercial / cinematic /
   narrator-only / product-only), and the **reuse axis** (keep the hook, the
   viral format, the visual style, the structure, the pacing, or the format
   inverted). Defaulting every pick to a UGC avatar and "keep the hook" is the
   failure mode this step exists to avoid. Read `social-content-strategist`'s
   `SKILL.md` first; the deck reuses its General Instructions verbatim.
8. **Report:** run `social-content-research-report`, then
   `slide-pdf-generator`, using absolute runtime paths under `PLUGIN_ROOT` and
   output paths under `WORKSPACE_ROOT`.

## Verify and deliver

- Confirm the HTML, Markdown, and PDF exist.
- Confirm the PDF has exactly 20 landscape pages (13 research + opener + 5
  strategies + closing), no placeholder/gray thumbnail boxes, no clipped
  content, and no pricing or deliverables.
- Confirm every featured example has a usable URL, account, metric, format, and
  source label; disclose missing or fallback platform coverage.
- Confirm every featured example passes the relevance gate, and be able to name
  which test each one meets. A card you can only justify by its view count is a
  card to replace. Ship fewer relevant cards over a full off-category set, and
  say which slots were short.
- Before stating that something does not exist — no competitor ads, no brand
  presence, no content in a format — confirm the search that would have found it
  actually ran and returned data. Distinguish "we looked and it is not there"
  from "the capture came back empty", and word the deck accordingly.
- Confirm each of the 5 strategy messages names a real inspiration URL that also
  appears in the research slides, and that no URL or account repeats across
  them.
- Return clickable paths to the report and a short inventory of intermediate
  artifacts. Do not claim completion if the report renderer or required
  validation fails.
