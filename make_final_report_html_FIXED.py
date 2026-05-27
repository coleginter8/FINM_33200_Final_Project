#!/usr/bin/env python3
"""
Convert FINM 33200 Final Project Report.pdf into a self-contained static HTML file.

Expected input filename, relative to the directory where you run the script:
    FINM 33200 Final Project Report.pdf

Output:
    FINM_33200_Final_Project_Report_static.html

Dependencies:
    pip install pymupdf

What this version fixes:
- Figures are placed by their actual PDF block order, so they stay between the same
  surrounding text as in the report instead of being appended to a section.
- Works Cited is rendered from the PDF's individual bibliography blocks as a list.
- The few formulas that PDF text extraction drops are restored as text equation blocks,
  avoiding MathJax/KaTeX rendering issues.
- Prompt text that wraps across PDF pages is merged into one prompt box.
"""

from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF

SCRIPT_VERSION = "2026-05-27 figure-order-and-bibliography-fix"

REPORT_FILE = Path("FINM 33200 Final Project Report.pdf")
OUTPUT_FILE = Path("FINM_33200_Final_Project_Report_static.html")

TITLE = "Comparative Effectiveness of StatsClaw and Base Claude Code on Financial Research Replications"
SUBTITLE = "FINM 33200 Final Project Report"
AUTHORS = "By Charlie Carvajal, Cole Ginter, Jonathon Nie, and Alex Nikolaev"

HEADING_PATTERN = re.compile(
    r"^(\d+)\.\s*(Introduction and Methodology|StatsClaw Overview|Case 1: Federal Yield Curve|Case 2:\s*Credit Default Swap Returns|Case 3 HKM Tables 2 and 3|Conclusion and Limitations|Works Cited|AI Usage Statement)\s*$"
)

EQUATIONS = {
    "eq_cds_statsclaw": "r_t = S_{t-1}/12 + (S_{t-1} - S_t) × RD_{t-1}",
    "eq_cds_claude": "r_t = S_{t-1}/12 + (S_{t-1} - S_t) × RD_{t-1}",
    "eq_capital_gain": "(S_{t-1} - S_t) × RD_{t-1}",
    "eq_ar1": "η_t = ρ_0 + ρ × η_{t-1} + u_t",
    "eq_residual": "u_t / η_{t-1}",
}

ElementKind = Literal["p", "fig", "eq"]


@dataclass
class Element:
    kind: ElementKind
    text: str = ""
    src: str = ""
    page: int | None = None


@dataclass
class Section:
    number: int
    title: str
    elements: list[Element] = field(default_factory=list)


def clean_raw_text(text: str) -> str:
    """Normalize extraction artifacts without editing report wording."""
    text = text.replace("\u200b", "")
    text = text.replace("\ufeff", "")
    text = text.replace("\xa0", " ")
    # Some PDF extractors produce headings like "4.\tCase..."; normalize spacing.
    text = re.sub(r"(?m)^(\s*\d+)\.\s+", r"\1. ", text)
    return text


def collapse_paragraph(text: str) -> str:
    """Collapse PDF line wrapping into one paragraph."""
    text = clean_raw_text(text).strip()
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_text_block_into_chunks(text: str) -> list[str]:
    """Split a PDF text block into logical chunks using blank lines."""
    text = clean_raw_text(text)
    chunks = []
    for part in re.split(r"\n\s*\n", text):
        p = collapse_paragraph(part)
        if not p:
            continue
        # Skip title page lines that are rendered separately in the HTML hero.
        if p in {TITLE, "Comparative Effectiveness of StatsClaw and Base Claude Code on", "Financial Research Replications", SUBTITLE, AUTHORS}:
            continue
        chunks.append(p)
    return chunks


def image_to_data_uri(block: dict) -> str:
    ext = str(block.get("ext", "png")).lower()
    mime = "image/jpeg" if ext in {"jpg", "jpeg"} else "image/png"
    data = block["image"]
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def is_report_figure(block: dict) -> bool:
    """Keep actual report figures but skip small formula/image artifacts."""
    return (
        block.get("type") == 1
        and int(block.get("width", 0)) >= 1000
        and int(block.get("height", 0)) >= 300
        and int(block.get("size", 0)) >= 20_000
    )


