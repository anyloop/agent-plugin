---
name: slide-pdf-generator
description: Generate landscape presentation-quality PDFs from HTML slide decks using Chrome CDP. Produces 16:9 slides with zero margins, no headers/footers, exact page dimensions.
---

# Slide PDF Generator

Converts HTML slide decks to landscape PDFs with exact 16:9 page dimensions.

## Design System

HTML slides should follow this structure:

```html
<style>
  @page { size: landscape; margin: 0; }
  body { background: #1e1e1e; color: #e8e8e8; }
  .slide {
    width: 1280px; height: 720px;
    page-break-after: always;
    overflow: hidden;
  }
</style>

<div class="slide">
  <!-- Slide content -->
</div>
```

### Image Cropping — Face-Centered Thumbnails
All thumbnail and cover images use `object-position: center 20%` to keep faces
visible when `object-fit: cover` crops the image. This shifts the crop anchor
to the upper 20% of the image where faces typically appear in portrait video
thumbnails.

### Color Palette (Cisumverse Style)
- Background: `#1e1e1e`
- Card: `#2a2a2a`
- Text: `#e8e8e8`
- Muted: `#888`
- Accent: `#c8e64a` (neon green)

### Slide Types
- **Cover**: Hero image right, title + badge left
- **Overview**: Section label + title + 3-column cards
- **Category Intro**: Full-height image left (480px), text right with divider
- **Video Grid (2-col)**: Two video cards side-by-side with thumbnails
- **Video Grid (3-col)**: Three narrower video cards
- **Combined**: Image left + text + embedded card (for single-video categories)
- **Summary**: Large stat numbers in a row

## Usage

```bash
# Basic
uv run --project skills/slide-pdf-generator/runtime \
  skills/slide-pdf-generator/runtime/to_pdf.py report.html output.pdf

# Custom dimensions
uv run --project skills/slide-pdf-generator/runtime \
  skills/slide-pdf-generator/runtime/to_pdf.py report.html output.pdf --width 1920 --height 1080

# Readiness cap for heavy pages (returns early when ready)
uv run --project skills/slide-pdf-generator/runtime \
  skills/slide-pdf-generator/runtime/to_pdf.py report.html output.pdf --wait 25
```

The renderer waits for document load, `document.fonts.ready`, image load and
decode, and two animation frames. `--wait` is only a hard cap for blocked
resources, so ready decks do not pay the full duration.

## Requirements
- Google Chrome
- Python 3.11+ and `uv`
