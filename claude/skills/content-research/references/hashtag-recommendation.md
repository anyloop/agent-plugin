# Hashtag recommendation

The research already found what a post's hashtags come from — the
competitors, the niche's keywords, and the brand's own name — so the report
recommends the hashtag sets rather than leaving the user to guess them when
they post. The social manager reads the block through `retrieve_strategy` and
writes every caption from it.

## Order of evidence

1. **Competitors first.** The direct competitors the profile step settled on
   (never the adjacent products) become competitor tags. A competitor tag
   carries the audience already shopping the category, so it belongs on a post
   that competes for that audience — a comparison, a switch story, a "better
   than" demo — not on every post.
2. **Key niche-field keywords.** The problem, the goal, and the product
   category as the audience says them, compacted to tags (`build credit
   fast` → `#buildcreditfast`; drop stop words like "how", "to", "best",
   "app"). The tags the collected outliers already carry rank first: read the
   captions (`text`) of the candidates you judged relevant, take their
   hashtags, and count them — a tag on three relevant winners is evidence, a
   tag you invented is a guess.
3. **The brand's own tag(s).** The client name compacted (`#alinea`), and for
   an app its app form first (`#alineaapp`), because a plain common-word name
   drowns in the other meaning.
4. **One community tag at most** — the niche's identity tag (`#fintok`,
   `#booktok`) when the collected winners use one. Never a feed tag (`#fyp`,
   `#viral`, `#foryou`, `#trending`): they name the feed, not the subject.

## The block

Write it into `report_data.json` as `hashtags`:

```json
{
  "max_per_post": 5,
  "pools": {
    "brand": ["#alineaapp", "#alinea"],
    "competitor": ["#robinhood", "#acorns"],
    "niche": ["#investing", "#buildwealth", "#investingforbeginners"],
    "community": ["#fintok"],
    "observed": ["#investing", "#wealth", "#alineaapp"]
  },
  "sets": {
    "tiktok": {
      "default": ["#alineaapp", "#investing", "#buildwealth", "#robinhood", "#fintok"],
      "competitor": ["#alineaapp", "#robinhood", "#acorns", "#investing", "#fintok"]
    },
    "instagram": { "default": ["…"], "competitor": ["…"] },
    "youtube": { "default": ["#alineaapp", "#investing", "#robinhood"], "competitor": ["…"] }
  }
}
```

- Each tag lives in exactly one pool (brand wins, then competitor).
- A `default` set is the brand tag first, then niche tags, one competitor
  tag, one community tag — at most five on TikTok and Instagram, three on
  YouTube Shorts, which read the title and description rather than the tags.
- A `competitor` set is the brand tag, two competitor tags, then niche, for a
  post competing for a rival's audience.
- Give every strategy a `hashtags` array: the platform's default set, or the
  competitor set when the strategy's source video competes with a named
  rival. Read the set before writing it — a compacted keyword can be wrong
  for the niche (`#invest` where the audience says `#investing`).

State the rules in the report's strategy intro in one sentence: at most five
per post, the brand tag always, niche keywords carry the subject, a competitor
tag only where the post competes, never a feed tag.
