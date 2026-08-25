---
name: adant
description: Use AdAnt from an AI agent to inspect credits, discover media models, generate image/video/voice assets, inspect or cancel media jobs, edit or analyze local media, or start an AdAnt creative workflow. Prefer the authenticated AdAnt Remote MCP when its adant_* tools are available; use adant-cli for local files or as a fallback. Trigger when the user mentions AdAnt, asks to use AdAnt tools, wants AI ad media, or provides a local asset for AdAnt processing.
---

# AdAnt

Use AdAnt's user-authorized Remote MCP and CLI. Never bypass these interfaces
or ask the user for third-party media service credentials.

## Route task-shaped workflows

When installed, use `adant-getting-started` when the user is new, asks what
AdAnt can do, or wants to verify that setup worked; use `adant-create-ad` for
a complete ad workflow and
`adant-clone-ad` for a reference-driven clone or adaptation. Those skills own
durable project setup, grounding, budgets, approvals, reconnects, and delivery.
Keep this `adant` skill for one-off media primitives, local editing/analysis,
job management, and adapter fallback.

## Choose the adapter

1. Use the Remote MCP when the session exposes `adant_*` tools and the request
   is supported there. It provides OAuth-scoped identity, structured results,
   durable idempotency, and an inline media preview where the host supports MCP
   Apps.
2. Use `adant-cli` when the request includes a local file, needs image editing
   or video analysis, or no AdAnt MCP tools are connected.
3. If neither surface is available, identify the current host before giving
   setup instructions. Do not improvise a generation call with unrelated tools.

## Recover a missing connection

Do not treat missing `adant_*` tools by itself as proof that OAuth failed.

- If AdAnt was installed or updated after the current task started, ask the
  user to start a new task first. Diagnose the connection only if a fresh task
  still lacks the tools.
- In ChatGPT desktop or the Codex app, keep connection repair inside the app.
  Ask the user to open **Plugins**, open AdAnt under **Installed** or
  **Personal**, and complete the connection or authorization prompt. Then
  start another new task. Never tell a desktop-only user to run `codex` in
  their system terminal.
- Use `codex mcp login adant` only for Codex CLI, or after verifying that the
  `codex` executable is available in the user's terminal.
- For Claude Code, use `claude mcp login plugin:adant:adant`.
- If no MCP host is available and the request can use the CLI adapter, run
  `npx @anyloop/adant-cli auth login` instead.

If an embedded OAuth browser times out, keep the login flow open and have the
user copy the AdAnt authorization-page address into Chrome or Safari. Opening
the page is not evidence of authentication: claim success only after a real
read-only AdAnt MCP or CLI call succeeds.

## Remote MCP workflow

Use only tools actually exposed by the connected AdAnt server:

- `adant_get_credit_balance`
- `adant_get_capabilities`
- `adant_list_media_models`
- `adant_get_media_model`
- `adant_generate_image`
- `adant_generate_video`
- `adant_generate_voice`
- `adant_get_media_job`
- `adant_cancel_media_job`
- `adant_creative_start`
- `adant_creative_get`
- `adant_creative_send`
- `adant_creative_respond`
- `adant_creative_stop`
- `adant_list_products`, `adant_get_product`, `adant_create_product`
- `adant_list_avatars`, `adant_get_avatar`
- `adant_list_templates`, `adant_get_template`
- `adant_prepare_upload`, `adant_complete_upload`

Before generation:

1. Call `adant_get_capabilities` when availability is uncertain.
2. Discover models with `adant_list_media_models`; call
   `adant_get_media_model` before using model-specific controls.
3. State the intended model, major controls, and indicative credit cost. Get
   explicit confirmation before submitting credit-spending generation.
4. Generate a caller-owned idempotency key for the user action. Reuse that key
   only when retrying the exact same arguments; use a new key after any input
   change.

Generation returns a durable job. Report its job id. When an MCP App preview is
present, do not keep the model turn alive by repeatedly polling; let the card
update. Without a preview, offer one explicit status check later. Cancel only
after an explicit user request because generation may already have consumed
credits.

Creative-project App cards can resolve visible questions, pickers, reviews,
and generation approvals directly. Treat those card actions as authoritative;
the card publishes the current interaction and recent decisions back into
model context. In hosts without App controls, keep using the native
conversation and resolve only the exact interaction id returned by the tool.

Model discovery reports an indicative sample cost, not an exact customized
quote. Label it accordingly; do not manufacture a precise price for duration,
resolution, or count controls that the tool has not quoted.

A conditional cancellation such as "if it takes too long" needs an explicit
deadline. Ask for that threshold rather than inventing one, and reconfirm before
canceling if the deadline is reached.

Remote MCP supports durable creative sessions, owner-scoped library reads,
verified uploads, and direct text-to-image/video/voice. Local media editing and
analysis remain CLI workflows.

## CLI workflow

Prefer `npx @anyloop/adant-cli` so the user does not need a global installation. If a
command reports that authentication is missing, run:

```bash
npx @anyloop/adant-cli auth login
```

Useful discovery and accounting commands:

```bash
npx @anyloop/adant-cli credit balance
npx @anyloop/adant-cli media model list --json
```

Generate media:

```bash
npx @anyloop/adant-cli media image generate --prompt "..." --model gpt-image-2 -o output.png
npx @anyloop/adant-cli media video generate --prompt "..." --model seedance-2.0 --download -o output.mp4
npx @anyloop/adant-cli media audio generate --text "..." -o output.mp3
```

Local-file and analysis workflows belong on the CLI:

```bash
npx @anyloop/adant-cli media image edit --image ./input.png --prompt "..." -o edited.png
npx @anyloop/adant-cli media analyze --video ./input.mp4 --prompt "..." --json -o analysis.json
npx @anyloop/adant-cli media clone-analysis --video ./input.mp4 -o analysis/
```

Inspect a durable job. Use `--wait` inside one CLI invocation instead of
repeatedly launching the CLI in an agent loop:

```bash
npx @anyloop/adant-cli media job get JOB_ID --session-id SESSION_ID
npx @anyloop/adant-cli media job get JOB_ID --session-id SESSION_ID --wait --timeout 900 -o output.mp4
```

Before a credit-spending CLI command, show the command and get confirmation.
After it runs, preserve the returned job and session identifiers and report the
output path or terminal error. Never claim completion merely because a job was
accepted.

## End-to-end creative requests

For a complete ad, route to `adant-create-ad`; for reference cloning, route to
`adant-clone-ad`. If those task skills are unavailable but the connected MCP
exposes creative tools, follow their durable project contract: start once,
preserve the project id, read progress later, and resolve only the exact current
interaction with explicit generation approval.

Creative MCP commands return before project work finishes. Do not repeatedly
poll a running project in the same model turn. A client disconnect does not
cancel it, and stopping its active agent turn does not imply that a submitted
media job was canceled.

When the user explicitly wants a terminal-driven creative session, use the
CLI's `session` commands and inspect `npx @anyloop/adant-cli session --help` first so the
available workflow catalog drives the command.

## Result contract

Finish with:

- adapter used (`Remote MCP`, `adant-cli`, or `Studio handoff`);
- model or workflow selected;
- credit confirmation obtained, when applicable;
- durable job/session id, when one has actually been created;
- current terminal state and artifact/output location;
- the next action if work is still running or blocked.
