---
name: competitor-research
description: Three-phase competitive intelligence — one bounded AdAnt web-research turn identifies true competitors, then local Chrome researches TikTok presence and a local renderer creates the Markdown report. This workflow keeps execution on the user's computer.
---

# Competitor Research

Three-phase competitive intelligence tool:

1. **Phase 1 — Competitor Discovery**: One bounded, research-only AdAnt web-research turn
2. **Phase 2 — TikTok Presence**: Browse TikTok in the user's local Chrome research profile
3. **Phase 3 — Report Generation**: Render the Markdown report deterministically on the user's computer

## Why This Exists

Most competitor discovery is broken:
- **Keyword-based** finds companies with similar marketing, not similar products
- **Technology-based** confuses tool-layer with decision-layer products
- **No TikTok intelligence** — competitor reports ignore social presence entirely

This skill does proper competitive intelligence AND social presence analysis in one pipeline.

## Prerequisites

- `uv` (Python package manager)
- Node.js/npm for the legacy authentication fallback (`npx @anyloop/adant-cli`)
- Google Chrome for optional local TikTok research
- AdAnt authentication (`npx @anyloop/adant-cli auth login` when needed)

Never request a Gemini or other upstream model key. The runtime uses one temporary,
authenticated AdAnt agent session. For this workflow, its request explicitly limits
the turn to web research and tells the agent not to invoke workspace, shell, computer,
artifact, media, or other execution tools. Other plugin workflows can continue to use
the full AdAnt agent when cloud execution is actually required.

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
| `--max-competitors` | Max competitors to find (default: 8) | No |
| `--tiktok-presence` | Phase 2: Browse TikTok locally for all competitors | No |
| `--tiktok-max-time` | Local TikTok capture time limit in seconds (default: 300) | No |
| `--report` | Phase 3: Render markdown report locally | No |
| `--report-output` | Output path for markdown report (default: `competitor_report.md`) | No |
| `--tiktok-output` | Output path for TikTok presence JSON (default: `competitors_tiktok_presence.json`) | No |
| `-o, --output` | Save main competitor research JSON to file | No (stdout) |

## Phase 1: Competitor Discovery

Uses one authenticated AdAnt agent turn for source-linked competitive intelligence.
The current workflow requests web research and model synthesis only; it does not ask
for cloud Computer or MCP execution. Website fetching and every file-producing step
remain local.

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

For each competitor discovered in Phase 1, the packaged TikTok Chrome/CDP runtime
runs on the user's computer to find:
- Official TikTok handle (tries multiple patterns: @company, @company.ai, @companyai, etc.)
- Follower count, total likes, video count
- Bio text and link in bio
- A deterministic brand-name/domain match, with a note to verify identity-critical results
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

Renders a markdown report locally from Phase 1 + Phase 2 data. This phase does
not call a model, CLI, API, or cloud computer:

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
