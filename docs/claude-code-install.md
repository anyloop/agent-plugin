# Install AdAnt in Claude Code

## Requirements

- A current local Claude Code installation with plugin support.
- A browser for AdAnt sign-in and OAuth consent.
- An AdAnt account; paid work uses AdAnt credits separately from host credits.

Remote Claude surfaces may not support local marketplace installation or the
interactive login flow. Complete setup in local Claude Code.

## Install

Run this once in a terminal:

```bash
claude plugin install adant --marketplace anyloop/agent-plugin
```

`--marketplace` needs Claude Code 2.1.292 or later. On an older version, update or add
the marketplace first:

```bash
claude plugin marketplace add https://github.com/anyloop/agent-plugin.git
claude plugin install adant@adant-ai
```

Inside a session the same steps are `/plugin marketplace add anyloop/agent-plugin`
and `/plugin install adant@adant-ai`, which opens a panel to choose the scope;
sign in from `/mcp`. A user-scope install also appears in the
Code tab of the Claude desktop app, which draws AdAnt's team, project, report and
video cards inline. The terminal gets short text replies and Studio links.

## Sign in

The plugin-managed MCP server is named `plugin:adant:adant`:

```bash
claude mcp login plugin:adant:adant
```

If the command needs a true interactive terminal, use the packaged helper:

```bash
sh "${CLAUDE_PLUGIN_ROOT}/skills/adant-claude-setup/scripts/login-adant.sh"
```

## Verify

```bash
claude plugin list
claude mcp get plugin:adant:adant
```

Start a new Claude Code conversation after installation so the AdAnt skills
and tools are loaded, then say "Introduce the AdAnt team" or send your product
URL. Reconnect if the MCP reports `insufficient_scope`.

## Update

```bash
claude plugin marketplace update adant-ai
claude plugin update adant@adant-ai
```

Start a new conversation after updating. Third-party marketplaces do not
auto-update by default; turn it on for `adant-ai` from `/plugin` > Marketplaces
to skip these commands.

## Remove

```bash
claude plugin uninstall adant@adant-ai
claude plugin marketplace remove adant-ai
```
