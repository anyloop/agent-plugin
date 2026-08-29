---
name: adant-init
description: First-run initialization for AdAnt. Verify the remote connection, open the live progress panel, check local research readiness, and offer three personalized starting prompts. Trigger on "$adant-init", setup, installation checks, or requests for how to start.
---

# Initialize AdAnt

Move from installation to a useful first action with at most one question.

## Verify both MCP surfaces

1. If `research_progress_open` exists, call it **before** running checks and say briefly
   that it shows live research progress.
2. Call `adant_get_credit_balance` to prove the remote OAuth connection.
3. Call `doctor(sessions=false)` once when research is relevant.

The remote `adant_*` tools and local research tools are independent. If neither
is present, say: “Quit and reopen the desktop app, then start a new task.” If only
one is absent, report that partial state; never work around a missing server or
ask for provider/API secrets. Reinstalling plugin files does not repair a stored
OAuth connection.

If `doctor` reports local authentication missing, call
`device_identity`, pass its two returned fields to
`adant_mint_local_token(scopes=["research"], device_id=..., device_name=...)`,
and pass the minted token directly to `auth_bootstrap`. Never print or repeat
the token.

Consolidate all missing prerequisites into one message.

## Offer exactly three starts

Use the known product, or ask once for its website. Then offer these personalized,
copy-ready prompts:

1. Research its short-form content landscape and build a report.
2. Create a 15-second vertical product ad with AdAnt.
3. Clone a supplied reference ad for the product.

Mention once that generation spends credits and requires confirmation. Route to
`initial-social-content-research`, `adant-create-ad`, or `adant-clone-ad`.
