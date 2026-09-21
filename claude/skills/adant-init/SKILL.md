---
name: adant-init
description: Verify the AdAnt remote connection and server research capabilities, then continue the requested work or offer three personalized starts.
---

# Initialize AdAnt

Use `$adant-init` to move from installation to useful work with at most one question.

## Verify the required surface

Follow the [authentication preflight](../adant/references/authentication.md):
call `adant_get_credit_balance` to verify remote authentication. If unavailable
or rejected, diagnose and return early with the observed error and matching
recovery instruction. Reinstalling plugin files does not repair OAuth.

For research, verify `adant_research_profile`, `adant_research_collect`,
`adant_research_seeds`, `adant_research_analyze`, `adant_research_status` and
`adant_research_save`. These run on AdAnt servers. Research requires no local
runtime, browser, local credential or progress panel. Missing local tools do
not block this workflow. Never work around a missing server with local research.

For explicitly requested local media, browser work or installation repair,
check the local surface separately. The remote `adant_*` tools and local
research tools are independent; `doctor` diagnoses only the latter.
When startup reports that it is missing, use the authorized
[runtime setup procedure](references/runtime-setup.md) to repair the local
prerequisite. Do not require that setup for server research.

When connection status says authorization is required, use the host's AdAnt
connection control. In Codex, `codex mcp login adant` is available when the CLI
is installed. In Claude Code, use `claude mcp login plugin:adant:adant`.
Never ask for credentials. If diagnostics are unavailable, say the cause is
unverified; never repeat restart advice after it has already failed.
Consolidate all missing prerequisites into one message.

## Continue the request or offer three starts

If a task or product URL with an intended workflow was supplied, continue it
in the same task after the relevant checks pass. Otherwise use the known
product, or ask once for its website, and offer:

1. Research its short-form content landscape and save a strategy report.
2. Create a 15-second vertical product ad with AdAnt.
3. Clone a supplied reference ad for the product.

Route to `initial-social-content-research`, `adant-create-ad`, or
`adant-clone-ad`. Mention once that generation spends credits and requires
confirmation; use the research skills' server workflow for research.
