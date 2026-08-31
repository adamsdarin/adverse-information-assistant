#!/usr/bin/env python3
"""Render PROCESS.md into docs/process-map.html — a page you can just open.

PROCESS.md is the file of record and renders fine on GitHub. But locally,
Markdown with mermaid fences is source code, not a picture. This produces a
self-contained page that draws the diagrams, so the process map is something
you LOOK at rather than read as text.

WHY THE OUTPUT LOOKS LIKE A DECK
--------------------------------
The audience for this page is not only the maintainer. It is beta testers,
reviewers, and eventually a security officer deciding whether the tool is worth
anyone's time. A dark engineering page with a stack of flowcharts asks those
readers to work. So each section renders as a landscape "slide": a letterspaced
eyebrow, a serif headline stating the point as a sentence, a standfirst, then
the diagram and the reasoning in bordered cards.

The generator is unchanged in kind — PROCESS.md is still the only source, and
the staleness test still binds the two. Restyling the renderer rather than
hand-authoring a deck means every future edit to PROCESS.md inherits the design
instead of needing someone to redraw it.

WHAT THIS RENDERER CANNOT DO
----------------------------
Mermaid draws graphs. It does not compose the hand-laid layouts of a designed
deck — a horizontal stepper with captioned dots, a three-column comparison, a
numbered list of stop conditions with status pills. Those live in PROCESS.md as
prose and tables and render as cards here. If a section ever needs a bespoke
layout, hand-author that one page and drop its mermaid fence; the staleness test
counts fences, so the check stays honest either way.

Usage: python scripts/render_process_map.py
"""
import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "PROCESS.md"
OUT = ROOT / "docs" / "process-map.html"

