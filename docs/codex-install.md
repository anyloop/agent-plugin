# Install AdAnt in Codex

## Requirements

- ChatGPT desktop with Codex, or Codex CLI with plugin support.
- A browser for AdAnt sign-in and OAuth consent.
- `uv` for local research tools. `uv` provisions Python automatically.

## ChatGPT desktop / Codex app

1. Open **Plugins**.
2. Add `https://github.com/anyloop/agent-plugin.git` as a personal marketplace
   on the `main` ref.
3. Find AdAnt under **Personal**, install it, and complete the connection or
   authorization prompt.
4. Start a new task so the installed skills and MCP tools are discovered.

If AdAnt was installed or updated in the current task, start a new task first.
If its tools are still unavailable there, open it under **Installed** or
**Personal**, complete any connection prompt, then start another new task. Do
not install Codex CLI only to reconnect the desktop plugin.

## Codex CLI

```bash
codex plugin marketplace add anyloop/agent-plugin --ref main
codex plugin add adant@adant-ai
```

The marketplace requests authentication during installation. If the browser
flow was closed or the account needs to change, and the `codex` executable is
available in this terminal, run:

```bash
codex mcp login adant
```

Complete sign-in in Chrome or Safari. If the embedded browser times out, return
to the AdAnt authorization page, copy its full address, and paste it into the
regular browser while the command keeps running. The AdAnt page also provides
a **Copy sign-in link** button for this recovery path.

## Verify

```bash
codex plugin list
codex mcp get adant
```

Start a new Codex task after installation so the AdAnt skills and tools are
discovered. Then ask Codex to create an image or short-form ad with AdAnt.

## Update

```bash
codex plugin marketplace upgrade adant-ai
codex plugin add adant@adant-ai
```

Start a new task after updating. In ChatGPT desktop, reconnect from the AdAnt
plugin details when prompted. In Codex CLI, re-run `codex mcp login adant` only
if the MCP connection reports that authentication or a newer permission scope
is needed.

## Remove

```bash
codex plugin remove adant@adant-ai
codex plugin marketplace remove adant-ai
```

## First run

Start a new task and send `$adant-init`. It opens the live progress panel,
verifies the AdAnt connection, checks local research prerequisites, and hands
you three ready-to-send starting prompts for your product.
