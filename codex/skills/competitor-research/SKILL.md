---
name: competitor-research
description: Three-phase competitive intelligence — Phase 1 identifies true competitors via capability cluster analysis with Google Search grounding. Phase 2 researches each competitor's TikTok presence (handles, followers, content strategy, viral videos). Phase 3 generates a markdown competitor analysis report combining competitive intelligence with TikTok presence data. Distinguishes decision-layer vs tool-layer products.
---

# Competitor Research

Three-phase competitive intelligence tool:

1. **Phase 1 — Competitor Discovery**: Identify TRUE competitors using capability cluster analysis with Gemini Google Search grounding
2. **Phase 2 — TikTok Presence**: Research each competitor's TikTok account, followers, content strategy, and viral videos
3. **Phase 3 — Report Generation**: Generate a markdown competitor analysis report combining both data sets

## Why This Exists

Most competitor discovery is broken:
- **Keyword-based** finds companies with similar marketing, not similar products
- **Technology-based** confuses tool-layer with decision-layer products
- **No TikTok intelligence** — competitor reports ignore social presence entirely

This skill does proper competitive intelligence AND social presence analysis in one pipeline.

## Prerequisites

- `uv` (Python package manager)
- `GEMINI_API_KEY` environment variable set (in `.env` or shell)

## Quick Start

```bash
# Full pipeline: discover competitors + TikTok presence + report
uv run --project skills/competitor-research/runtime \
  skills/competitor-research/runtime/research_competitors.py \
  --client "Example Insights" \
  --description "AI-native market research platform with synthetic personas and behavioral simulation" \
  --website "https://example.com/" \
  --competitors "Competitor One,Competitor Two,Competitor Three,Competitor Four,Competitor Five" \
  --tiktok-presence \
  --report \
  -o competitors.json

# Phase 1 only (just competitor discovery)
uv run --project skills/competitor-research/runtime \
  skills/competitor-research/runtime/research_competitors.py \
  --client "Example Insights" \
  --description "AI-native market research platform" \
  -o competitors.json

# Phase 1 + 2 (competitor discovery + TikTok, no report)
uv run --project skills/competitor-research/runtime \
  skills/competitor-research/runtime/research_competitors.py \
  --client "Example Insights" \
  --description "AI-native market research platform" \
  --competitors "Competitor One,Competitor Two" \
  --tiktok-presence \
  -o competitors.json
```

## Options

| Flag | Description | Required |
|------|-------------|----------|
| `--client` | Client/brand name | Yes |
| `--description` | Product/service description | Yes |
| `--website` | Client website URL (fetched for context) | No |
| `--competitors` | Comma-separated known competitors (will be searched and verified) | No |
| `--max-competitors` | Max competitors to find (default: 15) | No |
| `--tiktok-presence` | Phase 2: Research TikTok presence for all competitors | No |
| `--report` | Phase 3: Generate markdown competitor analysis report | No |
| `--report-output` | Output path for markdown report (default: `competitor_report.md`) | No |
| `--tiktok-output` | Output path for TikTok presence JSON (default: `competitors_tiktok_presence.json`) | No |
| `-o, --output` | Save main competitor research JSON to file | No (stdout) |

## Phase 1: Competitor Discovery

Uses Gemini with Google Search grounding for web-verified competitive intelligence.

### Capability Cluster Analysis

Breaks the client's product into capability clusters, then finds competitors per cluster:
- **Tier 1 — Direct Competitors**: Compete across MULTIPLE of the same clusters
- **Tier 2 — Partial Overlap**: Strong in 1-2 of the same clusters
- **Tier 3 — Behavioral Substitutes**: What customers actually do instead

### Key Distinctions
- **Decision-Layer vs Tool-Layer**: Voice synthesis ≠ research platform
- **Same Problem, Same Customer**: Only companies a buyer would realistically evaluate
- **Exclusion reasoning**: Explains why commonly confused companies are NOT competitors

## Phase 2: TikTok Presence Research (`--tiktok-presence`)

For each competitor discovered in Phase 1, uses Google Search to find:
- Official TikTok handle (tries multiple patterns: @company, @company.ai, @companyai, etc.)
- Follower count, total likes, video count
- Bio text and link in bio
- Whether the account is the real company or an unrelated user
- Notable/viral videos with URLs and view counts
- Content strategy observations
- Presence level classification (strong/medium/weak/minimal/none)

Also researches the CLIENT's own TikTok presence for comparison.

### Presence Levels
- **Strong**: 1000+ followers, regular posting, engagement > followers
- **Medium**: 500+ followers or notable engagement on some videos
- **Weak**: Account exists with content but very low engagement
- **Minimal**: Account exists with 0-2 videos or <10 followers
- **None**: No account found or account is clearly unrelated

## Phase 3: Report Generation (`--report`)

Generates a markdown report combining Phase 1 + Phase 2 data:

1. **Executive Summary** — Category, competitor count, TikTok landscape, strategic takeaway
2. **Client Capability Clusters** — Table of what the client does
3. **True Competitors** — Detailed per-tier competitor profiles
4. **Not Competitors (Excluded)** — What was excluded and why
5. **Competitor TikTok Presence** — Ranked table with handles, followers, likes, videos
6. **Deep Dive: Strongest Competitor** — Viral videos, content strategy, exploitable gaps
7. **TikTok Landscape Summary** — Market maturity, whitespace opportunity
8. **Competitive Landscape Summary** — Overall strategic assessment

## Output Files

| File | Phase | Content |
|------|-------|---------|
| `competitors.json` (`-o`) | 1+2 | Full competitor research data with TikTok presence merged |
| `competitors_tiktok_presence.json` | 2 | TikTok presence data only (handles, followers, presence levels) |
| `competitor_report.md` | 3 | Formatted markdown report |

## Integration with TikTok Research Notebook

This skill runs as **Steps 1-2** in the TikTok research pipeline:

1. **Competitor Discovery + TikTok Presence** (this skill, all 3 phases) → `competitors.json` + `competitors_tiktok_presence.json` + `competitor_report.md`
2. **Human Review** → User reviews, adds/removes competitors
3. **Confirmed Competitors** → `competitors_confirmed.json`
4. **Keyword Research** → Uses confirmed competitor names
5. **TikTok Browsing** → Searches for competitor brands on TikTok
6. **Final Report** → Uses competitor data for accurate competitive landscape section

## Example: capability-cluster analysis

Without capability clusters, a report may confuse adjacent tools with true competitors. With this skill:

| Capability | True Competitor | NOT a Competitor |
|---|---|---|
| Persona simulation | Competitor One, Competitor Two | Voice-only tool |
| AI interviews | Competitor One, Competitor Three | Avatar-only tool |
| Synthetic panels | Competitor Two, Competitor Four | Survey-only tool |

TikTok presence analysis can then reveal whether any true competitor has meaningful traction and where the category still has whitespace.
