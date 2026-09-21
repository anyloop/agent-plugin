# Authentication preflight

Run this once at the start of each requested workflow, before product/competitor
research, seed reads, discovery, analysis, generation, or uploads. Opening the
progress panel and read-only diagnostics may precede it. Reuse a successful
check within that workflow; stop immediately if authentication later fails.
Local-only report rendering needs no AdAnt authentication. Check before saving
it to Studio or starting any authenticated operation.

## Remote AdAnt connection

1. Discover the remote tools through the host's tool search when available.
   Call `adant_get_credit_balance` as a read-only authentication probe. A zero
   balance still proves authentication; it is not an authentication failure.
2. If the probe fails or cannot be called, inspect the host's MCP startup status
   or connection logs when available. **Return early** with the observed error
   and the matching recovery instruction below. Do not start local research,
   spend credits, or substitute browser discovery while remote authentication
   is failed or unverified. A working `adant-local` server or stored local token
   does not establish that the remote `adant` MCP is authenticated.
3. After a successful probe, check the remote tools required by the selected
   workflow. Social research uses `adant_research_profile`,
   `adant_research_collect`, `adant_research_analyze`, `adant_research_seeds`,
   `adant_research_status` and `adant_research_save`; it needs no local server.
   A missing tool is a capability gap on an authenticated connection, not an
   expired login or supplier outage. Return early with that exact gap; do not
   substitute a local/browser workflow or request social-account login.

## Local credential, when local authenticated phases are needed

Call `doctor(sessions=false)`. Its `adant-auth` check verifies only the local
credential; its overall `ok` never proves remote OAuth. If the credential is
missing or rejected, use the already authenticated remote
`adant_mint_local_token`, passing both `device` fields and the minimum required
scopes (`research`, `media`, and/or `report`), then `auth_bootstrap` without
displaying the token. Continue only when verification succeeds. If minting,
bootstrap, or verification fails, return early with that error and recovery;
do not run phases with an unverified credential. A network failure does not
prove that a token is invalid. Scope or account denials require their stated
remedy, not repeated sign-in. Never ask the user to paste credentials.

## Accurate failure reporting and recovery

Name the failed surface and quote the concise error, without tokens. Separate
what was observed from an unverified cause. State that work has not started
(or where it stopped) and preserve existing artifacts for resumption.

| Evidence | Tell the user and next step |
| --- | --- |
| Remote status says OAuth required, `reauthenticationRequired`, or refresh rejected with `invalid_grant` | The **AdAnt connection** needs authorization. In Codex desktop, reconnect AdAnt in plugin settings; if the Codex CLI is installed, run `codex mcp login adant`. In Claude Code, run `claude mcp login plugin:adant:adant` (or the packaged `adant-claude-setup` login helper). Then retry the same request and rerun the probe. |
| `invalid_grant: session not found` | AdAnt rejected the stored OAuth refresh token because its record could not be found. Do not claim the social account expired or invent why the record disappeared. |
| Tool absent and connection status unavailable | Required remote AdAnt tools are unavailable; the cause is unverified. Ask the user to check AdAnt's MCP connection status in the host. Do not prescribe social login or a reinstall as a proven fix. |
| Timeout, TLS, DNS, or HTTP 5xx | Report the connection/service error. Do not label it an authentication failure or request sign-in without authentication evidence. |
| HTTP 403 / scope or account denial | Report the returned permission/account reason and remedy; do not automatically say the token expired. |
| Collector reports supplier/platform gaps or zero results | Authentication has already succeeded. Report exactly the returned gap or zero results; neither establishes a social login requirement. |

Supplier collection uses AdAnt's server credentials and needs no TikTok or
Instagram account from the user. Reinstalling plugin files does not renew an
OAuth grant. A successful preflight is not a completed research report.
