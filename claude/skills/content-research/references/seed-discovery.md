# Seeds → queries → fresh, relevant, new candidates

A seed is anything the user hands the run as "more like this": example video
links, creator handles or profile links, keywords, or a saved report (its
Studio URL or id). Seeds shape the search and are excluded from the result.
The strategist scope ("New social ideas:") always follows this procedure; the
full research workflow follows it whenever a brief carries seeds.

## 1. Read every seed before writing a query

Never build queries from a URL's shape or from what a caption "probably"
says. Read the seed:

- **Video links or creator profile URLs** — call `adant_research_seeds` with
  this run's `researchId`, a stable `idempotency_key`, and up to eight URLs.
  For a creator use their public profile URL with `recent: 12`. Wait for the
  operation using `adant_research_status`; its `seeds` carry each video's
  caption, hashtags, author, dates and counts without downloading video.
  Inspect every seed. Analyze at most two ambiguous seed videos through
  `adant_research_analyze` when their metadata names no subject. A failed
  metadata read is a gap: use supplied captions or request usable video links;
  never guess the subject or request a desktop login. Creator handles alone
  are not search keywords.
- **Saved report (URL or id)** — call `adant_get_product_report`. Its `product`,
  `findings`, `formats`, strategy titles, `whyThisVideo`, `keep`/`change`
  notes and every cited video's `handle` and `format` are the seed
  vocabulary; its `videoUrls` join the exclusion list (step 4). It is free.
- **Keywords in the brief** — used as given, plus their platform-native
  variants.

Keep a seed inventory: per seed, its subject (what the video is
about, in five words), the audience or pain it speaks to, its format (talking
head, POV skit, tutorial, before/after, listicle, unboxing, green-screen
react…), hook mechanism, hashtags, author, posted date, and the platform it
performed on.

## 2. Build the queries from what the seeds say

Per platform, up to eight short queries, in this priority order:

1. **Subject queries** — the seed's subject in the words its caption uses,
   plus its two or three most specific hashtags as plain words (`#cgmlife` →
   `cgm life`, `#glucosemonitor` → `glucose monitor`). A feed tag or platform
   name is never a query.
2. **Audience-problem queries** — the pain or decision the seed addresses,
   phrased the way a viewer types it (`is a cgm worth it`, `blood sugar
   spikes after coffee`), naming the category as an app or device when it is
   one (`glucose tracker app`).
3. **Format-in-category queries** — the seed's format applied to the
   category (`cgm what i eat in a day`, `glucose monitor day 1 vs day 30`),
   so the collection surfaces the same mechanism on a new subject.
4. **Creator-niche queries** — the recurring subjects of a seed creator's
   recent videos, when the seed is a profile.
5. **Brief keywords** — the user's own words, last, so they never crowd out
   what the seeds proved.

Keep a query to two to five words, in the language of the seeds' captions.
Record the plan in the query plan with, per query, which seed(s) it came from,
so the report's gaps can say which seeds produced nothing.

Prior-report seeds: turn each strategy's `format` plus the product into one
format-in-category query, each finding into one audience-problem query, and
read the platform sections' `format` labels for the report's own vocabulary
(`VIBE CODING MEME` → `vibe coding meme`). The point is videos the report did
not already show, so its cited videos are excluded, not re-found.

## 3. Collect fresh content, and say how fresh

The strategist scope wants what is working now, so it collects with a window:

- `postedWithinDays: 60` (or the days the user named, at least 30) may go on
  one `adant_research_collect` call covering every platform. It is applied natively
  on TikTok and Instagram and re-verified against each post's date.
- YouTube and Meta Ads cannot apply it — the Shorts search returns no publish
  date and an ad's start date is not a post date — so they collect without it
  and say so on their own `degraded` note. They are no longer turned into
  gaps for asking (ADA-36). Rank them by metric and by any date the result
  carries, and label their freshness "unverified" in the report rather than
  calling them recent.
- Split the window off into its own TikTok + Instagram call only when the run
  genuinely depends on proven recency, since only those two can prove it.
- `sort: "relevance"` first. A second, smaller call with `sort:
  "most-liked"` on TikTok only when the relevance pass returned strong
  subject matches but few outliers — never as the first pass, because it
  surfaces old evergreen hits.

A candidate whose `postedAt` is older than the window is not a primary. It
may be a reserve, labelled evergreen with its date, when nothing fresher
carries the same mechanism. A candidate with no date is "date unknown", not
"recent".

## 4. Exclude what the user already has

Before curation, keep an exclusion list:

- every seed video URL, and every video listed for a seed creator;
- every URL in `adant_get_product_report`'s `videoUrls`, for each prior report;
- URLs the user says were already used or rejected.

Match by platform id, not by string: TikTok `/video/<id>`, Instagram
`/reel/<code>/` or `/p/<code>/`, YouTube `/shorts/<id>` or `v=<id>` — `www.`,
`vm.tiktok.com` redirects, query strings and trailing slashes all vary. Drop
the matches from the candidates, note the count in the report's evidence notes
("excluded 9 already-seen videos"), and never let an excluded video back in
as a reserve. A supplier outage does not lift the exclusion: when nothing new
was found, the brief is partial and says so.

## 5. Judge relevance before engagement

An outlier label means the post performed, not that it is about the seeds'
subject. Before analyzing, score each remaining candidate against the seeds
from its caption, hashtags, author and, once analyzed, the video itself:

| Score | Meaning |
| --- | --- |
| 3 | Same subject or product category, and same audience or pain |
| 2 | Same subject, or same pain with the category clearly present |
| 1 | Same format or creator niche only; the subject differs |
| 0 | Unrelated, however viral |

Only 2s and 3s are analyzed and can be primaries; a 1 is at most a reserve,
and only when the brief asked for that format; a 0 is dropped whatever its
numbers. Within the qualified set prefer stronger measured engagement, then
audience fit, replicable format, creator variety (at most two candidates per
creator), then recency. Record score and reason per candidate in
`curation.json`. The brief's intro states how many candidates were judged,
how many qualified, and why the strongest rejected ones were rejected.
