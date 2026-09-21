# Report data

Write one JSON object. Keep URLs permanent and metrics dated. The native report
uses these fields (additional evidence fields are retained in the downloadable JSON):

- `layout`: omit for the full research report; `strategy_brief` for the
  strategist's subset (cover, searched platforms, Meta Ads when searched,
  strategies). A brief omits `exec`, `landscape`, `competitive` and `formats`.
- `cover`: `clientName`, `reportSubtitle`, `reportDate` (YYYY-MM-DD).
  Read the actual date with `date -u +%F`; observation dates come from source
  retrieval timestamps such as `collectedAt`, never a guessed model date.
- `exec`: `headline`, `findings` (array of strings), `recommendation`.
- `landscape`: `headline`, `copy`, `stat`, `statSuffix`, `statLabel`, `statPlatforms`.
  Omit the statistic when no sourced comparable measurement exists.
- `competitive`: `tiers` (array of `{header, brand, badge, desc}`).
- `formats`: `headline`, `items` (array of `{tag, name, desc}`).
- `platforms`: `tiktok`, `instagram`, `youtube`, each with `brand_headline`,
  `brand_intro`, `brand_videos`, `creator_headline`, `creator_intro`,
  `creator_videos`. Use `brand_empty_note`/`creator_empty_note` for gaps.
- A video: `url`, `handle`, `metric` (a measured count and unit), `format`,
  `tier` — the collection's own label for that candidate, `outlier` (cleared
  its platform's bar), `reference` (measured, fell short) or `unverified`
  (could not be measured); copy it, never upgrade it, and never omit it for a
  video the collection judged. Omission is not neutral: an untagged video reads
  as unknown, and one untagged card keeps the whole slot's "nothing met the
  bar" note from appearing — and
  `thumb` — the candidate's `thumbnailUrl` from the collection (an https URL the
  save tool fetches into private storage) or the path of a thumbnail you uploaded.
  Omit `thumb` when the collection had none — the save and the PDF renderer then
  take the image from the video at `url` — and never invent one. Add
  `observedAt`, `relationship`, and `evidence` when relevant.
- `meta_ads`: `headline`, `intro`, `ads` (each with `advertiser`, `ad_id` (the Ad
  Library id from the collection — the save derives a missing `thumb` from it),
  `url`, `query`, and `thumb` from the ad's `thumbnailUrl`), `empty_note` when
  unavailable. Always keep `ad_id`: the save takes the creative's frame from
  the Ad Library when `thumb` is absent or dead. Never invent impression counts.
- `strategies`: `headline`, `intro`, `items` (primary strategies), `reserves`.
  Each item requires `title`, `url` (the analyzed source video), `platform`,
  `why_this_video`, `avatar`, `product`, `keep`, `change`, `overlays`, `message`.
  `platform` is one of `tiktok`, `instagram`, `youtube`, `meta-ads` (the server
  also reads "TikTok", "Instagram Reels", "YouTube Shorts", "Meta Ads" and
  "Facebook"). `analysisArtifactId` is the analysis reference the video was
  watched through; a primary without one on a `complete` report is a warning.
  `overlays` must be an array of strings. Include the source `handle`, `format`,
  measured `metric` and `thumb` when available so the native strategy card has
  context and an image — and always the exact `url`, because that is what the
  image falls back to. Copy the candidate's `tier` as `source_tier`, never
  upgraded: the card, the PDF and the run email say when a strategy was built
  on a video that fell short of the bar.
  Also preserve `hook`, `audience`, `script`, `cta`, `analysisArtifactId`
  (kept by the save) and `hashtags` (at most five, the brand tag first);
  `shots` and `risks` are dropped by the save — write them for your own
  reasoning, and do not promise the user they will appear.
  The three-line `message` is the creative handoff.
- `hashtags`: the recommendation (`references/hashtag-recommendation.md`) —
  `max_per_post` (5), `pools` (`brand`, `competitor`, `niche`, `community`,
  `observed`, each an array of `#tags`) and `sets` per platform (`tiktok`,
  `instagram`, `youtube`, each with `default` and `competitor` arrays). The
  native page does not render it yet; the save keeps it in the downloadable
  JSON and the social manager reads it through `retrieve_strategy`.
- `sources`: array of `{url, title, observedAt}` for product/competitor evidence.
- `gaps`: array of plain-language missing evidence and failed acquisition notes.
- `status`: `complete` or `partial`. `requestedStrategyCount`: default 5.

The save keeps `status`, `requestedStrategyCount`, `gaps`, `sources`,
`strategies.reserves` and each strategy's `hook`, `script`, `cta`, `audience`,
`observedAt` and `analysisArtifactId`; the native report renders them as an
"Evidence and limitations" section and an evidence badge on every strategy
card. A `complete` report that lists gaps, or delivers fewer strategies than
`requestedStrategyCount`, is saved as `partial`. A reserve needs only `url`;
the server never composes a Studio brief for it.

For partial delivery, also say so in the subtitle and summarize the gaps in
the strategy intro. Do not describe unanalyzed reserve URLs as verified strategies or publish
unverified metrics for them. Adaptations must not invent a real patient's treatment
history, guaranteed results, or endorsements; label concepts and attribute brand claims.

At least one grounded strategy is required by Social Strategy. With no analyzed
sources, say so in the reply, list the evidence you did gather with its source
URLs and dates, and explain why no report could be saved. Do not invent a
strategy to satisfy the schema, and do not save a Markdown stand-in — an
unsaved run has no deliverable, and saying so plainly is the honest outcome.
