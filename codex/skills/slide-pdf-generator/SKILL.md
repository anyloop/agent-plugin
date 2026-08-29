---
name: slide-pdf-generator
description: Convert a prepared landscape HTML slide deck into a presentation-quality PDF through the adant-local report phase.
---

# Generate a Slide PDF

Use only `research_run` phase `report` with variant `pdf`. Pass the prepared HTML
artifact, desired PDF artifact, and optional viewport width/height. The phase owns
browser startup, print settings, cleanup, and structured errors.

Verify the result exists and is non-empty. Keep 16:9 landscape geometry, zero
print margins, backgrounds enabled, and no browser headers/footers. Report the
output artifact and any render warning; do not claim success from phase exit alone.
