## Balance relevance and engagement

Treat collection outlier labels as discovery hints, not final selection. First
require concrete product, competitor, decision, or precise audience-problem
proof. A broadly related viral post is ineligible regardless of likes. Within
that qualified pool prefer stronger observed engagement, then use audience fit,
replicable format, creator diversity, and recency to resolve tradeoffs. Do not
rank by relevance alone or by a global cross-platform score.

- Target **10,000 likes on TikTok/Instagram** and **10,000 views on YouTube**.
  YouTube views measure reach, not likes. Never substitute follower counts,
  impressions, comments, or unlabeled numbers. Keep the original unit and
  `metric_observed_at` plus source URL, publication date (or unknown), and
  acquisition method (`server` or `signed-in-browser`) in each audit record.
  Recheck finalists during this run; never claim login or freshness from an
  earlier run. Mark older evergreen references explicitly, not as current trends.
- For a four- or five-card creator page, at least **60%** should meet the target.
  Use up to two below-target examples only for a specific missing use case or
  format. Give each `selection_role: "context"` and a concrete
  `selection_reason`; visibly label the card as context in its `format` and
  summarize exceptions in the page intro. Do not call them proven winners.
- When a rejected candidate has at least twice the engagement and equal or
  stronger relevance specificity, record why the selected candidate fits the
  audience/use case or adds a necessary format better in `selection_reason`.
  A generic "relevant" or "diverse" rationale is not sufficient evidence.
- A full page is not a stopping condition. Run the curation plan for quality
  gaps as well as card gaps. Try high-engagement sorting where available and
  precise audience-problem/use-case queries, not just tiny official accounts.
  Keep attempted queries, result counts, and rejected alternatives. Never mark
  unrun search modes exhausted just to unlock a lower `creator_floor`.
- If the bounded search cannot produce enough strong relevant evidence, record
  `creator_quality_gap` with the missing evidence and searches attempted; name
  the limitation in the report. A lower fallback floor is not a quality pass.
  Do not discard stronger qualified candidates merely to fill a niche checklist.
- Keep brand/competitor posts and Meta ads as positioning evidence unless actual
  performance is available. A partnership label proves disclosure, not success;
  an active ad proves activity, not conversions. Do not apply organic like
  targets to paid ads. Long-form references over 180 seconds are context, not
  short-form performance templates, even if their engagement is high.
- Lead the five primary strategies with at least three relevant references that
  meet the engagement target; use at most two explicit close-fit exceptions.
  Prefer reserves for low-like workflow ideas. If this cannot be supported,
  report a quality gap instead of claiming production-complete recommendations.

`curation validate` checks the creator mix, context explanations, metric units,
and report/audit agreement. Its count floors remain necessary but are not
sufficient: explain selection tradeoffs and evidence limits in the delivered
report as well as the audit.
