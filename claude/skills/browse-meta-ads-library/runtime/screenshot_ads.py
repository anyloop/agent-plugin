#!/usr/bin/env python3
"""
Screenshot individual Meta Ad Library cards by ad ID.

Uses Playwright headless browser to navigate to each ad's library page,
close the modal overlay, find the ad card by Library ID, and screenshot it.

Usage:
  uv run --project runtime runtime/screenshot_ads.py --ids 709633901484822 1227184966143012 -o output/thumbnails/
  uv run --project runtime runtime/screenshot_ads.py --ids-file ad_ids.txt -o output/thumbnails/
  uv run --project runtime runtime/screenshot_ads.py --ids 709633901484822 --prefix "newsbreak-"
"""

import argparse
import sys
import time
from pathlib import Path

from config import AD_LIBRARY_BASE_URL


def screenshot_ad_cards(
    ad_ids: list[str],
    output_dir: Path,
    prefix: str = "ad-",
    viewport_width: int = 500,
    viewport_height: int = 900,
    creative_only: bool = False,
) -> list[dict]:
    """Screenshot individual ad cards from Meta Ad Library.

    Args:
        ad_ids: List of Meta Ad Library IDs to screenshot.
        output_dir: Directory to save screenshots.
        prefix: Filename prefix for screenshots.
        viewport_width: Browser viewport width.
        viewport_height: Browser viewport height.
        creative_only: If True, crop to just the ad creative (skip metadata header).

    Returns:
        List of dicts with ad_id, path, and status for each screenshot.
    """
    from playwright.sync_api import sync_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": viewport_width, "height": viewport_height}
        )

        for ad_id in ad_ids:
            url = f"{AD_LIBRARY_BASE_URL}?id={ad_id}"
            filename = f"{prefix}{ad_id}.jpg"
            out_path = output_dir / filename

            print(f"  Capturing {ad_id}...")

            try:
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(4)

                # Close the "Link to ad" modal if present
                try:
                    close_btn = page.locator("text=Close").first
                    if close_btn.is_visible(timeout=3000):
                        close_btn.click()
                        time.sleep(2)
                except Exception:
                    pass

                # Find the ad card by its Library ID text
                card_box = page.evaluate(
                    """(adId) => {
                    const el = document.evaluate(
                        "//span[contains(text(), 'Library ID: " + adId + "')]",
                        document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                    ).singleNodeValue;
                    if (!el) return null;
                    let parent = el.parentElement;
                    for (let i = 0; i < 15; i++) {
                        if (!parent) break;
                        const rect = parent.getBoundingClientRect();
                        if (rect.height > 300 && rect.height < 800 && rect.width > 300) {
                            return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                        }
                        parent = parent.parentElement;
                    }
                    return null;
                }""",
                    ad_id,
                )

                if card_box:
                    # If creative_only, crop to bottom 55% of card (skip metadata header)
                    clip = card_box
                    if creative_only:
                        header_height = card_box["height"] * 0.35
                        clip = {
                            "x": card_box["x"],
                            "y": card_box["y"] + header_height,
                            "width": card_box["width"],
                            "height": card_box["height"] - header_height,
                        }

                    page.screenshot(
                        path=str(out_path),
                        type="jpeg",
                        quality=90,
                        clip=clip,
                    )
                    print(f"    Saved: {out_path}")
                    results.append(
                        {"ad_id": ad_id, "path": str(out_path), "status": "ok"}
                    )
                else:
                    # Fallback: find by advertiser name
                    fallback_box = page.evaluate(
                        """() => {
                        const els = document.querySelectorAll('strong, span, a');
                        for (const el of els) {
                            if (el.textContent.includes('Sponsored') && el.textContent.length < 30) {
                                let parent = el.parentElement;
                                for (let i = 0; i < 15; i++) {
                                    if (!parent) break;
                                    const rect = parent.getBoundingClientRect();
                                    if (rect.height > 300 && rect.height < 800 && rect.width > 300) {
                                        return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
                                    }
                                    parent = parent.parentElement;
                                }
                            }
                        }
                        return null;
                    }"""
                    )

                    if fallback_box:
                        page.screenshot(
                            path=str(out_path),
                            type="jpeg",
                            quality=90,
                            clip=fallback_box,
                        )
                        print(f"    Saved (fallback): {out_path}")
                        results.append(
                            {"ad_id": ad_id, "path": str(out_path), "status": "ok"}
                        )
                    else:
                        # Last resort: viewport screenshot
                        page.evaluate("window.scrollTo(0, 200)")
                        time.sleep(1)
                        page.screenshot(
                            path=str(out_path),
                            type="jpeg",
                            quality=90,
                        )
                        print(f"    Saved (viewport fallback): {out_path}")
                        results.append(
                            {
                                "ad_id": ad_id,
                                "path": str(out_path),
                                "status": "viewport_fallback",
                            }
                        )

            except Exception as e:
                print(f"    Error: {e}", file=sys.stderr)
                results.append(
                    {"ad_id": ad_id, "path": None, "status": f"error: {e}"}
                )

        browser.close()

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Screenshot Meta Ad Library cards by ad ID",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --ids 709633901484822 1227184966143012
  %(prog)s --ids-file ad_ids.txt -o output/thumbnails/
  %(prog)s --ids 709633901484822 --prefix "newsbreak-"
        """,
    )
    parser.add_argument(
        "--ids",
        nargs="+",
        default=[],
        help="Ad Library IDs to screenshot",
    )
    parser.add_argument(
        "--ids-file",
        type=str,
        default=None,
        help="File with ad IDs (one per line)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=str,
        default="output/ad-screenshots",
        help="Output directory for screenshots (default: output/ad-screenshots)",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="ad-",
        help="Filename prefix (default: ad-)",
    )
    parser.add_argument(
        "--creative-only",
        action="store_true",
        help="Crop to just the ad creative (skip metadata header)",
    )

    args = parser.parse_args()

    ad_ids = list(args.ids)
    if args.ids_file:
        ids_path = Path(args.ids_file)
        if ids_path.exists():
            ad_ids.extend(
                line.strip()
                for line in ids_path.read_text().splitlines()
                if line.strip() and not line.startswith("#")
            )

    if not ad_ids:
        parser.error("Provide ad IDs via --ids or --ids-file")

    output_dir = Path(args.output_dir)
    print(f"Screenshotting {len(ad_ids)} ad(s) to {output_dir}/")

    results = screenshot_ad_cards(
        ad_ids, output_dir, prefix=args.prefix, creative_only=args.creative_only
    )

    ok_count = sum(1 for r in results if r["status"] == "ok")
    print(f"\nDone: {ok_count}/{len(ad_ids)} captured successfully")

    for r in results:
        if r["status"] != "ok":
            print(f"  Warning: {r['ad_id']} - {r['status']}", file=sys.stderr)


if __name__ == "__main__":
    main()
