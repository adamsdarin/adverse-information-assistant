#!/usr/bin/env python3
"""Render docs/process-map.html to a PDF, one page per slide.

WHY THIS IS A SEPARATE SCRIPT WITH OPTIONAL DEPENDENCIES
-------------------------------------------------------
Everything else in scripts/ runs on the standard library plus PyYAML, because a
maintainer who is not a developer has to be able to run the whole suite with one
command. Producing a PDF needs a headless browser (Mermaid draws the diagrams in
JavaScript — there is no way to rasterise them without one), and that is a large
dependency to force on someone who only wants to validate a corpus.

So this script is opt-in. It is not imported by the test suite, nothing depends
on it, and it fails with an instruction rather than a traceback when the
dependencies are absent.

WHY IT SCREENSHOTS RATHER THAN USING THE BROWSER'S PRINT
-------------------------------------------------------
Chromium's print-to-PDF paginates against a fixed page height. The slides are
not a fixed height: most are exactly 860px, but the prose-heavy ones run to
about 2,000px, because the reasoning behind a section is sometimes long and
shrinking it to fit would make it unreadable. Printing at a fixed height split
those across page boundaries — the first attempt produced 25 pages out of 17
slides, with diagrams cut in half.

Screenshotting each slide and assembling a PDF whose page size matches each
image means nothing is ever cut. The cost is a raster PDF: the text is not
selectable. That trade is deliberate — this file exists to be looked at and
handed to someone, and docs/process-map.html remains the searchable version.

Usage:
  python scripts/render_pdf.py                       # -> docs/process-map.pdf
  python scripts/render_pdf.py --out /tmp/map.pdf
  python scripts/render_pdf.py --scale 2             # sharper, larger file

Requires:  pip install playwright img2pdf  &&  playwright install chromium
Needs network on first run, to load Mermaid from the CDN.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "process-map.html"
DEFAULT_OUT = ROOT / "docs" / "process-map.pdf"

MISSING = """\
This script needs two optional packages and a browser:

    pip install playwright img2pdf
    playwright install chromium

They are deliberately not repo dependencies — see the docstring. The HTML map at
docs/process-map.html needs none of this and is the canonical artifact."""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--scale", type=float, default=1.6,
                    help="device pixel ratio; 1.6 is legible, 2 is sharper "
                         "and roughly 60%% larger (default: 1.6)")
    ap.add_argument("--timeout", type=int, default=30000,
                    help="ms to wait for Mermaid to draw (default: 30000)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
        import img2pdf
    except ImportError:
        print(MISSING)
        return 1

    if not SRC.exists():
        print(f"ERROR: {SRC.relative_to(ROOT)} not found — run "
              "python scripts/render_process_map.py first")
        return 1

    shots_dir = args.out.parent / ".slides"
    shots_dir.mkdir(parents=True, exist_ok=True)
    shots = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900},
                                device_scale_factor=args.scale)
        page.goto(SRC.resolve().as_uri())
        try:
            page.wait_for_selector("svg[id^=mermaid]", timeout=args.timeout)
        except Exception:  # noqa: BLE001
            print("ERROR: Mermaid did not draw. It loads from a CDN, so this "
                  "needs network access on first run. Nothing was written.")
            browser.close()
            return 1
        # Mermaid lays out asynchronously after the first SVG appears; without
        # this the last diagrams screenshot mid-layout.
        page.wait_for_timeout(4500)

        slides = page.query_selector_all(".slide, .index")
        if not slides:
            print("ERROR: no slides found in the page")
            browser.close()
            return 1
        for i, el in enumerate(slides):
            f = shots_dir / f"p{i:02d}.png"
            el.screenshot(path=str(f))
            shots.append(str(f))
            h = el.bounding_box()["height"]
            print(f"  page {i + 1:>2}  {h:>5.0f}px")
        browser.close()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(img2pdf.convert(shots))
    for f in shots:
        Path(f).unlink(missing_ok=True)
    shots_dir.rmdir()

    size = args.out.stat().st_size
    print(f"\nWrote {args.out} — {len(shots)} pages, {size / 1e6:.1f} MB")
    print("Raster PDF: text is not selectable. docs/process-map.html is the "
          "searchable version.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
