---
name: adant-claude-setup
description: >-
  Connect, verify, or repair the AdAnt plugin in Claude Code. Use when AdAnt
  tools need authentication, the plugin MCP server reports disconnected or
  insufficient scope, or the user asks how to install, update, reconnect, or
  verify AdAnt in Claude Code.
---

# AdAnt Claude Setup

Use the plugin-managed MCP server named `plugin:adant:adant`. Do not configure a
second AdAnt MCP server or ask the user for an API key.

Before continuing a product task after setup, follow the shared
[authentication preflight](../adant/references/authentication.md), including its
connection recovery before reporting an authentication blocker.

## Verify

If the AdAnt tools are available, follow the [team
welcome](../adant/references/welcome.md) and stop there unless the user asked for
more. Otherwise say “Connecting AdAnt…”, with no team roster yet, and continue
setup once without recursive preflight.
Retain any supplied product URL and continue its kickoff after verification
and the existing credit checks.

Run:

```bash
claude plugin list
claude mcp get plugin:adant:adant
```

If the plugin is missing, follow `docs/claude-code-install.md` in the public
repository. If it is installed but disconnected, continue with login.

## Login or reconnect

Run the PTY-compatible helper so Claude Code can complete browser OAuth:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/skills/adant-claude-setup/scripts/login-adant.sh"
```

For an `insufficient_scope` response, run the same helper again to grant the
current AdAnt permissions. Never request, print, or store OAuth tokens.

## Update

```bash
claude plugin marketplace update adant-ai
claude plugin update adant@adant-ai
```

After login, use any exposed reconnect control, rediscover tools and rerun the
remote authentication probe. Continue the original request in this conversation
when verification passes, starting with `adant_meet_team`. A login run from the
shell does not refresh a session that is already open: if the tools stay absent
after rediscovery, use the short new-session message in the [authentication
preflight](../adant/references/authentication.md), and do not repeat login after
authorization has succeeded.
