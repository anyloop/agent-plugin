---
name: content-strategy-generator
description: Generate 5-10 copy-ready product content strategies from an AdAnt research report and analyzed trend-video candidates, excluding prior inspirations and near-duplicate concepts.
---

# Generate Content Strategies

Call `doctor`; bootstrap a `research` token if needed without exposing it.

1. Run `research_run` phase `strategy-keywords` with the product, niche,
   research report or supplied videos, optional profile/caption evidence, base
   keywords, and an output artifact.
2. Browse platforms one at a time with the platform phases. Prefer strong,
   recent, product-relevant videos; keep 5-10 candidates and record why each
   qualifies.
3. Analyze candidates with phase `strategy` in batches of at most two. Capture
   hook, structure, pacing, shots, overlays, audio, CTA, reusable mechanism, and
   promotion strength.
4. Run phase `content-strategies` with report/product details, candidate
   analysis, optional history, target count, and output/history artifacts.

Hard-exclude URLs already in history. Reject concepts too similar to previous
strategies. Each result must include source URL/evidence, product-specific angle,
hook, beat-by-beat script, shot list, overlay/audio direction, CTA, why it fits,
and a copy-ready AdAnt instruction. Preserve the viral mechanism without copying
brand claims or unsupported facts.
