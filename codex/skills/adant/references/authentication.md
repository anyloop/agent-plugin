# Authentication preflight

On the first AdAnt interaction in this conversation, present the First response
section of the [team welcome](welcome.md), including its image/text fallback.
This also applies when the user invokes a specialist directly. Then continue
this preflight once; do not recursively restart it. Preserve the requested
specialist scope and use the URL kickoff only for a new, otherwise unspecified
product task. Reconnects do not repeat onboarding.

Run this once at the start of each requested workflow, before product/competitor
research, seed reads, discovery, analysis, generation, or uploads. Read-only
diagnostics may precede it. Reuse a successful
check within that workflow. If authentication later fails, suspend new requests
and use the same recovery below, preserving work already submitted.

## Remote AdAnt connection

1. Discover the remote tools through the host's tool search when available.
   Call `adant_get_credit_balance` as a read-only authentication probe. A zero
   balance still proves authentication; it is not an authentication failure.
   Report the returned available credits. Before requested paid work, explain
   that it consumes AdAnt credits and continue without asking for a numeric
   budget or exact-cost approval. Respect any user-supplied limits.
2. If the probe fails or cannot be called, inspect current MCP startup status
   or connection logs when available; errors predating a successful login are
   not evidence of a new failure. An OAuth-required status,
   `reauthenticationRequired`, `invalid_grant`, or an unauthenticated challenge
   starts **connection recovery in this task**, not an immediate final error.
   Missing tools alone do not prove an authentication failure; use the error
   table below for other failures. Do not start research, spend credits, or
   substitute browser discovery while remote authentication is unverified.
3. After a successful probe, check the remote tools required by the selected
   workflow. Durable agent work uses `adant_agent_start`, `adant_list_agent_tasks`
   and the matching creative get/send/respond/stop tools. Check `adant_get_capabilities` for the supported
   roles, agent keys, project types and account availability; no local server
   is required.
   A missing tool is a capability gap on an authenticated connection, not an
   expired login or supplier outage. Return early with that exact gap; do not
   substitute a local/browser workflow or request social-account login.

## Connection recovery in the current task

The user's AdAnt task includes initiating the existing connection's sign-in.
Explain that you are opening AdAnt authorization and will resume after it
succeeds. Use the host's normal permission controls; the user completes browser
sign-in and consent. Never ask for passwords, tokens, or provider API keys.

1. Retain the original product URL, requested scope/counts and completed work.
   Retain the durable `projectId`; for primitive research also retain
   `researchId`, `operationId` values, idempotency keys,
   and the exact arguments of submitted operations before starting recovery.
2. Prefer an exposed host OAuth/reconnect control for the existing AdAnt server.
   If it is unavailable, use the installed host CLI from the task's terminal:
   - Codex desktop or CLI: check `command -v codex`; if the Codex CLI is installed, run `codex mcp login adant`.
   - Claude Code: check `command -v claude`; run `claude mcp login plugin:adant:adant`
     in a PTY, or use the packaged `adant-claude-setup` login helper.
   These host login commands are allowed during preflight even though research
   itself uses only remote MCP tools. Do not install a CLI, create a duplicate
   MCP server, edit credential stores, or use local bootstrap to replace OAuth.
3. Keep the login process/session alive while the user authorizes. Open or
   present its actual authorization URL; if an embedded browser cannot finish,
   use the same URL in a regular browser while the listener remains running.
   Wait in bounded intervals of at most 45 seconds and update the user at least
   once a minute. A yielded tool call is still running, not a failed login.
   Do not tell the user to retry research while this login is pending.
4. Wait for the host's completion event or the CLI's successful exit. Then use
   an exposed MCP reload/reconnect control once, if needed, and rediscover the
   remote tools. Call `adant_get_credit_balance` again and check the required
   workflow tools. A successful login is not proof that this task's tools have
   refreshed. If the probe still rejects after recovery, report that error
   without automatically starting a second login. Never invent a reload tool
   or use private host interfaces.
5. When verification passes, continue the original request in this task without
   requiring another research prompt. Recover submitted jobs by their existing
   project or operation IDs before starting more work. Retry an uncertain submission only
   with its original idempotency key and identical arguments; do not duplicate
   paid work or allocate a new research ID just because authentication changed.

Attempt one login flow per authentication failure; reuse a pending flow across
turns. If consent is declined, login times out/fails, or no permitted host login
surface is available, stop with the concrete reason and retain resume details.
Do not loop sign-in or change scopes to evade a permission/account denial.

If login succeeded but tools remain absent after rediscovery, report
**authorization succeeded; tool refresh is pending**, not another login failure.
In Codex desktop, reconnect AdAnt in plugin settings when no reload control is
exposed to the agent. Request a new task only when the host cannot refresh tools
in place, and provide a resume prompt with the original request and retained
IDs. Do not repeatedly ask for “continue,” reauthorize, or promise that another
message will refresh the tool catalog. Resume only after the remote probe and
required-tool checks pass.

## Accurate failure reporting and recovery

Name the failed surface and quote the concise error, without tokens. Separate
what was observed from an unverified cause. State that work has not started
(or where it stopped) and preserve existing artifacts for resumption.

| Evidence | Tell the user and next step |
| --- | --- |
| Remote status says OAuth required, `reauthenticationRequired`, or refresh rejected with `invalid_grant` | Initiate the current-task connection recovery above, wait for consent, recheck the remote connection, and resume the original work. |
| `invalid_grant: session not found` | AdAnt rejected the stored OAuth refresh token because its record could not be found. Do not claim the social account expired or invent why the record disappeared. |
| Tool absent and connection status unavailable | Required remote AdAnt tools are unavailable; the cause is unverified. Ask the user to check AdAnt's MCP connection status in the host. Do not prescribe social login or a reinstall as a proven fix. |
| Timeout, TLS, DNS, or HTTP 5xx | Report the connection/service error. Do not label it an authentication failure or request sign-in without authentication evidence. |
| HTTP 403 / scope or account denial | Report the returned permission/account reason and remedy; do not automatically say the token expired. |
| Collector reports supplier/platform gaps or zero results | Authentication has already succeeded. Report exactly the returned gap or zero results; neither establishes a social login requirement. |

Supplier collection uses AdAnt's server credentials and needs no TikTok or
Instagram account from the user. Reinstalling plugin files does not renew an
OAuth grant. A successful preflight is not a completed research report.