def extract_sections_in_pdf_order(pdf_path: Path) -> list[Section]:
    """Extract text and figures in actual PDF block order, grouped by section."""
    doc = fitz.open(pdf_path)
    sections: list[Section] = []
    current: Section | None = None

    try:
        for page_number, page in enumerate(doc, start=1):
            blocks = page.get_text("dict")["blocks"]
            # Sort by vertical position, then horizontal position. This is the key change:
            # images now enter the content stream exactly where they sit on the PDF page.
            blocks = sorted(blocks, key=lambda b: (round(b["bbox"][1], 1), round(b["bbox"][0], 1)))

            for block in blocks:
                if block.get("type") == 0:
                    raw = ""
                    for line in block.get("lines", []):
                        line_text = "".join(span.get("text", "") for span in line.get("spans", []))
                        raw += line_text + "\n"
                    for chunk in split_text_block_into_chunks(raw):
                        m = HEADING_PATTERN.match(chunk)
                        if m:
                            current = Section(number=int(m.group(1)), title=re.sub(r"\s+", " ", m.group(2)).strip())
                            sections.append(current)
                        elif current is not None:
                            current.elements.append(Element(kind="p", text=chunk, page=page_number))
                elif is_report_figure(block):
                    if current is not None:
                        current.elements.append(
                            Element(kind="fig", src=image_to_data_uri(block), page=page_number)
                        )
    finally:
        doc.close()

    if not sections:
        raise RuntimeError("Could not find numbered section headings in the PDF text.")

    merge_wrapped_prompt_elements(sections)
    restore_formula_elements(sections)
    return sections


def merge_wrapped_prompt_elements(sections: list[Section]) -> None:
    """Merge long prompts that wrap across PDF page breaks into one prompt box."""
    for section in sections:
        merged: list[Element] = []
        i = 0
        while i < len(section.elements):
            el = section.elements[i]
            if el.kind == "p" and i + 1 < len(section.elements) and section.elements[i + 1].kind == "p":
                nxt = section.elements[i + 1]
                # StatsClaw CDS prompt continuation.
                if (
                    el.text.startswith("Replicate the HKM (2017) CDS portfolio returns pipeline")
                    and nxt.text.startswith("validation/validation_contract.parquet")
                ):
                    merged.append(Element(kind="p", text=el.text + " " + nxt.text, page=el.page))
                    i += 2
                    continue
                # Base Claude CDS prompt continuation.
                if (
                    el.text.startswith("Replicate the HKM (2017) CDS portfolio returns pipeline")
                    and nxt.text.startswith('"[username]"')
                ):
                    merged.append(Element(kind="p", text=el.text + " " + nxt.text, page=el.page))
                    i += 2
                    continue
            merged.append(el)
            i += 1
        section.elements = merged