# ---------------------------------------------------------------------------
# THE PALETTE
# ---------------------------------------------------------------------------
# Desaturated on purpose. This document describes somebody's worst month, and
# saturated status colours make a report of a drink-driving arrest read like a
# monitoring dashboard. The tints carry the same semantics the old dark theme
# did — red for a hard floor, green for optional or passing, amber for
# unverified, blue and lilac for gates — at a weight that reads as paper.
CSS = """
  /* PRINT PAGE. US Letter PORTRAIT with real margins.
     This was landscape, on the theory that the diagrams are wide. That was the
     wrong trade: there are nine figures and several thousand words, so the page
     spent most of its width as margin beside a text column on every prose page.
     Portrait lets the text fill the measure, and the figures scale to the
     column — which they had to do on paper anyway, since a printed page cannot
     scroll. */
  /* Letter LANDSCAPE. Portrait filled the text column but starved the figures:
     a 4,700px-wide flowchart scaled to a 6.5in column is a picture of a
     flowchart, not a readable one. Landscape gives them roughly twice the
     width, and the prose runs in two columns so none of that width is wasted
     as margin — which is what portrait was solving for. */
  @page { size:letter landscape; margin:11mm 13mm; }

  :root {
    --paper:#F5F1E9; --card:#FDFBF7; --ink:#2B2723; --ink-soft:#5D5750;
    --ink-mute:#8A7F70; --rule:#E2DCD0;
    --rust:#C2703F; --rust-deep:#5C2F24; --dark:#332E29;
    /* The measure IS the column. Nothing is narrower than the page it sits on,
       so there is no reserved margin inside the text area — that was the last
       source of dead space after the fixed-height pages went away. */
    --measure:100%;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Source Serif 4",
            Charter,Georgia,"Times New Roman",serif;
    --sans:"Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--paper); color:var(--ink);
         font:15.5px/1.68 var(--sans); -webkit-font-smoothing:antialiased; }

  /* ---------------------------------------------------- continuous flow
     ONE document, read top to bottom. There is no .slide, no page badge and no
     per-page footer, because the document is not a deck: chopping it into
     seventeen cards meant every seam was a decision about where a reader must
     stop, and none of those decisions were ones the content asked for.
     Text runs at a fixed measure so it stays readable. Figures break out of
     that measure, because a flowchart is not prose and should use the width it
     needs. */
  .doc { max-width:1240px; margin:0 auto; padding:56px 44px 80px; }
  .measure { max-width:var(--measure); }

  .kicker { font-size:10.5px; font-weight:700; letter-spacing:.14em;
            text-transform:uppercase; color:var(--ink-mute); margin:0 0 10px; }
  .kicker .n { color:var(--rust); }
  h1 { font-family:var(--serif); font-size:48px; line-height:1.08;
       font-weight:400; margin:0 0 20px; letter-spacing:-.01em; }
  h2 { font-family:var(--serif); font-size:27px; line-height:1.2;
       font-weight:400; margin:0 0 14px; letter-spacing:-.005em;
       max-width:34ch; }
  h3 { font-size:11px; font-weight:700; letter-spacing:.11em;
       text-transform:uppercase; color:var(--rust); margin:0 0 12px; }
  .lede { font-family:var(--serif); font-size:20px; line-height:1.5;
          color:var(--ink-soft); margin:0 0 34px; max-width:52ch; }
  .standfirst { font-size:16.5px; line-height:1.6; color:var(--ink-soft);
                margin:0 0 26px; max-width:var(--measure); }

  section { margin:0; padding:44px 0 4px; border-top:1px solid var(--rule); }
  section:first-of-type { border-top:0; }
  /* Only the PROSE is multi-column. Figures sit between .cols blocks as
     full-width elements rather than spanning columns, because column-span:all
     in paged media is unreliable in every engine and a figure silently dropped
     into one narrow column is worse than no columns at all. */
  .cols { columns:2; column-gap:36px; }
  .cols > * { break-inside:avoid-column; }
  .cols > h4:first-child { margin-top:0; }

  p, li { color:var(--ink-soft); margin:0 0 14px; max-width:var(--measure); }
  strong { color:var(--ink); font-weight:600; }
  ul { padding-left:20px; margin:0 0 16px; }
  h4 { font-family:var(--serif); font-size:20px; font-weight:400;
       margin:30px 0 10px; color:var(--ink); max-width:var(--measure); }
  code { font-family:ui-monospace,"Cascadia Mono",Consolas,monospace;
         font-size:12.5px; background:#EFE9DC; border-radius:3px;
         padding:1px 5px; color:var(--rust-deep); }
  table { border-collapse:collapse; margin:0 0 20px; font-size:13.5px;
          max-width:100%; }
  th,td { border-bottom:1px solid var(--rule); padding:9px 14px 9px 0;
          text-align:left; vertical-align:top; color:var(--ink-soft); }
  th { font-size:10px; font-weight:700; letter-spacing:.09em;
       text-transform:uppercase; color:var(--ink);
       border-bottom:1px solid #CFC6B4; }
  blockquote { margin:0 0 18px; padding:4px 0 4px 18px;
               border-left:3px solid var(--rust); font-family:var(--serif);
               font-size:17px; line-height:1.5; color:var(--ink);
               max-width:60ch; }

  /* ---------------------------------------------------- figures
     Full width, natural size, scrollable when wider than the page. Squeezing a
     10:1 flowchart into the text measure put its labels at about 7px. On paper
     the print rules below scale it to fit instead, since a printed page cannot
     scroll. */
  figure { margin:8px 0 34px; }
  .figbox { background:var(--card); border:1px solid var(--rule);
            border-radius:10px; padding:20px; position:relative; }
  .mermaid { display:flex; justify-content:center; }
  .mermaid svg { max-width:none !important; }
  figcaption { font-size:11px; font-weight:700; letter-spacing:.09em;
               text-transform:uppercase; color:var(--ink-mute);
               margin:10px 0 0; }

  /* ---------------------------------------------------- diagram pan/zoom
     Every figure gets the same treatment: the .zoom-pane clips, the SVG
     inside it carries the transform, and .figbox never scrolls natively —
     scroll and drag both mean "pan" once JS attaches, so they can't fight
     each other. Diagrams are already a hard JS dependency (Mermaid renders
     nothing without it), so overflow:hidden here costs no no-JS fallback
     that didn't already not exist. */
  .zoom-pane { overflow:hidden; cursor:grab; border-radius:6px; }
  .zoom-pane.grabbing { cursor:grabbing; }
  /* No will-change here on purpose. It promotes the SVG to its own
     GPU-composited layer, which gets rasterized to a bitmap once and then
     stretched as scale changes — exactly what makes zoomed text go blurry.
     Without it the browser repaints the vector content on the main thread
     at each new scale, so labels stay sharp at any zoom level; these are
     small flowcharts, not large images, so the repaint cost is trivial. */
  .zoom-pane .mermaid svg { transform-origin:0 0; }
  .zoom-controls { position:absolute; top:14px; right:14px; z-index:2;
                   display:flex; align-items:center; gap:6px; }
  .zoom-controls button { width:28px; height:28px; border-radius:6px;
                           border:1px solid var(--rule); background:var(--card);
                           color:var(--ink); font-size:15px; line-height:1;
                           cursor:pointer; font-family:var(--sans); }
  .zoom-controls button:hover { background:#EFE9DC; }
  .zoom-hint { font-size:10px; color:var(--ink-mute); letter-spacing:.03em;
               margin-right:2px; user-select:none; }

  /* ---------------------------------------------------- masthead + contents */
  .masthead { padding-bottom:44px; }
  .pair { display:grid; grid-template-columns:1fr 1fr; gap:22px;
          margin:0 0 34px; max-width:100%; }
  .pair > div { background:var(--card); border:1px solid var(--rule);
                border-radius:10px; padding:20px 22px; }
  .pair h3 { margin-bottom:10px; }
  .pair p { margin:0; font-size:14px; max-width:none; }
  .principles { display:grid; grid-template-columns:repeat(4,1fr); gap:20px;
                margin:0 0 34px; }
  .principles > div { border-top:2px solid var(--rust); padding-top:14px; }
  .principles .n { font-family:var(--serif); font-size:26px; color:var(--rust);
                   line-height:1; margin-bottom:10px; }
  .principles h4 { font-family:var(--sans); font-size:10.5px; font-weight:700;
                   letter-spacing:.1em; text-transform:uppercase;
                   margin:0 0 7px; color:var(--ink); }
  .principles p { margin:0; font-size:13px; max-width:none; }
  .contents { margin:0 0 10px; }
  .contents ol { margin:0; padding-left:20px; columns:2; column-gap:56px; }
  .contents li { font-size:14.5px; margin:0 0 8px; }
  .contents a { color:var(--rust); text-decoration:none; }
  .contents a:hover { text-decoration:underline; }
  .boundary { background:#EFE9DC; border-left:3px solid var(--rust);
              padding:14px 18px; font-size:12px; color:var(--ink-soft);
              margin:0 0 8px; max-width:none; }
  .colophon { border-top:1px solid var(--rule); margin-top:56px;
              padding-top:14px; font-size:12px; color:var(--ink-mute); }

  /* ---------------------------------------------------- print */
  @media print {
    /* White paper in print, cream reserved for figure boxes and callouts.
       A cream content block floating inside white page margins looked like a
       mistake, and a full-bleed tint is not something a printer can honour
       anyway. */
    html, body { background:#fff; }
    .doc { padding:0; max-width:none; }
    body { font-size:9.8pt; line-height:1.5; }
    h1 { font-size:28pt; } h2 { font-size:16pt; max-width:none; }
    .lede { font-size:12.5pt; max-width:none; }
    .standfirst { font-size:11pt; }
    section { padding-top:22px; }
    figure { margin:6pt 0 14pt; }
    .cols { column-gap:30px; }
    .principles { gap:12pt; } .pair { gap:12pt; }
    /* NO forced page break per section. This was the single largest source of
       white space in the printed file: six sections meant six fresh pages, and
       any section running just over a page left most of the next one blank.
       Content now flows and the printer breaks where the text runs out, which
       is what "continuous document" has to mean on paper. */
    section { padding-top:26px; }
    figure, table, blockquote { break-inside:avoid; }
    h2, h3, h4 { break-after:avoid; }
    /* A printed page cannot scroll, so a figure scales to the column rather
       than being cut off at the page edge.
       The height cap is what keeps pages full. A figure is kept whole (never
       split across a page), so one too tall to fit the space remaining jumps to
       the next page and leaves the rest of the current one empty. Capping height
       means every figure fits inside roughly half a page, so the gap it can
       leave behind is bounded instead of being most of a sheet. */
    .figbox { overflow:visible; padding:12pt; }
    .zoom-pane { overflow:visible !important; cursor:default !important; }
    .zoom-controls, .zoom-hint { display:none !important; }
    .mermaid svg { max-width:100% !important; height:auto !important;
                   max-height:2.9in !important;
                   transform:none !important; }
    figcaption { margin-top:5pt; }
    /* Keep a heading with the figure it introduces, and never leave one or two
       lines of a paragraph stranded at a page edge. */
    h3 { break-after:avoid; }
    .kicker, h2, .standfirst { break-after:avoid; }
    p { orphans:3; widows:3; }
  }
"""

