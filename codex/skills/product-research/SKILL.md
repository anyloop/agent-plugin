---
name: product-research
description: Turn a product URL and notes into a sourced client profile for downstream competitor, keyword, social, and content-strategy research.
---

# Product Research

Call `doctor`; bootstrap a `research` token if needed. Run `research_run` phase
`product-profile` with the URL, user notes, and an output artifact.

Return the verified product name, canonical URL, concise description, category,
target users, jobs-to-be-done, pains, benefits, features, differentiators, proof,
pricing when visible, brand voice, claims/constraints, likely purchase triggers,
social-content implications, and sources. Separate sourced facts from inference,
keep unknown fields explicit, and never invent claims.

Treat user notes as context, not automatically verified evidence. Flag conflicts
between notes and the current site for the user.