def restore_formula_elements(sections: list[Section]) -> None:
    """Insert equations where the PDF stores them as non-text images.

    The PDF extractor drops these formula images or turns the surrounding words into
    awkward fragments. This routine keeps the report prose intact while inserting
    text equation blocks at the same points in the flow.
    """
    for section in sections:
        out: list[Element] = []
        i = 0
        while i < len(section.elements):
            el = section.elements[i]

            # StatsClaw CDS formula: paragraph ending with the colon, followed by
            # a continuation that begins with the period left behind by the formula image.
            if (
                section.number == 4
                and el.kind == "p"
                and "protection-seller monthly return formula" in el.text
                and el.text.rstrip().endswith("Palhares (2012):")
                and i + 1 < len(section.elements)
                and section.elements[i + 1].kind == "p"
                and section.elements[i + 1].text.startswith(". Through this formula")
            ):
                out.append(el)
                out.append(Element(kind="eq", text=EQUATIONS["eq_cds_statsclaw"], page=el.page))
                cont = section.elements[i + 1].text
                cont = re.sub(r"^\.\s*", "", cont)
                out.append(Element(kind="p", text=cont, page=section.elements[i + 1].page))
                i += 2
                continue

            # Base Claude CDS formula is split across four text fragments because
            # the equation image interrupts the line.
            if (
                section.number == 4
                and el.kind == "p"
                and el.text.endswith("The agent also correctly applied the Palhares")
                and i + 3 < len(section.elements)
                and section.elements[i + 1].kind == "p"
                and section.elements[i + 1].text.startswith("(2013) seller-of-protection return formula:")
                and section.elements[i + 2].kind == "p"
                and "capital gain of" in section.elements[i + 2].text
                and section.elements[i + 3].kind == "p"
                and section.elements[i + 3].text.startswith("using the lagged risky duration")
            ):
                prefix = el.text + " " + section.elements[i + 1].text
                prefix = prefix.replace(": , with", ":")
                prefix = prefix.replace(", with", "")
                carry = section.elements[i + 2].text
                if carry.startswith("the carry term"):
                    carry = "with " + carry
                out.append(Element(kind="p", text=prefix, page=el.page))
                out.append(Element(kind="eq", text=EQUATIONS["eq_cds_claude"], page=el.page))
                out.append(Element(kind="p", text=carry, page=section.elements[i + 2].page))
                out.append(Element(kind="eq", text=EQUATIONS["eq_capital_gain"], page=section.elements[i + 2].page))
                out.append(section.elements[i + 3])
                i += 4
                continue

            # HKM AR(1) equation and residual expression.
            if (
                section.number == 5
                and el.kind == "p"
                and "successfully run the regression:" in el.text
                and el.text.rstrip().endswith("regression: and")
                and i + 1 < len(section.elements)
                and section.elements[i + 1].kind == "p"
                and section.elements[i + 1].text.startswith("extract the appropriate residuals")
            ):
                before = re.sub(r"\s+and$", "", el.text)
                cont = section.elements[i + 1].text
                cont = re.sub(r"^extract", "and extract", cont)
                # Split after residuals, insert residual equation, then continue.
                m = re.match(r"(and extract the appropriate residuals)\s*\.\s*(However, beyond this,.*)", cont)
                out.append(Element(kind="p", text=before, page=el.page))
                out.append(Element(kind="eq", text=EQUATIONS["eq_ar1"], page=el.page))
                if m:
                    out.append(Element(kind="p", text=m.group(1), page=section.elements[i + 1].page))
                    out.append(Element(kind="eq", text=EQUATIONS["eq_residual"], page=section.elements[i + 1].page))
                    out.append(Element(kind="p", text=m.group(2), page=section.elements[i + 1].page))
                else:
                    out.append(Element(kind="p", text=cont, page=section.elements[i + 1].page))
                    out.append(Element(kind="eq", text=EQUATIONS["eq_residual"], page=section.elements[i + 1].page))
                i += 2
                continue

            out.append(el)
            i += 1
        section.elements = out

def is_prompt(text: str) -> bool:
    return text.startswith(
        (
            "Construct the GSW (2007) daily zero-coupon Treasury yield curve dataset.",
            "replicate the dataset and paper located in fed_yeild curve replication/200628pap-2.pdf",
            "Replicate the HKM (2017) CDS portfolio returns pipeline",
            "Replicate Tables 2 and 3 only from He, Kelly & Manela (2017)",
        )
    )


def equation_html(text: str) -> str:
    return f'<div class="equation plain-equation"><code>{html.escape(text)}</code></div>'