# ---------------------------------------------------------------------------
# Optional per-section metadata, read from PROCESS.md itself so this script is
# not a second source of truth. On the line after the heading:
#   <!-- eyebrow: PRIVACY CHOICES | headline: A sentence stating the point. -->
# Absent metadata falls back to the section title, so PROCESS.md never has to
# carry it and a newly added section cannot silently break the page.
# ---------------------------------------------------------------------------
META_RE = re.compile(
    r"<!--\s*eyebrow:\s*(?P<eyebrow>[^|>]+?)\s*"
    r"(?:\|\s*headline:\s*(?P<headline>[^|]+?)\s*)?"
    r"(?:\|\s*standfirst:\s*(?P<standfirst>.+?)\s*)?-->", re.S)

# A figure is a mermaid fence, optionally preceded by a bold caption line:
#
#   **01a · Setup and intake.**
#
#   ```mermaid
#   ...
#   ```
#
# The caption renders as ordinary bold text on GitHub and becomes the slide's
# sub-label here, so one source serves both. Captions are stripped from the
# prose so they don't appear twice.
FIG_RE = re.compile(
    r"(?:\*\*(?P<cap>[^*\n]+?)\*\*\s*\n\s*\n)?```mermaid\n(?P<code>.*?)```", re.S)


def md_min(s: str) -> str:
    """Just enough Markdown for the explanatory prose: sub-headings, bold,
    italic, code, blockquotes, bullet lists, tables."""
    s = html.escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s, flags=re.S)
    s = re.sub(r"(?<!\*)\*([^*\n]+?)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    out = []
    for para in s.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("|"):
            rows = [r for r in para.splitlines() if r.strip().startswith("|")]
            rows = [r for r in rows if not re.match(r"^\|[\s\-:|]+\|$", r.strip())]
            cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
            if not cells:
                continue
            head = "".join(f"<th>{c}</th>" for c in cells[0])
            body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                           for r in cells[1:])
            out.append(f"<table><thead><tr>{head}</tr></thead>"
                       f"<tbody>{body}</tbody></table>")
        elif para.startswith("- "):
            items = "".join(f"<li>{l[2:].strip()}</li>" for l in para.splitlines()
                            if l.strip().startswith("- "))
            out.append(f"<ul>{items}</ul>")
        elif para.startswith("&gt;"):
            body = " ".join(re.sub(r"^&gt;\s?", "", l).strip()
                            for l in para.splitlines())
            out.append(f"<blockquote>{body.strip()}</blockquote>")
        elif para.startswith("#### "):
            out.append(f"<h4>{para[5:].strip()}</h4>")
        elif para.startswith("### "):
            out.append(f"<h4>{para[4:].strip()}</h4>")
        else:
            out.append("<p>" + para.replace("\n", " ") + "</p>")
    return "".join(out)


