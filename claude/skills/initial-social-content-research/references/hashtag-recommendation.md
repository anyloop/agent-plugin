# Hashtag recommendation

The research already found the three things a post's hashtags come from —
the competitors, the niche's keywords, and the brand's own name — so the run
recommends the hashtag sets as part of the deliverable rather than leaving
the user to guess them at posting time.

## Order of evidence

1. **Competitors first.** The `competitors` artifact's direct-tier names (then
   partial overlap) become competitor tags; the keyword research's
   `competitor` category adds the ones with a platform presence. A competitor
   tag carries the audience already shopping the category, so it belongs on a
   post that competes for that audience — a comparison, a switch story, a
   "better than" demo — and not on every post.
2. **Key niche-field keywords.** The keyword research's `niche` and `hook`
   categories and the profile's `keyword_seeds`, compacted to tags. The ones
   the relevant curated posts already carry rank first: the curation audit is
   mined for hashtags on candidates whose relevance test passed, so the
   recommendation is evidence, not invention.
3. **The brand's own tags.** The client name compacted (`#alinea`), and for
   an app its app form first (`#alineaapp`) because a plain common-word name
   drowns in the other meaning.
4. **One community tag at most** from the keyword research's `tiktok_native`
   list (`#fintok`, `#booktok`). Never a feed tag (`#fyp`, `#viral`,
   `#foryou`): those name the feed, not the subject.

## The sets

`research_run` phase `hashtags` takes the profile, the competitors, every
keyword artifact, and the curation audit, and writes `hashtags.json`:

- `pools` — `brand`, `competitor`, `niche`, `community`, `observed`, each tag
  in exactly one pool.
- `sets` — per platform, a `default` set (brand tag first, then niche tags,
  one competitor tag, one community tag) and a `competitor` set (brand, two
  competitor tags, then niche) for posts competing for a rival's audience.
  TikTok and Instagram sets hold at most five tags; YouTube Shorts three,
  because Shorts read the title and description rather than the tags.
- `rules` — the sentences to repeat to the user: at most five per post,
  always the brand tag, niche keywords carry the subject, a competitor tag
  only where it competes, never a feed tag.

## Into the report

Copy `hashtags.json` into `report_data.json` as its `hashtags` block (the
markdown preview renders it as "Recommended Hashtags"; the saved report keeps
it in the downloadable JSON), and give every strategy a `hashtags` array of at
most five: the platform's default set, or the competitor set when the
strategy's source video competes with a named rival. Read the sets before
writing them into a strategy — a compacted keyword can be wrong for the niche
(`#invest` where the audience says `#investing`), and the run's judgment
fixes it; the phase only ranks what the research found.
