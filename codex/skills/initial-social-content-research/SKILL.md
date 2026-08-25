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

- Run the one-shot preflight **once** before anything else, with
  `ADANT_SOCIAL_DATA_DIR` already exported:

  ```bash
  python3 {PLUGIN_ROOT}/runtime/doctor.py --json
  ```

  It checks Python 3.11+, `uv`, Node.js/npm, Google Chrome, `yt-dlp`, AdAnt CLI
  authentication (read-only, equivalent to `npx @anyloop/adant-cli credit balance`),
  and both platform sessions in a single pass. Report every missing item to the
  user in **one consolidated message** — each with its fix command, an expected
  time cost, and the consequence of skipping — instead of surfacing failures one
  at a time mid-run. If authentication is missing, ask for
  `npx @anyloop/adant-cli auth login`. Never request a Gemini or other
  upstream model-provider key and never write credentials into the plugin or
  project. Re-run `doctor.py` after the user reports a fix; do not re-litigate
  items that already passed.
- Browsing runs in headless research browsers — muted, autoplay blocked, no
  focus stealing — so a feed of short-form video never plays over the user's
  work. The only windows this workflow may show are the **Sidecar progress
  window** (below) and, when needed, the one-time platform sign-in window.
- **Sidecar progress window:** the first research command (`doctor.py` or any
  `run_phase.py run`) automatically starts a local progress server bound to
  127.0.0.1 and opens one small read-only Chrome app window that renders the
  live event stream — you never start it as a separate step. Read the
  `sidecar: ready <url>` / `sidecar: disabled (<reason>)` line it prints:
  relay the URL to the user once ("progress is visible in the AdAnt window on
  the right"), and on `disabled` continue chat-only without treating it as an
  error. All decisions stay in chat; the window only observes. If the user asks
  not to open a window, export `ADANT_NO_SIDECAR=1` for the rest of the
  workflow. The server exits by itself when research goes quiet.
- **Get the user signed in to TikTok and Instagram before browsing them.** Signed
  out, those two return almost nothing, so a session is the difference between
  research and an empty file. `doctor.py` already ran each skill's `--login-check`
  (opens and launches nothing), so fold session status into the same consolidated
  preflight message. When it reports `logged_in: false`, tell the user that one
  dedicated, muted foreground sign-in window is about to open, then run that skill's
  `--login` so it opens directly in front via Chrome. Ask them to sign in, close
  the window, and confirm. Open it at
  most once per platform per workflow. After confirmation, re-run `--login-check`
  before browsing. If the user declines or asks to skip, or the check still
  fails, do not open it again or keep prompting; use the documented fallback and
  disclose the thinner coverage. Do not copy, expose, or log cookie contents.
  The visible login window should be explicitly brought forward, stay muted, and
  block autoplay so it does not disrupt the user's work. YouTube Shorts and Meta
  Ads Library need no login.
- If the check reports `logged_in: null`, its cookie store was unreadable. Explain
  that briefly and continue with the fallback without opening a sign-in window.
- A local cookie can be revoked server-side. If every TikTok or Instagram query
  returns zero despite `logged_in: true`, treat the session as expired. If that
  platform's sign-in window has not opened in this workflow, use the same one-time
  sign-in flow and retry once; otherwise use the fallback without another prompt.
- Read a component skill's `SKILL.md` before invoking its runtime. Model-backed
  components use authenticated AdAnt agent or media API calls; browsing and report
  components remain deterministic/local.
- Preserve raw source URLs and label fallbacks in JSON. Never present inferred
  or search-fallback metrics as directly browsed platform data.

## Progress events and parallel fan-out

Long phases run through the shared wrapper so progress lands on the Sidecar
event bus (`$ADANT_SOCIAL_DATA_DIR/progress/events.jsonl`) without any extra
bookkeeping:

```bash
python3 {PLUGIN_ROOT}/runtime/run_phase.py run \
  --phase <phase-id> --skill <skill-name> --label "<short human label>" \
  -- <the phase command exactly as documented>
```

Canonical phase ids: `doctor`, `product-profile`, `competitors`, `keywords`,
`platform-tiktok`, `platform-instagram`, `platform-meta-ads`,
`platform-youtube`, `curation`, `report`, `strategy`.

**Run independent work in parallel — this is the expected shape, not an
optimization.** Sequential runs of independent phases waste 10+ minutes of the
user's time:

- Step 3: the TikTok and Instagram keyword skills are independent — launch both
  with `run_phase.py run --bg`, then `run_phase.py status --wait`.
- Step 4: the four platform browses (4a-4d) are independent — launch all four
  as background jobs the same way, then wait once:

  ```bash
  python3 {PLUGIN_ROOT}/runtime/run_phase.py run --bg --phase platform-tiktok \
    --skill browse-tiktok-research -- <documented browse command>
  # ... repeat for platform-instagram, platform-meta-ads, platform-youtube ...
  python3 {PLUGIN_ROOT}/runtime/run_phase.py status --wait --timeout 1800
  ```

- Step 7: the five `trend-video-understanding` analyses are independent — run
  them concurrently the same way (`--phase strategy`, one suffix per pick, e.g.
  `strategy-pick-1`).

Where the host supports parallel agents or parallel tool calls, those may
replace background jobs; detached `--bg` jobs are the portable default and
survive the end of a single tool call. Rules: parallel jobs must write
**separate output files** (the documented per-platform paths already do);
never share an output path; check `status` output and each job's log before
declaring a phase complete; top-up passes that depend on curation results stay
sequential. A failed background job is a failed phase — rerun it in the
foreground to diagnose, never silently continue.

## Run the workflow

1. **Product profile:** run `product-research` with the URL and notes. Read its
   `brand_folder`, create that folder below `WORKSPACE_ROOT`, and place the
   profile there.
2. **Competitors:** run `competitor-research`; derive confirmed competitors from
   Tier 1 and Tier 2. In autonomous mode, accept those tiers and record that
   choice. Otherwise, offer one concise review checkpoint.
3. **Keywords:** run the TikTok and Instagram keyword skills and derive a
   YouTube-native list. Build separate **theme**, **product**, **brand-owned**,
   and **branded partnership** query sets. Product queries name the client,
   competitors, product/model names, and high-intent actions such as review,
   comparison, sizing, fitting, setup, maintenance, troubleshooting, and
   `best X for Y`. App queries retain explicit `app`, `app review`,
   `apps like X`, and `X alternative` variants. Derive a
   third **branded partnership set** for the client and every confirmed Tier 1/2
   brand using
   plain and hashtagged brand names; product-use variants such as `review`,
   `demo`, and `tutorial`; and relationship variants such as `ad`, `partner`,
   `collaboration`, and `ambassador`. Search both brand-name text and brand-name hashtags.
   Do not require disclosure or sponsorship language for discovery.
   Batch partnership searches by brand when the set exceeds 12 queries,
   preserving per-query provenance.
   Before top-up research, generate a gap-aware query plan from the current
   artifacts:

   ```bash
   python3 runtime/discovery_policy.py \
     --data report_data.json --profile product_profile.json \
     --competitors competitors_confirmed.json --audit curation_audit.json \
     -o discovery_top_up_plan.json
   ```

   Treat the plan's ordered `passes` as required work, not suggestions. Brand
   gaps progress through verified accounts, product queries, brand hashtags,
   partnership content, retailers/distributors, then indexed fallback. Creator
   gaps progress through exact products, competitor products, product decisions,
   precise problems, relevant mined hashtags, then indexed fallback. Each pool
   targets a 12-candidate relevance-qualified buffer for five cards. Four cards
   per brand/creator page is the delivery minimum; five remains the target.
   The plan automatically mines hashtags from candidates with specificity 2-3,
   adds content-type expansion queries for missing educational, testimonial,
   commercial, and owned lanes, and emits executable batches of at most eight
   queries. Never expand from off-category posts.
4. **Platform research:** collect auditable official brand, branded creator
   partnership, and independent creator pools per organic platform. For brands,
   browse verified account/channel pages plus product/model queries, then
   over-collect enough candidates to rank by reach instead of accepting the
   first five posts returned. If the official set is low-reach or thin, run a
   product-specific top-up across confirmed brands, retailers, and distributors.
   Run partnership queries separately; treat relevant brand tags as candidate
   signals, not proof of sponsorship. For shortlisted creator posts, inspect
   captions, descriptions, platform partnership labels, promo codes, and the
   creator profile bio and outbound links, then run
   `trend-video-understanding --brand` to score how directly each video promotes
   the named product. Preserve caption,
   profile, and video evidence separately. For creators, run product queries
   before broad theme queries. Check every browse's per-query counts and retry
   isolated zero-result queries once; a capture failure is not a market finding.
   Recompute the gap plan after each pass. Each mode emits up to three primary
   batches of eight queries plus auditable reserve batches. Run primary batches,
   re-curate, and run reserve batches only while that page remains below four.
   Stop only when each page has at least four qualified cards, continuing toward
   five from a 12-candidate buffer. Search each thin platform directly and
   through its indexed fallback; a zero-result capture advances to the next
   pass, not to an empty slide. Content-type expansion and relevant mined
   hashtags run before creator engagement floors relax. Product relevance and
   brand attribution never relax.
   For Meta Ads, select competitors by their exact Facebook Page name.
5. **Curation:** apply product relevance before engagement. Every selected card
   records a relevance test, concrete caption/transcript/on-screen evidence, and
   a specificity score. Accept exact products/models, named competitor products,
   product decisions/services, or a precise product problem. Reject general-topic
   montages, lifestyle footage, and category showcases where a product is merely
   incidental. The brand side can combine owned posts with creator partnerships, sponsored UGC, KOC/KOL
   placements, affiliate integrations, ambassador content,
   and well-supported potential collaborations. Without a disclosure, require a
   directly promotional creator-native video plus independent profile evidence,
   label the inference explicitly, and never present it as confirmed sponsorship.
   Within
   the eligible brand pool, rank by observed reach, relationship confidence, and
   account/format diversity; the highest-reach eligible candidate on each
   platform must be represented. Rank independent creators by reach only after
   the specificity gate. Start at 50K engagement; use 10K only after the
   targeted top-up cannot fill five relevant creator cards, use 1K after every
   top-up mode completes, and allow a no-minimum verified-niche fallback only
   when four relevant cards still cannot be filled at 1K. Record
   `creator_floor`, both pools' `*_search_modes`, and
   `*_top_up_complete: true` whenever a candidate pool remains below 12, a card
   pool remains below five, or the creator floor drops below 50K. Select at
   least three distinct content types across each platform. Write all
   searched, selected, and rejected candidates with reasons to
   `curation_audit.json`.
6. **Report data:** assemble `report_data.json` from evidence, not invented
   claims. Include permanent platform/ad URLs, source labels, local thumbnails,
   and each card's `relevance` object from the audit. For brand-side creator
   posts, retain `relationship` (`owned`, `confirmed_paid`,
   `commercial_affiliate`, `potential_collaboration`, or `brand_attributed`),
   `relationship_confidence`, `relationship_evidence`,
   `creator_profile_evidence`, `promotion_strength`, `promotion_evidence`,
   and `discovery_query`. Use `Sponsored creator UGC` only when a platform
   label, disclosure, or explicit partnership wording confirms it. Affiliate
   codes alone do not prove sponsorship. A product demo with
   only a brand tag or hashtag remains a discovery candidate: analyze the video and profile. Call it
   `Potential creator collaboration` only when the video is directly promotional
   and independent profile evidence supports an ongoing relationship; otherwise
   use `Creator product integration`. Run
   `runtime/validate_curation.py --data report_data.json --audit
   curation_audit.json` before building the deck; fix failures rather than
   weakening the relevance or reach rules.
   Validate production reports with `--require-min-cards 4
   --require-type-coverage`. When the request requires every content card
   filled, add `--require-full-cards`; this requires exactly five brand and five
   creator selections on each organic platform.
   Tag every curated card with its **content type** — branded/owned IP,
   branded commercial, educational (story or animation), UGC testimonial, or a
   category-specific type the evidence justifies. The tag is cross-cutting: the
   platform slides keep their fixed order (brand/competitor, then organic
   creator, per platform), and the type distribution drives only the executive
   summary, the formats slide and the strategy section. An unoccupied type is
   the most actionable thing a research deck can report.
   Keep the evidence layer and presentation layer separate: detailed search
   coverage, rejected candidates, exclusion reasons, blank captions, missing
   handles, threshold exceptions, and verification notes belong only in
   `curation_audit.json`. Never paste an audit narrative into slide copy.
   Every video-card page (`brand_intro`, `creator_intro`, and `meta_ads.intro`)
   gets one short insight, with two sentences and 160 characters as hard
   maximums. The intro should interpret the cards, not enumerate them. Follow
   the field budgets in `social-content-research-report` and run its builder
   with `--strict` before rendering.
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
9. **Save to AdAnt:** when the AdAnt Remote MCP (`adant_*` tools) is
   connected, follow `social-content-research-report`'s **Save to AdAnt**
   section — `handoff.py manifest` → `adant_prepare_uploads` →
   `handoff.py upload` → `adant_complete_uploads` → `handoff.py payload` →
   `adant_save_product_report`. Keep the returned `url`; it is the
   deliverable's primary link. Without the MCP, deliver the files and say the
   report was not saved to AdAnt.

## Verify and deliver

- Confirm the HTML, Markdown, and PDF exist.
- When the report was saved to AdAnt, lead the closing message with the
  Studio link ("Saved to your AdAnt Drive — open <url> to read the report and
  start any strategy in Studio") and relay any `warnings[]` in one line. Pass
  the `reportId` back into a re-run so the new version joins the same report.
- Confirm the PDF has exactly 20 landscape pages (13 research + opener + 5
  strategies + closing), no placeholder/gray thumbnail boxes, no clipped
  content, and no pricing or deliverables.
- Confirm every featured example has a usable URL, account, metric, format, and
  source label; disclose missing or fallback platform coverage.
- Read every video-card page as a client would: keep only one concise takeaway,
  never search methodology. Confirm `brand_intro`, `creator_intro`, and
  `meta_ads.intro` are at most two sentences and 160 characters; prefer one.
- Confirm every brand-side creator post has relationship evidence. Do not infer
  sponsorship from reach, production quality, or a brand hashtag alone. Do not
  discard a relevant hashtag candidate for lacking disclosure: inspect its
  profile, analyze its promotion strength, and label supported but unconfirmed
  cases as potential collaborations.
- Confirm the partnership sweeps searched both each brand name and its hashtag
  form on TikTok, Instagram, and YouTube, and preserve the per-query counts even
  when the sweep returns no usable posts.
- Confirm every featured example passes the relevance gate, and be able to name
  which test each one meets. A card you can only justify by its view count is a
  card to replace. Ship fewer relevant cards over a full off-category set, and
  say which slots were short.
- Confirm every thin pool ran every ordered primary batch and, while below four,
  the required reserve batches in
  `discovery_top_up_plan.json`, including content-type expansion, relevant mined
  hashtags, and indexed fallback. Record the modes in `brand_search_modes` or
  `creator_search_modes` and set the matching `*_top_up_complete: true` before
  accepting fewer than 12 candidates, fewer than five cards, or a sub-50K
  creator floor. Never deliver a page below four cards and never lower
  specificity to fill one.
- Confirm each platform's audit includes official-account and product-query
  brand searches, includes its highest-reach eligible brand candidate, and gives
  a reason for every higher-reach candidate that was rejected.
- Confirm creator cards have specificity 2 or 3 with concrete evidence. Merely
  showing somebody skiing, surfing, exercising, studying, or using the broad
  category is not product relevance.
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