def strip_p(fragment: str) -> str:
    """Unwrap a single <p> so a promoted first paragraph can be restyled."""
    m = re.fullmatch(r"<p>(.*)</p>", fragment, re.S)
    return m.group(1) if m else fragment


def main() -> int:
    if not SRC.exists():
        print(f"ERROR: {SRC} not found")
        return 1
    text = SRC.read_text(encoding="utf-8")

    sections = []
    for part in re.split(r"^## ", text, flags=re.M)[1:]:
        title = part.splitlines()[0].strip()
        # PROCESS.md headings are already numbered ("1. Session flow"); the
        # rendered page supplies its own badge, so strip the duplicate.
        title = re.sub(r"^\d+\.\s*", "", title)
        m = META_RE.search(part)
        eyebrow = (m.group("eyebrow").strip() if m else title).upper()
        headline = ((m.group("headline") or "").strip() if m else "")
        standfirst = ((m.group("standfirst") or "").strip() if m else "")
        diagrams = [((f.group("cap") or "").strip(), f.group("code"))
                    for f in FIG_RE.finditer(part)]
        prose = FIG_RE.sub("", part)
        prose = META_RE.sub("", prose)
        prose = "\n".join(prose.splitlines()[1:])
        prose = re.sub(r"\n-{3,}\n", "\n", prose).strip()
        sections.append((title, eyebrow, headline, standfirst, diagrams, prose))

    if not sections:
        print("ERROR: no '## ' sections found in PROCESS.md")
        return 1

    # ------------------------------------------------------------------
    # ONE CONTINUOUS DOCUMENT.
    #
    # This used to emit seventeen .slide blocks. Every seam was a decision about
    # where a reader had to stop, and none of those decisions came from the
    # content: the reasoning behind a section was cut away from the diagram it
    # explained, and a section with four figures became four pages that had to
    # announce themselves as "01b", "01c", "01d" so nobody lost the thread.
    #
    # A document does not need any of that. Sections flow, figures sit where
    # they are referenced, prose follows the picture it discusses, and the
    # printer decides where pages break — which is its job, not this script's.
    # ------------------------------------------------------------------
    body = []
    for i, sec in enumerate(sections, 1):
        title, eyebrow, headline, standfirst, diagrams, prose = sec
        body.append(f'<section id="s{i}">')
        body.append(f'<p class="kicker"><span class="n">{i:02d}</span> &nbsp;'
                    f'{html.escape(eyebrow)}</p>')
        body.append(f'<h2>{html.escape(headline or title)}</h2>')
        if standfirst:
            body.append(f'<p class="standfirst">{strip_p(md_min(standfirst))}</p>')
        # FIGURES FIRST, THEN PROSE — and the order is load-bearing for
        # pagination, not a stylistic choice.
        #
        # A figure is kept whole, so it is rigid: if it does not fit the space
        # left on a page it moves to the next one. Prose is fluid and breaks
        # anywhere. Put the fluid element last and it flows down to fill each
        # page to the bottom; put it first and it ends mid-page, then the rigid
        # figure jumps and leaves the rest of the sheet blank. Trying it the
        # other way round left half of one page empty.
        for j, (cap, code) in enumerate(diagrams, 1):
            body.append("<figure>")
            if cap:
                body.append(f'<h3>{html.escape(cap)}</h3>')
            body.append(
                '<div class="figbox">'
                '<div class="zoom-controls">'
                '<span class="zoom-hint">scroll to zoom &middot; drag to pan</span>'
                '<button type="button" data-z="out" aria-label="Zoom out" title="Zoom out">&minus;</button>'
                '<button type="button" data-z="reset" aria-label="Reset zoom" title="Reset zoom">&#8635;</button>'
                '<button type="button" data-z="in" aria-label="Zoom in" title="Zoom in">&plus;</button>'
                '</div>'
                '<div class="zoom-pane"><pre class="mermaid">'
                f'{html.escape(code)}</pre></div></div>')
            if len(diagrams) > 1:
                body.append(f'<figcaption>Figure {i}.{j} of {len(diagrams)} '
                            f'&mdash; {html.escape(title)}</figcaption>')
            body.append("</figure>")
        if prose.strip():
            body.append(f'<div class="cols">{md_min(prose)}</div>')
        body.append("</section>")

    contents = "".join(f'<li><a href="#s{i}">{html.escape(s[0])}</a></li>'
                       for i, s in enumerate(sections, 1))
    figure_count = sum(len(s[4]) for s in sections)

    page = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adverse Information Assistant &mdash; Process Map</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<style>{CSS}</style></head>
