---
name: adant-init
description: First-run initialization for AdAnt. Verify the remote connection, open the live progress panel, check local research readiness, and offer three personalized starting prompts. Trigger on "$adant-init", setup, installation checks, or requests for how to start.
---

# Initialize AdAnt

Move from installation to a useful first action with at most one question.

## Verify both MCP surfaces

1. If `research_progress_open` exists, call it **before** running checks and say briefly
   that it shows live research progress.
2. If available, call `adant_get_credit_balance` to prove the remote OAuth connection.
3. Call `doctor(sessions=false)` once when available and research is relevant.

The remote `adant_*` tools and local research tools are independent. Missing
tools do not prove the plugin is uninstalled or that a restart will fix it.
Report which surface is unavailable; never work around a missing server or
ask for provider/API secrets. Reinstalling plugin files does not repair a stored
OAuth connection.

When tools are missing, check the host's MCP connection/startup status if
available. For installation troubleshooting, read-only inspection of host logs,
resolved server configuration, and prerequisite availability is appropriate;
do not run research or generation through a substitute shell workflow.

- Remote server: if status says not logged in, direct the user to AdAnt's
  connection prompt in the host's plugin settings. In Codex, when its CLI is
  installed, `codex mcp login adant` is also available. Browser authorization
  requires the user; never ask them to paste credentials or tokens.
- Local server: `uv` must be installed and discoverable by the launcher. If
  startup reports that it is missing, explain the prerequisite and use the
  [runtime setup procedure](references/runtime-setup.md) when setup or repair
  is authorized. It installs uv and prepares the locked environment before
  reconnecting. Do not recommend OAuth reconnect as a fix for a local crash.
- If logs show a different startup error, report that error and investigate it
  instead of assuming missing authentication or dependencies. If diagnostics
  are unavailable, state that the cause is unverified.
- After a prerequisite fix, use the host's MCP reconnect/restart control if
  available and re-check tools. Only suggest a fresh task after installation,
  update, or a prerequisite fix when tools remain unavailable.
  A desktop restart may refresh stale state, but never repeat restart advice
  after the user has already tried it without success.

If `doctor` reports local authentication missing, pass the two fields of its
`device` to
`adant_mint_local_token(scopes=["research"], device_id=..., device_name=...)`,
and pass the minted token directly to `auth_bootstrap`. Never print or repeat
the token.

Consolidate all missing prerequisites into one message.

## Continue the request or offer three starts

If the user already supplied a task or product URL with an intended workflow,
continue that request after checks pass in the same task. Do not require another
init invocation or replace their request with a menu. Otherwise offer the three
starts below.

Use the known product, or ask once for its website. Then offer these personalized,
copy-ready prompts:

1. Research its short-form content landscape and build a report.
2. Create a 15-second vertical product ad with AdAnt.
3. Clone a supplied reference ad for the product.

Mention once that generation spends credits and requires confirmation. Route to
`initial-social-content-research`, `adant-create-ad`, or `adant-clone-ad`.