def paragraph_to_html(text: str) -> str:
    """Render paragraphs and restore formula placeholders that disappeared in PDF extraction."""
    escaped = html.escape(text)

    # 1. StatsClaw CDS formula.
    escaped = re.sub(
        r"(StatsClaw correctly identified the protection-seller monthly return formula from He, Kelly, and Manela \(2017\) and Palhares \(2012\):)\s*\.\s*(Through this formula)",
        r"\1</p>" + equation_html(EQUATIONS["eq_cds_statsclaw"]) + r"<p>\2",
        escaped,
    )

    # 2. Base Claude CDS formula.
    escaped = re.sub(
        r"(The agent also correctly applied the Palhares \(2013\) seller-of-protection return formula:)\s*,\s*(with the carry term)",
        r"\1</p>" + equation_html(EQUATIONS["eq_cds_claude"]) + r"<p>\2",
        escaped,
    )

    # 3. Capital gain expression.
    escaped = re.sub(
        r"(and a capital gain of)\s*(using the lagged risky duration)",
        r"\1</p>" + equation_html(EQUATIONS["eq_capital_gain"]) + r"<p>\2",
        escaped,
    )

    # 4 and 5. HKM AR(1) regression and residual expression.
    escaped = re.sub(
        r"(but statsClaw was able to successfully run the regression:)\s*and\s*(extract the appropriate residuals)",
        r"\1</p>" + equation_html(EQUATIONS["eq_ar1"]) + r"<p>\2",
        escaped,
    )
    escaped = re.sub(
        r"(extract the appropriate residuals)\s*\.\s*(However, beyond this)",
        r"\1</p>" + equation_html(EQUATIONS["eq_residual"]) + r"<p>\2",
        escaped,
    )

    if "</p>" in escaped or '<div class="equation' in escaped:
        return "<p>" + escaped + "</p>"
    if is_prompt(text):
        return f'<div class="literal"><p>{escaped}</p></div>'
    return f"<p>{escaped}</p>"


def figure_to_html(element: Element) -> str:
    caption = f"Figure from report page {element.page}"
    return (
        '<figure class="report-figure">'
        f'<img class="figure-img" src="{element.src}" alt="{html.escape(caption)}"/>'
        f'<figcaption>{html.escape(caption)}</figcaption>'
        "</figure>"
    )


def works_cited_html(section: Section) -> str:
    entries = [el.text for el in section.elements if el.kind == "p"]
    # Fallback for unexpected extractor behavior: split a single collapsed paragraph back into entries.
    if len(entries) == 1:
        text = entries[0]
        starts = [
            "Bejarano, Jeremiah.",
            "FTSFR. n.d. cds_returns.",
            "FTSFR. n.d. fed_yield_curve.",
            "Gürkaynak, Refet S.",
            "He, Zhiguo, Bryan Kelly, and Asaf Manela.",
            "Olson, Matt.",
            "Palhares, Diogo.",
        ]
        positions = sorted((text.find(s), s) for s in starts if text.find(s) >= 0)
        if len(positions) > 1:
            entries = []
            for j, (idx, _) in enumerate(positions):
                end = positions[j + 1][0] if j + 1 < len(positions) else len(text)
                entries.append(text[idx:end].strip())

    items = "\n".join(f"<li>{html.escape(e)}</li>" for e in entries if e.strip())
    return f'<ul class="works-cited">{items}</ul>'


def section_to_html(section: Section) -> str:
    if section.number == 7:
        body = works_cited_html(section)
    else:
        chunks = []
        for el in section.elements:
            if el.kind == "p":
                chunks.append(paragraph_to_html(el.text))
            elif el.kind == "fig":
                chunks.append(figure_to_html(el))
            elif el.kind == "eq":
                chunks.append(equation_html(el.text))
        body = "\n".join(chunks)

    return f'''
<section class="page" data-title="{html.escape(section.title)}" id="section-{section.number}">
  <div class="section-kicker">Section {section.number}</div>
  <h1>{section.number}. {html.escape(section.title)}</h1>
  {body}
</section>'''


def build_html(sections: list[Section]) -> str:
    nav_links = "\n".join(
        f'<a data-page="section-{s.number}" href="#section-{s.number}"><span class="nav-num">{s.number}.</span>{html.escape(s.title)}</a>'
        for s in sections
    )
    mobile_options = "\n".join(
        f'<option value="section-{s.number}">{s.number}. {html.escape(s.title)}</option>' for s in sections
    )
    section_markup = "\n".join(section_to_html(s) for s in sections)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<meta name="generator" content="make_final_report_html.py {html.escape(SCRIPT_VERSION)}"/>