<body>
<div class="doc">

<header class="masthead">
  <p class="kicker">Operating map</p>
  <h1>Adverse Information Assistant</h1>
  <p class="lede">How a session actually runs, what grounds each decision, and
  where the guarantees are enforced &mdash; rather than merely requested.</p>

  <div class="pair">
    <div><h3>What the process does</h3>
      <p>Finds the reporting floor before anything else, gathers the details the
      forms actually demand without overreaching, writes in the user's own
      voice, and leaves every unresolved item visible before handoff.</p></div>
    <div><h3>What it does not do</h3>
      <p>It does not predict an outcome, decide an agency's position, tell
      anyone a matter is unreportable, or let polished prose stand in for a
      missing field.</p></div>
  </div>

  <div class="principles">
    <div><div class="n">01</div><h4>Obligation first</h4>
      <p>Reportability is settled before adjudicative context. The answer is
      &ldquo;yes&rdquo; or &ldquo;consult your security office&rdquo; &mdash;
      never a casual &ldquo;no.&rdquo;</p></div>
    <div><div class="n">02</div><h4>The user leads</h4>
      <p>New threads are followed only where the user raised them and agrees to
      widen the scope. The tool never fishes.</p></div>
    <div><div class="n">03</div><h4>Privacy is chosen</h4>
      <p>The user picks a tier governing other people's details. SSNs, dates of
      birth and classified information never enter, at any tier.</p></div>
    <div><div class="n">04</div><h4>Scripts, not promises</h4>
      <p>Instructions to the assistant are requests, not guarantees. The
      fixed checks are the only controls actually enforced.</p></div>
  </div>

  <nav class="contents"><p class="kicker">Contents</p><ol>{contents}</ol></nav>

  <p class="boundary"><strong>Boundary:</strong> Not affiliated with, endorsed
  by, or reviewed by DCSA, DOHA, ODNI, or any U.S. Government agency. The
  Government makes every adjudicative determination. This describes a proposed
  reporting-support workflow &mdash; not adjudicative or legal advice.</p>
