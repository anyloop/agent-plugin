# Install AdAnt in Codex

## Requirements

- A current Codex installation with plugin support.
- A browser for AdAnt sign-in and OAuth consent.

## Install and sign in

```bash
codex plugin marketplace add anyloop/agent-plugin --ref main
codex plugin add adant@adant-ai
```

The marketplace requests authentication during installation. If the browser
flow was closed or the account needs to change, run:

```bash
codex mcp login adant
```

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

Start a new task after updating. Re-run `codex mcp login adant` only if the MCP
connection reports that authentication or a newer permission scope is needed.

## Remove

```bash
codex plugin remove adant@adant-ai
codex plugin marketplace remove adant-ai
```
