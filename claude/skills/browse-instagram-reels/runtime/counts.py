#!/usr/bin/env python3
"""The one place this skill turns a rendered count into a number.

Both sites write a count and its noun into a single node — "12.3K likes",
"1.2M views" — and both abbreviate above a thousand. A parser that matches the
whole string misses those and falls back to `parseInt`, which answers 12 and 1:
plausible numbers, three and six orders of magnitude wrong, that travel all the
way into a delivered report without ever looking like an error. So the rule
here is: read the count at the START of the text, keep its multiplier, and
ignore whatever follows. Text that does not begin with a number is not a count.
"""

import re

COUNT_RE = re.compile(r"^\s*([\d,]+(?:\.\d+)?)\s*([KMB])?\b", re.IGNORECASE)
MULTIPLIER = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}

# The same rule in the browser, injected into every extraction snippet so the
# page-side and recovery-side parsers cannot drift apart.
JS_PARSE_COUNT = r"""  function parseCount(s) {
    if (!s) return null;
    var m = s.toString().trim().replace(/,/g, '').match(/^(\d+(?:\.\d+)?)\s*([KMB])?\b/i);
    if (!m) return null;
    var n = parseFloat(m[1]);
    var u = (m[2] || '').toUpperCase();
    if (u === 'K') return Math.round(n * 1000);
    if (u === 'M') return Math.round(n * 1000000);
    if (u === 'B') return Math.round(n * 1000000000);
    return Math.round(n);
  }
"""

# Which count a node is naming, read from the SAME node as the number.
JS_COUNT_NOUN = r"""  function countNoun(text) {
    var t = (text || '').toString().toLowerCase();
    var hits = [];
    if (t.indexOf('like') !== -1) hits.push('like_count');
    if (t.indexOf('comment') !== -1) hits.push('comment_count');
    if (t.indexOf('view') !== -1 || t.indexOf('play') !== -1) hits.push('view_count');
    // Two nouns in one string name a row, not a figure — it identifies nothing.
    return hits.length === 1 ? hits[0] : null;
  }
"""


def parse_count(text) -> int | None:
    """'12.3K' / '12.3K likes' / '1,234 views' -> int; anything else -> None."""
    m = COUNT_RE.match(str(text or ""))
    if not m:
        return None
    try:
        n = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    return round(n * MULTIPLIER[(m.group(2) or "").upper()])
