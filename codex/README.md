# AdAnt for Codex

Research social content, build strategies, and create or clone short-form video
ads in one AdAnt plugin. It connects Codex to the authenticated AdAnt MCP at
`https://api.adant.ai/mcp`.

## Install in ChatGPT desktop

Open **Plugins**, add `https://github.com/anyloop/agent-plugin.git` as a personal
marketplace on the `main` ref, then install AdAnt from **Personal**. Complete
the AdAnt connection prompt during installation and start a new task so the
skills and MCP tools are discovered.

If AdAnt was installed or updated in the current task, start a new task first.
If its tools are still unavailable there, open AdAnt under **Plugins** >
**Installed** or **Personal**, complete any connection prompt, then start
another new task. ChatGPT desktop does not require the separate `codex`
terminal command.

## Install in Codex CLI

Add the public AdAnt marketplace, then install the plugin:

```bash
codex plugin marketplace add anyloop/agent-plugin --ref main
codex plugin add adant@adant-ai
```

Installation is configured to authenticate immediately. Codex CLI opens AdAnt
in the browser so the user can sign in or create an account, review the
requested permissions, and authorize the connection. A manual CLI reconnect
is also available:

```bash
codex mcp login adant
```

Use this command only when the `codex` executable is installed in that
terminal. Finish sign-in in Chrome or Safari. If the embedded browser times
out, return to the AdAnt authorization page, copy its full address, and paste
it into the regular browser while the command keeps running.

Verify the installation with:

```bash
codex plugin list
codex mcp get adant
```

Start a new Codex task after installing or updating the plugin so the new
skills and tools are discovered.

## Included workflows

- `adant` routes one-off image, video, and voice generation plus credit, model,
  job, upload, and library operations.
- `adant-create-ad` runs a durable, approval-gated creative project for a
  complete ad.
- `adant-clone-ad` analyzes and adapts a reference ad while preserving the
  traits chosen by the user.
- `initial-social-content-research` researches a product, competitors, TikTok,
  Instagram, Meta Ads, and YouTube before generating a research deck.
- `social-content-strategist` converts current examples and prior research into
  distinct, reusable content strategies.
- Component skills provide product research, keyword discovery, platform
  browsing, video understanding, report generation, and strategy synthesis.

Generation spends AdAnt credits. The skills require an explicit confirmation
before submitting credit-spending work and derive project ownership from the
authorized AdAnt account.

Social-research model work uses the installed AdAnt connection to mint a
short-lived, scoped local token; it does not require a second CLI login or a
Gemini/provider key. Local tools require `uv` and Chrome; `uv` provisions the
locked Python runtime automatically, so no system Python or Node.js install is
needed. Some searches also require an interactive TikTok or Instagram session.
The progress view is a live MCP App; hosts that cannot render it receive a
tokenized local-only fallback URL. Remote generation and local media tools
share a content-hashed MCP App preview for job state, credits, analysis,
cancellation, and completed assets. Browser state and credentials must never
be exposed.

## Support

For product information, visit [adant.ai](https://adant.ai). For help, email
[contact@anyloop.ai](mailto:contact@anyloop.ai).
