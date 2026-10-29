---
name: adant-clone-ad
description: Run a complete reference ad adaptation workflow through AdAnt server agents.
---

# Adant Clone Ad

Before work, follow the [authentication preflight](../adant/references/authentication.md).

Follow the [durable project procedure](../adant/references/projects.md).
Select `agentKey: "adant-social-video"` with `adant_agent_start` after checking capabilities.

Use `projectType: "clone"` with a supported reference URL or completed upload.
State which hook, structure, pacing, shots, voice, overlays and product traits
to preserve and which to change. Ask AdAnt to analyze and plan before generation
unless the user already approved that plan. Do not promise frame-perfect
reproduction. Review returned artifacts against the brief and refine the same
project rather than restarting it.
