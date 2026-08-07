# AdAnt for Codex

Research social content, build strategies, and create or clone short-form video
ads in one AdAnt plugin. It connects Codex to the authenticated AdAnt MCP at
`https://api.adant.ai/mcp`.

## Install

Add the public AdAnt marketplace, then install the plugin:

```bash
codex plugin marketplace add anyloop/agent-plugin --ref main
codex plugin add adant@adant-ai
```

Installation is configured to authenticate immediately. Codex opens AdAnt in
the browser so the user can sign in or create an account, review the requested
permissions, and authorize the connection. A manual reconnect is also
available:

```bash
codex mcp login adant
```

Run the reconnect command in your system terminal and finish sign-in in your
regular Chrome or Safari browser. If Google times out in Codex's built-in
browser, return to the AdAnt authorization page, copy its full address, and
paste it into the regular browser while the command keeps running.

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

Social-research model work reuses AdAnt's authenticated CLI and server-side
credentials. If the CLI has not been authorized on this machine, run
`npx @anyloop/adant-cli auth login`; no Gemini or other model-provider API key is needed.
Local adapters may also require Python 3.11+, `uv`, Chrome, and an interactive
TikTok or Instagram session. They store browser state outside the plugin via
`ADANT_SOCIAL_DATA_DIR` and must never expose cookies or credentials.

## Support

For product information, visit [adant.ai](https://adant.ai). For help, email
[contact@anyloop.ai](mailto:contact@anyloop.ai).