<title>{html.escape(TITLE)}</title>
<style>
:root{{--bg:#fff;--surface:#f8f9fb;--surface-2:#f1f3f7;--text:#1f2328;--muted:#6b7280;--border:#d8dee9;--accent:#2563eb;--accent-dark:#1d4ed8;--code-bg:#f6f8fa;--sidebar:#fbfbfd;--shadow:0 10px 30px rgba(15,23,42,.08);--content:820px}}
*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:var(--text);background:var(--bg);line-height:1.65}}a{{color:var(--accent);text-decoration:none}}a:hover{{text-decoration:underline}}
.app{{display:grid;grid-template-columns:300px minmax(0,1fr) 250px;min-height:100vh}}.sidebar{{position:sticky;top:0;align-self:start;height:100vh;overflow:auto;border-right:1px solid var(--border);background:var(--sidebar);padding:1.25rem 1rem}}.brand{{display:flex;align-items:center;gap:.7rem;font-weight:700;color:#111827;margin-bottom:1.25rem}}.brand-mark{{width:34px;height:34px;border-radius:8px;background:linear-gradient(135deg,#111827,#2563eb);box-shadow:var(--shadow)}}.brand small{{display:block;font-weight:500;color:var(--muted);font-size:.78rem;margin-top:.1rem}}.search-note{{font-size:.78rem;color:var(--muted);border:1px solid var(--border);background:#fff;padding:.7rem;border-radius:10px;margin-bottom:1rem}}nav.section-nav{{display:flex;flex-direction:column;gap:.1rem}}nav.section-nav a{{color:#374151;padding:.5rem .6rem;border-radius:8px;display:flex;gap:.55rem;align-items:flex-start;font-size:.92rem;line-height:1.35}}nav.section-nav a.active{{background:#eaf2ff;color:#0f3b80;font-weight:650}}.nav-num{{color:var(--muted);font-variant-numeric:tabular-nums;min-width:1.45rem}}
main{{max-width:var(--content);width:100%;margin:0 auto;padding:2.25rem 2rem 5rem}}.hero{{border-bottom:1px solid var(--border);padding-bottom:2rem;margin-bottom:2rem}}.breadcrumb{{color:var(--muted);font-size:.85rem;margin-bottom:1rem}}.hero h1{{font-family:Georgia,"Times New Roman",serif;font-size:clamp(2rem,4.6vw,3.25rem);line-height:1.12;margin:.25rem 0 .75rem;letter-spacing:-.02em}}.hero .subtitle{{font-size:1.08rem;color:#374151;margin:0}}.hero .authors{{color:var(--muted);margin-top:.4rem}}
.page{{display:none;animation:fade .18s ease-in}}.page.active{{display:block}}@keyframes fade{{from{{opacity:.25;transform:translateY(3px)}}to{{opacity:1;transform:none}}}}.section-kicker{{color:var(--accent-dark);font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:.77rem;margin-bottom:.35rem}}.page h1{{font-family:Georgia,"Times New Roman",serif;font-size:2.15rem;line-height:1.18;margin:.1rem 0 1.4rem;padding-bottom:.7rem;border-bottom:1px solid var(--border)}}.page p{{margin:0 0 1.05rem;font-size:1rem}}.works-cited{{margin:0;padding-left:1.35rem}}.works-cited li{{margin:0 0 .85rem;padding-left:.25rem;line-height:1.55}}
.literal{{background:var(--code-bg);border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:10px;padding:1rem 1.05rem;margin:1.15rem 0;overflow-wrap:anywhere}}.literal p{{font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;white-space:normal;font-size:.9rem;margin:0;line-height:1.55}}
.report-figure{{margin:1.75rem 0 2rem}}.figure-img{{display:block;max-width:100%;height:auto;border:1px solid var(--border);border-radius:12px;background:white;box-shadow:var(--shadow)}}figcaption{{color:var(--muted);font-size:.82rem;margin-top:.45rem;text-align:center}}
.equation.plain-equation{{display:block;background:#fff!important;color:#111827!important;border:1px solid var(--border);border-radius:10px;padding:.75rem 1rem;margin:1.05rem auto 1.25rem;text-align:center;box-shadow:0 4px 18px rgba(15,23,42,.04);overflow-x:auto}}.equation.plain-equation code{{display:inline-block;background:transparent!important;color:#111827!important;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,"Liberation Mono",monospace;font-size:1.02rem;line-height:1.55;white-space:normal}}
.toc{{position:sticky;top:0;height:100vh;overflow:auto;border-left:1px solid var(--border);padding:1.25rem 1rem;color:var(--muted);background:#fff}}.toc h2{{font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:#4b5563;margin:0 0 .7rem}}.toc a{{display:block;color:var(--muted);font-size:.86rem;padding:.3rem 0}}.toc a.active{{color:var(--accent-dark);font-weight:650}}.topbar{{display:none;position:sticky;top:0;z-index:10;background:rgba(255,255,255,.96);border-bottom:1px solid var(--border);padding:.7rem 1rem}}.topbar select{{width:100%;padding:.55rem;border:1px solid var(--border);border-radius:8px;background:white}}
.pager{{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--border);display:flex;justify-content:space-between;gap:1rem}}.pager a{{border:1px solid var(--border);border-radius:10px;padding:.7rem .85rem;color:#374151;background:#fff;max-width:49%}}.pager a:hover{{background:var(--surface);text-decoration:none}}
@media(max-width:1100px){{.app{{grid-template-columns:260px minmax(0,1fr)}}.toc{{display:none}}}}@media(max-width:820px){{.app{{display:block}}.sidebar{{display:none}}.topbar{{display:block}}main{{padding:1.25rem 1.1rem 4rem}}.hero h1{{font-size:2.1rem}}.page h1{{font-size:1.7rem}}}}@media print{{.sidebar,.toc,.topbar,.pager{{display:none!important}}.app{{display:block}}main{{max-width:none;padding:0}}.page{{display:block!important;page-break-before:always}}.hero{{page-break-after:always}}}}
</style>
</head>
<body>
<div class="topbar"><select aria-label="Choose section" id="mobile-nav">{mobile_options}</select></div>
<div class="app">
  <aside class="sidebar">
    <div class="brand"><div class="brand-mark"></div><div>FINM 33200<small>Final Project Report</small></div></div>
    <div class="search-note">Static HTML version. Use the section links to move between pages.</div>
    <nav aria-label="Sections" class="section-nav">{nav_links}</nav>
  </aside>
  <main>
    <div class="hero">
      <div class="breadcrumb">Generative and Agentic AI for Finance / Final Project</div>
      <h1>{html.escape(TITLE)}</h1>
      <p class="subtitle">{html.escape(SUBTITLE)}</p>
      <p class="authors">{html.escape(AUTHORS)}</p>
    </div>
    {section_markup}
  </main>
  <aside class="toc"><h2>On this page</h2>{nav_links}</aside>
</div>
<script>
(function(){{
  const pages = Array.from(document.querySelectorAll('.page'));
  const links = Array.from(document.querySelectorAll('[data-page]'));
  const select = document.getElementById('mobile-nav');
  function show(id){{
    if(!id || !document.getElementById(id)) id = pages[0].id;
    pages.forEach(p => p.classList.toggle('active', p.id === id));
    links.forEach(a => a.classList.toggle('active', a.dataset.page === id));
    if(select) select.value = id;
    window.scrollTo({{top:0, behavior:'instant'}});
  }}
  links.forEach(a => a.addEventListener('click', e => {{ e.preventDefault(); const id=a.dataset.page; history.pushState(null,'','#'+id); show(id); }}));
  if(select) select.addEventListener('change', e => {{ const id=e.target.value; history.pushState(null,'','#'+id); show(id); }});
  window.addEventListener('popstate', () => show(location.hash.slice(1)));
  show(location.hash.slice(1));
}})();
</script>
</body>
</html>'''


def main() -> None:
    if not REPORT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {REPORT_FILE!s}. Put this script in the same directory as the report PDF, "
            "or change REPORT_FILE at the top of the script."
        )

    sections = extract_sections_in_pdf_order(REPORT_FILE)
    output = build_html(sections)
    OUTPUT_FILE.write_text(output, encoding="utf-8")
    print(f"Using script version: {SCRIPT_VERSION}")
    print(f"Wrote {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