</header>

{''.join(body)}

<p class="colophon">Reference material version 0.1.0. Wide diagrams scroll
sideways on screen and are scaled to fit when printed.</p>

</div>
<script>
  mermaid.initialize({{ startOnLoad:false, theme:'base',
    flowchart:{{ useMaxWidth:false, htmlLabels:true, curve:'basis',
                 nodeSpacing:38, rankSpacing:44 }},
    themeVariables:{{
      background:'#FDFBF7', fontSize:'12.5px',
      fontFamily:'Segoe UI, system-ui, -apple-system, sans-serif',
      primaryColor:'#F3EDE1', primaryTextColor:'#2B2723',
      primaryBorderColor:'#C3B8A2', lineColor:'#A89C8A',
      secondaryColor:'#ECE7F5', tertiaryColor:'#E4EFE6',
      mainBkg:'#F3EDE1', nodeBorder:'#C3B8A2', clusterBkg:'#F7F3EA',
      clusterBorder:'#DCD5C7', titleColor:'#2B2723',
      edgeLabelBackground:'#F5F1E9', textColor:'#2B2723'
    }} }});

  // ---------------------------------------------------------------------
  // Pan/zoom, attached after Mermaid actually finishes rendering — not on
  // a timer race. startOnLoad is off above specifically so this await is
  // meaningful: zoom setup needs a real <svg> in the DOM, and a guess at
  // "Mermaid is probably done by now" is how that silently breaks.
  // ---------------------------------------------------------------------
  function initZoom(figbox) {{
    const pane = figbox.querySelector('.zoom-pane');
    const svg = pane && pane.querySelector('svg');
    if (!svg) return; // this figure's diagram failed to render; nothing to attach to

    const MIN = 0.25, MAX = 8;
    let scale = 1, tx = 0, ty = 0;
    let panning = false, startX = 0, startY = 0, startTx = 0, startTy = 0;
    let pinchDist = null;

    function apply() {{
      svg.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
    }}
    function zoomAt(factor, clientX, clientY) {{
      const rect = pane.getBoundingClientRect();
      const px = clientX - rect.left, py = clientY - rect.top;
      const next = Math.min(MAX, Math.max(MIN, scale * factor));
      tx = px - (px - tx) * (next / scale);
      ty = py - (py - ty) * (next / scale);
      scale = next;
      apply();
    }}
    function reset() {{ scale = 1; tx = 0; ty = 0; apply(); }}

    pane.addEventListener('wheel', (e) => {{
      e.preventDefault();
      zoomAt(e.deltaY < 0 ? 1.12 : 1 / 1.12, e.clientX, e.clientY);
    }}, {{ passive: false }});

    pane.addEventListener('mousedown', (e) => {{
      panning = true; pane.classList.add('grabbing');
      startX = e.clientX; startY = e.clientY; startTx = tx; startTy = ty;
    }});
    window.addEventListener('mousemove', (e) => {{
      if (!panning) return;
      tx = startTx + (e.clientX - startX);
      ty = startTy + (e.clientY - startY);
      apply();
    }});
    window.addEventListener('mouseup', () => {{
      panning = false; pane.classList.remove('grabbing');
    }});
    pane.addEventListener('dblclick', reset);

    // Touch: one finger pans, two fingers pinch-zoom around their midpoint.
    pane.addEventListener('touchstart', (e) => {{
      if (e.touches.length === 1) {{
        panning = true;
        startX = e.touches[0].clientX; startY = e.touches[0].clientY;
        startTx = tx; startTy = ty;
      }} else if (e.touches.length === 2) {{
        panning = false;
        const [a, b] = e.touches;
        pinchDist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
      }}
    }}, {{ passive: true }});
    pane.addEventListener('touchmove', (e) => {{
      if (e.touches.length === 1 && panning) {{
        tx = startTx + (e.touches[0].clientX - startX);
        ty = startTy + (e.touches[0].clientY - startY);
        apply();
      }} else if (e.touches.length === 2 && pinchDist) {{
        const [a, b] = e.touches;
        const dist = Math.hypot(a.clientX - b.clientX, a.clientY - b.clientY);
        const mx = (a.clientX + b.clientX) / 2, my = (a.clientY + b.clientY) / 2;
        zoomAt(dist / pinchDist, mx, my);
        pinchDist = dist;
      }}
      e.preventDefault();
    }}, {{ passive: false }});
    pane.addEventListener('touchend', () => {{ panning = false; pinchDist = null; }});

    const controls = figbox.querySelector('.zoom-controls');
    controls.querySelector('[data-z="in"]').addEventListener('click', () => {{
      const r = pane.getBoundingClientRect();
      zoomAt(1.3, r.left + r.width / 2, r.top + r.height / 2);
    }});
    controls.querySelector('[data-z="out"]').addEventListener('click', () => {{
      const r = pane.getBoundingClientRect();
      zoomAt(1 / 1.3, r.left + r.width / 2, r.top + r.height / 2);
    }});
    controls.querySelector('[data-z="reset"]').addEventListener('click', reset);

    apply();
  }}

  document.addEventListener('DOMContentLoaded', async () => {{
    await mermaid.run({{ querySelector: '.mermaid' }});
    document.querySelectorAll('.figbox').forEach(initZoom);
  }});
</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} — {len(page):,} bytes, "
          f"{len(sections)} sections, "
          f"{figure_count} figures")
    for i, s in enumerate(sections, 1):
        title, _eb, hl, sf, d, _ = s
        missing = [n for n, v in (("headline", hl), ("standfirst", sf)) if not v]
        mark = f"   (MISSING metadata: {', '.join(missing)})" if missing else ""
        print(f"  {i:02d}. {title}  ({len(d)} diagram){mark}")
    print("\nOpen it by double-clicking the file. Needs internet the first "
          "time, to load the diagram renderer.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
