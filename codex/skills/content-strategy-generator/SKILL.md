---
name: content-strategy-generator
description: Generate 5-10 copy-ready product content strategies from an AdAnt research report, example videos, and analyzed trend-video candidates, excluding prior inspirations and near-duplicate concepts.
---

# Generate Content Strategies

Call `doctor`; bootstrap a `research` token if needed without exposing it.

1. Run `research_run` phase `strategy-keywords` with the product, niche,
   research report or supplied videos, optional profile/caption evidence, base
   keywords, and an output artifact. Pass every example video the user gave
   as `--video`: the phase fetches each seed's caption, mines the hashtags the
   winning videos actually use, and writes the per-platform queries from
   them. `--report` takes the initial report as markdown or PDF, or the JSON
   `adant_get_product_report` returns for a saved report's URL or id — its
   cited videos are mined for keywords and belong in the exclusion list.
2. Browse platforms one at a time with the platform phases. Prefer strong,
   recent, product-relevant videos; keep 5-10 candidates and record why each
   qualifies.
3. Analyze candidates with phase `strategy` in batches of at most two. Capture
   hook, structure, pacing, shots, overlays, audio, CTA, reusable mechanism, and
   promotion strength.
4. Run phase `content-strategies` with report/product details, candidate
   analysis, optional history, target count, and output/history artifacts.
   The history's `excluded_urls` holds every seed video and every video a
   prior report already shows; candidates are matched to it by platform id,
   so URL spelling does not matter.

Hard-exclude URLs already in history. Reject concepts too similar to previous
strategies. Each result must include source URL/evidence, product-specific angle,
hook, beat-by-beat script, shot list, overlay/audio direction, CTA, why it fits,
and a copy-ready AdAnt instruction. Preserve the viral mechanism without copying
brand claims or unsupported facts.
