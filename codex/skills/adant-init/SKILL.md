---
name: adant-init
description: Verify the AdAnt remote connection and available agents before research, creation or social work.
---

# Adant Init

Before work, follow the [authentication preflight](../adant/references/authentication.md).

Follow the [durable project procedure](../adant/references/projects.md).

Use `$adant-init` for setup. Call `adant_get_credit_balance` as the read-only
authentication probe, then `adant_get_capabilities` and discover the creative
project tools plus `adant_agent_start` and `adant_list_agent_tasks`.
Inspect role metadata for Strategist, Scout, Creator and Manager, including
which specialists/project types this account can use. A zero balance proves authentication but may prevent paid work.
Research requires no local runtime or social login. Never work around a missing
server with a browser, provider key or local script. Consolidate missing
capabilities into one concrete explanation; never repeat restart advice without
new evidence. Continue the original request once the probe and capabilities pass.
Explain that AdAnt usage is billed separately from the host coding agent.
