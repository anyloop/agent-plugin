---
name: social-content-strategist
description: >-
  Turn an initial social research report—or a product URL, description, and
  example videos—into 5–10 product-specific content strategies based on recent
  TikTok, Instagram Reels, Meta Ads, and YouTube Shorts trends. Use when Codex
  needs fresh inspiration videos, concept-deduplicated strategy batches, or an
  updated strategy report that excludes previously used ideas and URLs in
  Codex or Claude Code.
---

# Social Content Strategist

Find recent, cloneable inspiration and generate concise strategy blocks while
maintaining history so later batches do not repeat URLs or concepts.

## Resolve paths and choose a mode

1. Resolve `SKILL_DIR` as the directory containing this file and `PLUGIN_ROOT`
   as its grandparent (`SKILL_DIR/../..`). Never assume the caller's current
   directory contains `skills/`.
2. Choose a writable `WORKSPACE_ROOT` outside `PLUGIN_ROOT`. Store downloads,
   browser profiles, candidate analyses, strategy output, and history there.
   Set `ADANT_SOCIAL_DATA_DIR` to `WORKSPACE_ROOT/.runtime` before invoking any
   browser component so persistent profiles never land in the plugin install.
3. Use report mode when the user supplies an initial research `.md` or `.pdf`.
   Use standalone mode when the user supplies a product URL and description.
   Example videos are optional in either mode and must be excluded from results.
4. Default the strategy count to 8 and the recency window to 60 days. Accept only
   5–10 strategies and a 30- or 60-day window unless the user explicitly changes
   the workflow requirements.
5. Read [references/social-content-strategist.anyt](references/social-content-strategist.anyt)
   before execution for exact CLI flags, candidate thresholds, schemas, and
   retry behavior. Translate every relative `skills/...` path in that reference
   to an absolute path below `PLUGIN_ROOT`.

## Preflight

- Require Python 3.11+, `uv`, `yt-dlp`, Node.js/npm, and Google Chrome. Confirm
  AdAnt CLI authentication with `npx @anyloop/adant-cli credit balance`; if missing, ask
  for `npx @anyloop/adant-cli auth login`. Never request a Gemini or other upstream model
  key. `TIKAPI_KEY` remains optional for the documented TikTok fallback only.
- Browsing runs in headless research browsers: no windows, no focus stealing, and
  every browser muted with autoplay blocked, so a feed of short-form video never
  plays over the user's work.
- **Get the user signed in to TikTok and Instagram before browsing them.** Signed
  out, those two return almost nothing. Check with each skill's `--login-check`
  (opens and launches nothing). When it reports `logged_in: false`, tell the user
  that one dedicated, muted sign-in window is about to open, then run that skill's
  `--login` and ask them to sign in, close the window, and confirm. Open it at
  most once per platform per workflow. After confirmation, re-run `--login-check`
  before browsing. If the user declines or asks to skip, or the check still
  fails, do not open it again or keep prompting; use the documented fallback and
  disclose the thinner coverage. Do not copy, expose, or log cookie contents.
- If the check reports `logged_in: null`, its cookie store was unreadable. Explain
  that briefly and continue with the fallback without opening a sign-in window.
- A local cookie can be revoked server-side. If every TikTok or Instagram query
  returns zero despite `logged_in: true`, treat the session as expired. If that
  platform's sign-in window has not opened in this workflow, use the same one-time
  sign-in flow and retry once; otherwise use the fallback without another prompt.
- Read a component skill's `SKILL.md` before invoking its runtime.
- Keep source URLs and source labels through every transformation.

## Run the workflow

1. **Ingest:** read the report and adjacent product/keyword artifacts when
   available. In standalone mode, run `product-research` to create a profile.
2. **History and exclusions:** initialize or load strategy history. Merge past
   inspiration URLs and client-liked example URLs into `excluded_urls` before
   browsing or ranking candidates.
3. **Keyword mining:** run `content-strategy-generator`'s keyword miner over the
   report and/or example videos. Prioritize language found in winning examples,
   then product seeds and adjacent creative angles. Keep at least half of an
   app product's keywords explicitly app-related.
4. **Trend research:** browse TikTok, Instagram Reels, Meta Ads, and YouTube
   Shorts. Enforce the selected recency window after collection and record any
   fallback. Avoid concurrent processes that compete for a fixed CDP port.
5. **Candidate selection:** normalize URLs, deduplicate, exclude history, reject
   unavailable or stale videos, and apply the documented engagement floor.
   Rank by engagement, recency, relevance, cloneability, and format diversity;
   retain roughly twice the requested strategy count.
6. **Video understanding:** run `trend-video-understanding` for every retained
   candidate. It calls authenticated `adant-cli media analyze`, so respect AdAnt
   usage and limit concurrency to 3–4 jobs. Drop failures and top up the pool.
7. **Strategies:** run `content-strategy-generator` with the candidate manifest
   and history. If it exits with code 2 because all concepts are too similar,
   expand to adjacent angles and repeat research rather than weakening dedupe.

## Verify and deliver

- Confirm the requested number of strategies was produced and history updated.
- Confirm every strategy cites a usable inspiration URL and contains a concise
  reuse axis, adaptation direction, avatar suggestion, and 2–3 overlay lines;
  reject full scripts or timeline-heavy output.
- Confirm each avatar names a TYPE grounded in that video's analysis — UGC,
  animation (with the style: 3D, anime, 2D, Pixar-style, claymation, ink-wash),
  commercial/TVC, cinematic actor, narrator-only, or product-only. An animated
  or studio reference must never yield a "UGC avatar"; read
  `fingerprint.character`, `setting` and the narrative visual-style notes.
- Confirm the reuse axis VARIES across the batch and is justified per video:
  keep the hook, the viral format, the visual style, the structure, the pacing,
  or the format inverted. A batch where every entry says "keep the hook" has not
  read its own analyses.
- Confirm no URL appears in prior history, exclusions, example videos, or twice
  in the new batch. Confirm analyzed concepts are not near-duplicates.
- Return clickable paths to the strategy Markdown and history JSON, plus a short
  note about rejected candidates and platform fallbacks.
