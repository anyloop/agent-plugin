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
when verification passes. If the host cannot refresh its tools here, preserve
the request and research operation IDs in a resume prompt for a new conversation;
do not repeat login after authorization has succeeded.
