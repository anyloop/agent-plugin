---
name: adant-getting-started
description: >-
  Orient a new AdAnt user in under five minutes: verify the AdAnt connection
  with one read-only call, surface the credit balance, check local research
  readiness, and offer three ready-to-send starting prompts personalized to
  the user's product. Trigger when the user asks what AdAnt can do, how to
  start or try it, whether setup or installation worked, says the plugin was
  just installed, or arrives with no concrete task.
---

# Getting started with AdAnt

Goal: from "just installed" to a first successful action in under five
minutes, with at most one question asked along the way.

## Verify the connection first

1. When the session exposes `adant_*` MCP tools, call
   `adant_get_credit_balance` — read-only, and it proves OAuth end to end.
   Otherwise run `npx --yes @anyloop/adant-cli credit balance`.
2. On success, report the balance in one line. On failure, follow the `adant`
   skill's **Recover a missing connection** steps for the current host; never
   guess at OAuth state or ask for API keys.

## Check research readiness only when relevant

When the user's interest includes trend, competitor, or content research — or
they have no stated goal yet — run the plugin doctor once:

```bash
python3 {PLUGIN_ROOT}/runtime/doctor.py --skip-sessions
```

`--skip-sessions` keeps it fast; platform sign-ins are handled later by the
research workflow itself. Fold any missing items into the same message as the
prompts below — one consolidated message, never a series of interruptions.
Skip the doctor entirely when the user only wants media generation; generation
needs no local tools.

## Offer three ways to start

Ask for the product website URL only if no product is known from context.
Then offer exactly three ready-to-send prompts, personalized to the product:

1. **Research** — "Research the short-form content landscape for `<product>`
   and build the research report."
2. **Create** — "Create a 15-second vertical product ad for `<product>` with
   AdAnt."
3. **Clone** — "Clone this reference ad for `<product>`: `<video URL>`."

Present them as copy-ready lines. Note once that generation spends AdAnt
credits and that the packaged skills confirm before credit-spending work.
Route the user's choice to `initial-social-content-research`,
`adant-create-ad`, or `adant-clone-ad`; keep the `adant` skill for one-off
media primitives.

## Keep it short

The entire orientation fits in one consolidated status-and-prompts message
plus at most one follow-up. Never dump the full skill catalog — three
personalized prompts beat seventeen skill names.
