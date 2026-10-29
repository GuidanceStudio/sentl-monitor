"""`monitor.py pdf`: a report as a print-ready HTML page and, when a PDF engine is on the machine, as a PDF.

The renderer reads the markdown the reports use (headings, paragraphs, lists, tables, quotes, bold, italic,
code spans, links, rules) and nothing else. The engine is whichever of chromium, google-chrome, weasyprint
or wkhtmltopdf that is installed and writes the file; the skill installs none.
"""

import html
import re
import shutil
import subprocess
from pathlib import Path

from .common import Refused, Study

ENGINES = (
    ("weasyprint", ["{html}", "{pdf}"]),
    ("chromium", ["--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("chromium-browser", ["--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("google-chrome", ["--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("wkhtmltopdf", ["{html}", "{pdf}"]),
    # Where the browser's sandbox is unavailable (a container, a restricted user namespace), the same page,
    # which holds no script, is printed without it.
    ("chromium", ["--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("chromium-browser", ["--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("google-chrome", ["--headless", "--disable-gpu", "--no-sandbox", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
)

STYLE = """
@page { size: A4; margin: 18mm 16mm; }
body { font: 11pt/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1c1c1c; max-width: 46em; margin: 0 auto; }
h1 { font-size: 20pt; line-height: 1.25; margin: 0 0 .4em; }
h2 { font-size: 14pt; margin: 1.6em 0 .4em; border-bottom: 1px solid #d0d0d0; padding-bottom: .2em; break-after: avoid; }
h3 { font-size: 12pt; margin: 1.2em 0 .3em; break-after: avoid; }
p, ul, ol, table, blockquote { margin: .6em 0; }
blockquote { border-left: 3px solid #b8b8b8; padding: .1em 0 .1em 1em; color: #333; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 10pt; break-inside: avoid; }
th, td { border: 1px solid #d0d0d0; padding: .3em .5em; text-align: left; vertical-align: top; }
th { background: #f2f2f2; }
code { font: 10pt ui-monospace, Menlo, Consolas, monospace; background: #f2f2f2; padding: 0 .2em; }
hr { border: 0; border-top: 1px solid #d0d0d0; margin: 1.2em 0; }
"""


def inline(text):
    """Escape a line and apply code spans, links, bold and italic."""
    spans = []

    def keep(m):
        spans.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep, text)
    text = html.escape(text, quote=False)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: spans[int(m.group(1))], text)


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table(lines):
    head, body = _cells(lines[0]), [_cells(line) for line in lines[2:]]
    rows = "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>" for r in body)
    return ("<table><thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def render(markdown):
    """The report's markdown as the body of an HTML page."""
    lines = markdown.replace("\r\n", "\n").split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
        elif re.match(r"^#{1,6}\s", line):
            level = len(line) - len(line.lstrip("#"))
            out.append(f"<h{level}>{inline(line[level:].strip())}</h{level}>")
            i += 1
        elif re.match(r"^(-{3,}|\*{3,})\s*$", line):
            out.append("<hr>")
            i += 1
        elif line.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            out.append(_table(lines[i:j]))
            i = j
        elif line.startswith(">"):
            j = i
            while j < len(lines) and lines[j].startswith(">"):
                j += 1
            out.append("<blockquote><p>" + "<br>".join(inline(l.lstrip(">").strip()) for l in lines[i:j]) + "</p></blockquote>")
            i = j
        elif re.match(r"^\s*([-*]|\d+\.)\s", line):
            ordered = bool(re.match(r"^\s*\d+\.\s", line))
            tag, j, items = ("ol" if ordered else "ul"), i, []
            while j < len(lines) and re.match(r"^\s*([-*]|\d+\.)\s", lines[j]):
                items.append(f"<li>{inline(re.sub(r'^\s*([-*]|\d+\.)\s+', '', lines[j]))}</li>")
                j += 1
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
            i = j
        else:
            j = i
            while j < len(lines) and lines[j].strip() and not re.match(r"^(#{1,6}\s|>|\s*([-*]|\d+\.)\s|\s*\|)", lines[j]):
                j += 1
            out.append("<p>" + "<br>".join(inline(l.strip()) for l in lines[i:max(j, i + 1)]) + "</p>")
            i = max(j, i + 1)
    return "\n".join(out)


def page(markdown, language="en"):
    body = render(markdown)
    title = re.search(r"<h1>(.*?)</h1>", body)
    name = re.sub(r"<[^>]+>", "", title.group(1)) if title else "Report"
    return (f'<!doctype html>\n<html lang="{html.escape(language)}"><head><meta charset="utf-8">'
            f"<title>{name}</title><style>{STYLE}</style></head><body>\n{body}\n</body></html>\n")


def _latest(folder):
    found = sorted(p for p in folder.path("reports").glob("*.md")
                   if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", p.name))
    if not found:
        raise Refused("no final report in reports/: run `report` (or `snapshot`) first")
    return found[-1]


def share_name(folder, study, date):
    """`<Subject> + Sentl.ai - monitoring report (<start> to <end>)`: what the recipient sees of the file."""
    subject = ((study.get("subject") or {}).get("label") or "").strip()
    entry = next((e for e in folder.reports() if e["date"] == date), None)
    period = entry.get("period") if entry else None
    span = f"{period['from'][:10]} to {period['to'][:10]}" if period else date
    name = f"{subject} + Sentl.ai - monitoring report ({span})" if subject else f"Sentl.ai - monitoring report ({span})"
    return " ".join(re.sub(r'[/\\:*?"<>|]', " ", name).split())


def _share(folder, study, source, target, pdf):
    """Copy the page and the PDF made for `source` to reports/share/ under the descriptive name."""
    name = share_name(folder, study, source.stem)
    shared = folder.path("reports", "share")
    shared.mkdir(exist_ok=True)
    for made in (target, pdf):
        if made.exists():
            shutil.copyfile(made, shared / f"{name}{made.suffix}")
    return shared / f"{name}{'.pdf' if pdf.exists() else '.html'}"


def write(root, date=None, engines=ENGINES):
    """Write reports/<date>.html and, with a PDF engine on the path, reports/<date>.pdf; the copies to send
    are written to reports/share/ under a descriptive name."""
    message = _write(root, date, engines)
    folder = Study(root)
    source = folder.path("reports", f"{date}.md") if date else _latest(folder)
    study = folder.study if folder.path("study.json").exists() else {}
    shared = _share(folder, study, source, source.with_suffix(".html"), source.with_suffix(".pdf"))
    return f"{message} To send: {shared}"


def _write(root, date, engines):
    folder = Study(root)
    source = folder.path("reports", f"{date}.md") if date else _latest(folder)
    if not source.exists():
        raise Refused(f"{source} not found: run `report` first")
    study = folder.study if folder.path("study.json").exists() else {}
    target = source.with_suffix(".html")
    target.write_text(page(source.read_text(encoding="utf-8"), study.get("report_language") or "en"), encoding="utf-8")
    pdf = source.with_suffix(".pdf")
    failures = []
    for name, template in engines:
        exe = shutil.which(name)
        if not exe:
            continue
        cmd = [exe] + [a.format(html=str(target), pdf=str(pdf), url=target.resolve().as_uri()) for a in template]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            failures.append(f"{name} took more than 3 minutes")
            continue
        if done.returncode == 0 and pdf.exists():
            return f"Wrote {target} and {pdf} (engine: {name})."
        pdf.unlink(missing_ok=True)
        failures.append(f"{name}: {' '.join((done.stderr or done.stdout).split())[:160]}")
    if failures:
        return (f"Wrote {target}. No installed PDF engine wrote the PDF ({'; '.join(failures)}). Open the page in a "
                "browser and print it to PDF.")
    return (f"Wrote {target}. No PDF engine (weasyprint, chromium, google-chrome, wkhtmltopdf) is on this machine: "
            "open the page in a browser and print it to PDF, or install one and run this command again.")
