"""`deck`: one period as one short slide deck for whoever decides what to do about it.

The code places each question in a block by its type and draws every tile, chart and table from the period; the
writer fills only the text of `reports/<date>.deck.json`, which `check` reads against the period (ARCHITECTURE.md
§The deck). The page holds no script and no network reference, like the report's.
"""

import html
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path

from . import pdf as report_pdf
from . import theme as sentl_theme
from .charts import span
from .check import (ELLIPSIS, _allowed, _figures, _pieces, _plain, _quoted_in, _ratio, _shown, _stops_matching, _unquote,
                    leaks)
from .common import Refused, Study, fmt_decimal, load_json, match_key, round_half_up, write_json, write_text
from .i18n import DECK
from .insights import fact_terms, tight
from .method import measured
from .period import Reader, _answers_to, _authors, _runs_of

SCHEMA = "sentl-monitor/deck@1"
BLOCKS = ("reach", "description", "facts")
CLASSES = ("not_named", "named_by_name_only", "passed_over", "no_information", "named_with_warning", "wrong_fact",
           "confused", "holds")
TODO = "[[...]]"
MAX_ACTIONS, MAX_POINTS, MAX_SLIDES, MAX_EXCERPTS, MAX_ROWS, MAX_WORDS = 5, 4, 11, 2, 8, 40
# The characters each text may hold for its slide to stay on one page.
LIMITS = {"title": 125, "point": 175, "read": 210, "what": 175, "rests_on": 70, "read_next": 70, "limit": 170, "ask": 120}
SCORING = re.compile(r"\b(giudic\w*|judge\w*|letture|readings?|instabil\w*|unstable)\b", re.I)
SENTENCE_START = re.compile(r"(?:^|[.!?:;]|(?:^|\s)(?:[-•]|\d+[.)]))\s*$")
SENTENCE_END = re.compile(r"[.!?:;…]$")
# The printers a deck takes: the page lays its slides out with flex and grid, which wkhtmltopdf does not read.
ENGINES = tuple(e for e in report_pdf.ENGINES if e[0] not in ("weasyprint", "wkhtmltopdf"))
ENGINES += tuple(e for e in report_pdf.ENGINES if e[0] == "weasyprint")

STYLE = """
:root { --sl-good: #2F6F8F; --sl-mid: #C4C9D1; }
@page { size: 13.333in 7.5in; margin: 0; }
html, body { margin: 0; padding: 0; background: #fff; }
body { font: 20px/1.4 var(--sl-font); color: var(--sl-text); -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.slide { box-sizing: border-box; width: 100%; min-height: calc(7.5in - 1px); padding: 38px 56px 22px; display: flex;
  flex-direction: column; gap: 16px; break-after: page; }
.slide:last-of-type { break-after: auto; }
h1 { font-size: 31px; line-height: 1.2; color: var(--sl-deep); margin: 0; font-weight: 700; }
.read { margin: 0; font-size: 20px; }
.foot { margin-top: auto; padding-top: 8px; display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; color: var(--sl-muted); border-top: 1px solid var(--sl-line); }
.foot img { height: 16px; vertical-align: -3px; margin-right: 6px; }
.cover { padding: 0; flex-direction: row; gap: 0; }
.band { width: 34px; background: var(--sl-primary); }
.cover-body { flex: 1; padding: 64px 72px; display: flex; flex-direction: column; justify-content: center; gap: 22px; }
.cover-body img { height: 58px; width: auto; align-self: flex-start; margin-bottom: 26px; }
.cover h1 { font-size: 58px; line-height: 1.12; }
.cover-kind { font-size: 26px; color: var(--sl-text); }
.cover-line { font-size: 22px; color: var(--sl-muted); }
.tiles { display: flex; gap: 20px; }
.tile { flex: 1; background: var(--sl-tint); border-radius: 10px; padding: 16px 20px; display: flex; flex-direction: column; gap: 4px; }
.tile-head { font-size: 16px; font-weight: 700; color: var(--sl-deep); }
.tile-fig { font-size: 50px; line-height: 1.1; font-weight: 700; }
.tile-fig small { font-size: 26px; font-weight: 600; color: var(--sl-muted); }
.tile-row { font-size: 21px; font-weight: 700; }
.tile-row span { font-size: 15px; font-weight: 400; color: var(--sl-muted); }
.tile-cap { font-size: 16px; line-height: 1.3; color: var(--sl-muted); }
.points { margin: 0; padding: 0 0 0 24px; flex: 1; display: flex; flex-direction: column; justify-content: space-evenly; gap: 6px; }
.points li { font-size: 21px; line-height: 1.32; }
table { border-collapse: collapse; width: 100%; font-size: 15.5px; line-height: 1.3; }
th { text-align: left; font-size: 14px; background: var(--sl-tint); color: var(--sl-deep); padding: 8px 10px; }
td { padding: 9px 10px; border-bottom: 1px solid var(--sl-line); vertical-align: top; }
td.num { font-weight: 700; text-align: center; }
td.class { font-weight: 700; }
.actions table { font-size: 16px; table-layout: fixed; }
.actions th { font-size: 14.5px; }
.actions td { padding: 7px 10px; }
.actions th:nth-child(1), .actions th:nth-child(6) { width: 44px; }
.actions th:nth-child(2) { width: 136px; }
.actions th:nth-child(3) { width: 38%; }
.sources table { font-size: 17px; }
.sources th { font-size: 15px; }
.sources td { padding: 16px 10px; }
.sources .small-meter { height: 12px; }
.chart { flex: 1; display: flex; flex-direction: column; gap: 8px; justify-content: center; }
.legend { display: flex; gap: 22px; font-size: 14px; color: var(--sl-muted); }
.legend i { display: inline-block; width: 13px; height: 13px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.rows { display: grid; column-gap: 18px; row-gap: 9px; align-items: center; font-size: 17px; line-height: 1.25; }
.reach-rows { grid-template-columns: 290px 1fr 84px 340px; }
.description-rows { grid-template-columns: 330px 1fr 92px; }
.facts-rows { grid-template-columns: 440px 1fr 92px 92px; }
.long { font-size: 15px; }
.head { font-size: 14px; font-weight: 600; color: var(--sl-muted); }
.group { grid-column: 1 / -1; font-size: 15px; font-weight: 700; color: var(--sl-deep); margin-top: 4px; }
.fig { font-weight: 700; white-space: nowrap; }
.foils { font-size: 15px; color: var(--sl-muted); }
.bar { display: flex; gap: 2px; height: 28px; }
.few .bar, .few .meter { height: 44px; }
.dense { row-gap: 5px; font-size: 16px; }
.dense .bar, .dense .meter { height: 22px; }
.seg { display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; overflow: hidden; min-width: 0; }
.seg:first-child { border-radius: 4px 0 0 4px; }
.seg:last-child { border-radius: 0 4px 4px 0; }
.seg:only-child { border-radius: 4px; }
.good { background: var(--sl-good); color: #fff; }
.mid { background: var(--sl-mid); color: var(--sl-text); }
.low { background: var(--sl-primary); color: var(--sl-text); }
.meter { height: 28px; background: var(--sl-line); border-radius: 4px; overflow: hidden; }
.meter span { display: block; height: 100%; background: var(--sl-primary); border-radius: 0 4px 4px 0; }
.small-meter { height: 10px; margin-top: 5px; }
.quotes { display: flex; gap: 20px; }
.quote { flex: 1; margin: 0; padding: 2px 0 2px 14px; border-left: 3px solid var(--sl-primary); }
.quote blockquote { margin: 0 0 5px; font-size: 16px; line-height: 1.3; }
.quote figcaption { font-size: 13px; line-height: 1.3; color: var(--sl-muted); }
.strip { background: var(--sl-tint); border-radius: 8px; padding: 9px 14px; font-size: 16.5px; line-height: 1.3; }
.strip b { color: var(--sl-deep); }
.method-cols { display: flex; gap: 28px; flex: 1; }
.method-cols > div { flex: 1; }
h2 { font-size: 17px; color: var(--sl-deep); margin: 0 0 4px; }
.method-cols p, .method-cols ul { font-size: 16px; line-height: 1.32; margin: 0 0 12px; }
.method-cols ul { padding-left: 18px; }
"""


def esc(value):
    return html.escape(str(value), quote=False)


# --- the blocks -------------------------------------------------------------

def _short(name, subject):
    """A project's name with the subject it opens on taken off: the deck is about the subject already."""
    return re.sub(rf"^{re.escape(subject)}\s*[·:–-]\s*", "", name)


def _block(study, reader, text, scope):
    """The block a question belongs to. A question naming no subject measures whether the subject is
    found, even when it has recorded facts; a category or a method has no presence to measure."""
    kind = (study.get("subject") or {}).get("kind")
    if not reader.position(text) and kind not in ("category", "method"):
        return "reach"
    return "facts" if scope.get("facts") else "description"


def _row(project, dimension, label, items):
    cells = [scope["total"] for _, scope in items]
    judged = sum(c["judged"] for c in cells)
    foils = Counter()
    for c in cells:
        foils.update(c["foils"])
    figure = judged and all(c["figure"] for c in cells)
    return {"project": project, "dimension": dimension, "label": label, "judged": judged,
            "named": sum(c["presence"]["named"] for c in cells), "given": sum(c["presence"]["given"] for c in cells),
            "bands": {k: sum(c["bands"][k] for c in cells) for k in ("1-2", "3", "4-5")},
            "mean": sum(c["mean"] * c["judged"] for c in cells if c["mean"] is not None) / judged if figure else None,
            "foils": sorted(foils.items(), key=lambda kv: (-kv[1], kv[0]))[:3]}


def _fact_row(project, dimension, question, scope):
    c = scope["facts"]["total"]
    total = scope["total"]
    return {"project": project, "dimension": dimension, "label": question["text"], "given": c["given"],
            "current": c["current_only"] + c["both"], "outdated": c["outdated_only"], "silent": c["given"] - c["stating"],
            "mean": total["mean"] if total["figure"] else None}


def _measure(key, row):
    return {"reach": (row.get("named"), row.get("given")), "facts": (row.get("current"), row.get("given")),
            "description": ((row.get("bands") or {}).get("4-5"), row.get("judged"))}[key]


def _block_figures(key, rows, same_audience):
    """The figure of a block, one per project: a count across audiences says nothing, so the projects
    are added up only when the deck says they address the same audience and market."""
    groups = {}
    for row in rows:
        group = groups.setdefault(None if same_audience else row["project"], [0, 0])
        a, b = _measure(key, row)
        group[0] += a
        group[1] += b
    return [{"project": project, "a": a, "b": b} for project, (a, b) in groups.items()]


def _sources(responses, reader):
    out = _authors(responses, reader)
    domains = Counter(d for r in responses for d in {s["domain"] for s in r["sources"] if s["domain"]})
    top = sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    return {**out, "domains": [{"domain": d, "answers": n, "author": reader.author(d)} for d, n in top]}


def _assistant(model, names):
    return (names.get(model) or model).split(": ", 1)[-1]


def build_model(folder, study, period, doc=None):
    """What the deck draws, from the period: each block's rows, figures and sources, the method table."""
    doc = doc or {}
    moved = doc.get("moved") or {}
    reader, subject = Reader(study), study["subject"]["label"]
    names = period.get("names") or {}
    blocks = {b: {"rows": [], "questions": [], "placed": [], "responses": []} for b in BLOCKS}
    method, cache = [], {}

    def run_of(key, run_id):
        if (key, run_id) not in cache:
            cache[(key, run_id)] = folder.run(key, run_id)
        return cache[(key, run_id)]

    for proj, dims in measured(study, period):
        key, part = proj["key"], period["projects"][proj["key"]]
        runs, name = _runs_of(period, key, run_of), _short(proj["name"], subject)
        for d in dims:
            entry = part["dimensions"][d["key"]]
            here = {b: [] for b in BLOCKS}
            for q in d["questions"]:
                scope = entry["questions"][q["key"]]
                if "foils" not in scope["total"]:
                    raise Refused(f"the period of {period['date']} was built before the deck's figures: "
                                  f"run period --date {period['date']} again")
                block = moved.get(q["key"]) or _block(study, reader, q["text"], scope)
                here[block].append((q, scope))
                blocks[block]["placed"].append({"key": q["key"], "text": q["text"], "dimension": d["name"],
                                                "names_subject": bool(reader.position(q["text"]))})
                blocks[block]["responses"] += _answers_to(runs, q["key"])
                if scope.get("facts") and (block == "facts" or scope["facts"]["total"]["stating"]):
                    blocks["facts"]["rows"].append(_fact_row(name, d["name"], q, scope))
            for b in ("reach", "description"):
                if here[b]:
                    blocks[b]["rows"].append(_row(name, d["name"], d["name"], here[b]))
                    blocks[b]["questions"] += [_row(name, d["name"], q["text"], [(q, s)]) for q, s in here[b]]
        settings = (period.get("settings") or {}).get(key) or {}
        method.append({"name": name, "questions": sum(len(d["questions"]) for d in dims),
                       "assistants": [_assistant(m, names) for m in settings.get("models") or part["by_model"]],
                       "answers": part["total"]["received"], "schedule": settings.get("schedule")})
    for key, block in blocks.items():
        block["figures"] = _block_figures(key, block["rows"], doc.get("same_audience"))
        block["sources"] = _sources(block.pop("responses"), reader)
    assistants = {a for row in method for a in row["assistants"]}
    return {"blocks": blocks, "method": method, "subject": subject,
            "totals": {"questions": sum(r["questions"] for r in method), "assistants": len(assistants),
                       "answers": sum(r["answers"] for r in method)}}


def present(m):
    return [b for b in BLOCKS if m["blocks"][b]["rows"]]


# --- what the writer fills --------------------------------------------------

def _latest(folder):
    days = sorted(p.stem for p in folder.path("history", "periods").glob("*.json")
                  if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem) and not load_json(p).get("rebuilt"))
    if not days:
        raise Refused("no period yet: run period first")
    return days[-1]


def load(root, date=None):
    """(folder, date, study, period, the deck's text or None)."""
    folder = Study(root)
    study = folder.study
    date = date or _latest(folder)
    path = folder.path("history", "periods", f"{date}.json")
    if not path.exists():
        raise Refused(f"no period for {date}: run period --date {date} first")
    period = load_json(path)
    folder.require_runs([period], date)
    doc_path = folder.path("reports", f"{date}.deck.json")
    if not doc_path.exists():
        return folder, date, study, period, None
    try:
        return folder, date, study, period, json.loads(doc_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise Refused(f"{doc_path} is not valid JSON ({exc})") from None


def _skeleton(date, m):
    slide = {"title": TODO, "read": TODO, "rows": "dimensions", "dimensions": [], "excerpts": [], "action": None}
    return {"schema": SCHEMA, "date": date, "same_audience": False, "moved": {},
            "found": {"title": TODO, "points": [TODO]},
            "actions_title": TODO,
            "actions": [{"class": TODO, "what": TODO, "rests_on": TODO, "read_next": TODO, "block": TODO}],
            "blocks": {b: [dict(slide)] for b in present(m)},
            "sources": {"title": TODO, "read": TODO},
            "method": {"limits": [], "ask": [TODO]}}


def _plan(m, study, date, lang):
    """The figures the deck will draw, block by block, as the writer may cite them."""
    t = DECK[lang]

    def of(a, b):
        return f"{a} {t['of']} {b}"
    out = [f"# Figures of the deck of {date}", "",
           "What the deck draws. The text may cite these figures as they stand here, and the figures of the sections "
           "that follow. Each question shows its block and its key.", "", "## Blocks", ""]
    for key in present(m):
        block = m["blocks"][key]
        shown = "; ".join((f"{f['project']}: " if f["project"] else "") + of(f["a"], f["b"]) for f in block["figures"])
        out += [f"### {key}: {shown}", ""]
        for row in block["rows"]:
            a, b = _measure(key, row)
            line = f"- {row['project']} / {row['label']}: {of(a, b)}"
            if key == "reach" and row["foils"]:
                line += "; competitors named: " + ", ".join(f"{label} {of(n, row['given'])}" for label, n in row["foils"])
            if key == "description":
                line += "; scores 1-2: " + of(row["bands"]["1-2"], row["judged"]) + ", 3: " + of(row["bands"]["3"], row["judged"])
            if key == "facts":
                line += f"; outdated {of(row['outdated'], row['given'])}, not stated {of(row['silent'], row['given'])}"
            if key != "reach" and row.get("mean") is not None:
                line += f"; mean {fmt_decimal(row['mean'], lang)}"
            out.append(line)
        out += ["", "Questions:"] + [f"- {q['key']} ({q['dimension']}): «{q['text']}»" for q in block["placed"]]
        s = block["sources"]
        out += ["", f"Sources: of {s['with_sources']} answers citing a source, the subject's pages in {s['owned']}, "
                    f"competitors' pages in {s['foil']}, third parties' pages in {s['third']}; domains cited most: "
                    + (", ".join(f"{d['domain']} ({d['answers']})" for d in s["domains"]) or "none"), ""]
    return out


def _without_answers(material):
    """The material with each answer and its heading taken out."""
    out, inside = [], False
    for line in material.splitlines():
        if line == "~~~~":
            inside = not inside
        elif not inside and not (line.startswith("**") and ", sources: " in line) and not line.startswith("Each answer is between"):
            if line or (out and out[-1]):
                out.append(line)
    return out


def write(root, date=None):
    """The figures file and, the first time, the deck's text to fill. A second run keeps what is written and
    reads its `moved` and `same_audience`."""
    folder, date, study, period, doc = load(root, date)
    lang = study["report_language"]
    m = build_model(folder, study, period, doc)
    path = folder.path("reports", f"{date}.deck.json")
    if doc is None:
        path.parent.mkdir(exist_ok=True)
        write_json(path, _skeleton(date, m))
    material = folder.path("history", "material", f"{date}.md")
    if not material.exists():
        raise Refused(f"no material for {date}: run period --date {date} first")
    figures = folder.path("history", "deck", f"{date}.figures.md")
    figures.parent.mkdir(exist_ok=True)
    write_text(figures, "\n".join(_plan(m, study, date, lang) + _without_answers(material.read_text(encoding="utf-8"))) + "\n")
    blocks = ", ".join(f"{b} ({len(m['blocks'][b]['placed'])} questions)" for b in present(m))
    return f"Blocks: {blocks}. Figures: {figures}. To fill: {path}."


# --- the check --------------------------------------------------------------

def _texts(doc):
    """(field, limit name, text) of every text of the deck the reader gets, excerpts apart."""
    found = doc.get("found") or {}
    yield "found title", "title", found.get("title") or ""
    for point in found.get("points") or []:
        yield "found point", "point", point
    yield "actions title", "title", doc.get("actions_title") or ""
    for n, a in enumerate(doc.get("actions") or [], 1):
        for field in ("what", "rests_on", "read_next"):
            yield f"action {n} {field}", field, a.get(field) or ""
    for key, slides in (doc.get("blocks") or {}).items():
        for slide in slides:
            yield f"{key} title", "title", slide.get("title") or ""
            yield f"{key} read", "read", slide.get("read") or ""
    sources = doc.get("sources") or {}
    yield "sources title", "title", sources.get("title") or ""
    yield "sources read", "read", sources.get("read") or ""
    method = doc.get("method") or {}
    for text in method.get("limits") or []:
        yield "method limit", "limit", text
    for text in method.get("ask") or []:
        yield "method question", "ask", text


def _structure(doc, m):
    """The actions and what supports them, the slides of each block, and the deck's length."""
    problems = []
    blocks, actions = doc.get("blocks") or {}, doc.get("actions") or []
    points = (doc.get("found") or {}).get("points") or []
    if not actions:
        problems.append("the deck has no action")
    if len(actions) > MAX_ACTIONS:
        problems.append(f"{len(actions)} actions: a deck holds at most {MAX_ACTIONS}")
    if not points or len(points) > MAX_POINTS:
        problems.append(f"{len(points)} points on what was found: write one to at most {MAX_POINTS}")
    for key, value in (doc.get("moved") or {}).items():
        if value != "description":
            problems.append(f"question {key} moved to {value}: a question can move only to description")
        if not any(q["key"] == key and not q["names_subject"] for q in m["blocks"]["description"]["placed"]):
            problems.append(f"question {key} is moved, and only a question naming no subject can be")
    for key in present(m):
        block = m["blocks"][key]
        slides = blocks.get(key) or []
        if not slides:
            problems.append(f"block {key} has no slide")
        if len(slides) > 2:
            problems.append(f"block {key} has {len(slides)} slides: a block holds at most 2")
        shown = set()
        for slide in slides:
            known = {r["dimension"] for r in block["rows"]}
            for name in slide.get("dimensions") or []:
                if name not in known:
                    problems.append(f"block {key}: {name} is not one of its dimensions ({', '.join(sorted(known))})")
            rows = rows_of(key, block, slide)
            shown |= {r["dimension"] for r in rows}
            if len(rows) > MAX_ROWS:
                problems.append(f"a slide of block {key} draws {len(rows)} rows, at most {MAX_ROWS}: "
                                "split them over its two slides with `dimensions`")
            if len(slide.get("excerpts") or []) > MAX_EXCERPTS:
                problems.append(f"a slide of block {key} holds more than {MAX_EXCERPTS} excerpts")
            if slide.get("action") is not None and not 1 <= slide["action"] <= len(actions):
                problems.append(f"a slide of block {key} supports action {slide['action']}, which the deck does not have")
        missing = {r["dimension"] for r in block["rows"]} - shown
        if slides and missing:
            problems.append(f"block {key}: no slide draws {', '.join(sorted(missing))}")
    problems += [f"block {key} has no question in this period: remove it" for key in blocks if key not in present(m)]
    for n, a in enumerate(actions, 1):
        if a.get("class") not in CLASSES:
            problems.append(f"action {n}: class {a.get('class')!r} is not one of {', '.join(CLASSES)}")
        if a.get("block") not in present(m):
            problems.append(f"action {n}: block {a.get('block')!r} is not one of {', '.join(present(m))}")
        elif not any(s.get("action") == n for s in blocks.get(a["block"]) or []):
            problems.append(f"action {n} has no evidence slide: set `action` on a slide of block {a['block']}")
        for field in ("rests_on", "read_next"):
            if not re.search(r"\d", a.get(field) or ""):
                problems.append(f"action {n}: {field} carries no figure")
    count = 3 + sum(len(s) for s in blocks.values()) + bool(_any_sources(m)) + 1
    if count > MAX_SLIDES:
        problems.append(f"the deck has {count} slides, at most {MAX_SLIDES}")
    return problems


def _any_sources(m):
    return any(m["blocks"][b]["sources"]["with_sources"] for b in present(m))


def rows_of(key, block, slide):
    """The rows a slide draws: its dimensions, one row each or, with `rows: questions`, one per question."""
    pool = block["questions"] if slide.get("rows") == "questions" and key != "facts" else block["rows"]
    chosen = slide.get("dimensions") or []
    return [r for r in pool if not chosen or r["dimension"] in chosen]


def _responses(folder, period):
    """{(question text, model): the answers given}, compared in `check`'s plain form."""
    out = {}
    for key, ids in period["runs"].items():
        keys = {q["key"]: match_key(q["text"]) for d in period["asked"].get(key, []) for q in d["questions"]}
        for run_id in ids:
            for r in folder.run(key, run_id)["responses"]:
                if r["match"] != "unmatched" and r["answer"] and r["question"] in keys:
                    out.setdefault((keys[r["question"]], r["model"]), []).append(_plain(r["answer"]))
    return out


def _cut(text, pieces, answers):
    """Whether an excerpt starts or ends inside a sentence with no mark of the cut: read without the words
    around it, a part of a sentence can say what the sentence does not."""
    bare = text.strip().strip("«»“”\"'").strip()
    opened = bool(re.match(r"(?:\[…\]|\[\.\.\.\]|\(…\)|\(\.\.\.\)|…|\.\.\.)", bare))
    closed = bool(re.search(r"(?:\[…\]|\[\.\.\.\]|\(…\)|\(\.\.\.\)|…|\.\.\.)$", bare))
    found = []
    for answer in answers:
        if not _quoted_in(pieces, [answer]):
            continue
        at = answer.find(pieces[0])
        end = answer.rfind(pieces[-1]) + len(pieces[-1])
        if not opened and not SENTENCE_START.search(answer[:at].rstrip() if answer[:at].strip() else ""):
            found.append("starts inside a sentence")
        if not closed and end < len(answer) and not SENTENCE_END.search(pieces[-1]):
            found.append("ends inside a sentence")
        return found
    return found


def _excerpts(doc, study, period, by_answer, names):
    problems = []
    questions = {match_key(q["text"]) for d in (d for ds in period["asked"].values() for d in ds) for q in d["questions"]}
    models = {}
    for model, name in names.items():
        models[match_key(name)] = model
        models[match_key(name.split(": ", 1)[-1])] = model
    for key, slides in (doc.get("blocks") or {}).items():
        for slide in slides:
            for e in slide.get("excerpts") or []:
                text, question, assistant = e.get("text") or "", e.get("question") or "", e.get("assistant") or ""
                pieces = _pieces(text)
                if len(ELLIPSIS.sub(" ", text).split()) > MAX_WORDS:
                    problems.append(f"an excerpt holds over {MAX_WORDS} words: {text[:60]!r}")
                if match_key(question) not in questions:
                    problems.append(f"{question!r} is not a question of the period: copy it as `figures` gives it")
                    continue
                if match_key(assistant) not in models:
                    problems.append(f"{assistant!r} is not an assistant of the period ({', '.join(names.values())})")
                    continue
                pool = by_answer.get((match_key(question), models[match_key(assistant)]), [])
                if not _quoted_in(pieces, pool):
                    problems.append(f"excerpt not found verbatim in the answers of {assistant} to this question: {text[:80]!r}; "
                                    + _stops_matching(pieces[0] if pieces else "", pool))
                    continue
                problems += [f"an excerpt {why}: mark the cut with […], and keep whole any condition or comparison its "
                             f"meaning rests on: {text[:80]!r}" for why in _cut(text, pieces, pool)]
    return problems


def _quotable(study):
    """The texts a «» may hold without being read as figures: questions and fact terms."""
    found = {tight(match_key(q["text"])) for p in study["projects"] for d in p["dimensions"] for q in d["questions"]}
    terms = (fact_terms(q) or {} for p in study["projects"] for d in p["dimensions"] for q in d["questions"])
    return found | {tight(match_key(t)) for term in terms for ts in term.values() for t in ts}


def _allowed_figures(m, period):
    """What the text may cite: the figures of the period, and those the deck draws from it."""
    scopes = [s for b in period["projects"].values() for s in [b, *b["dimensions"].values()]]
    scopes += [q for b in period["projects"].values() for d in b["dimensions"].values() for q in d["questions"].values()]
    decimals, percents, pairs = _allowed(scopes)
    for key in present(m):
        block = m["blocks"][key]
        for f in block["figures"]:
            _ratio(f["a"], f["b"], percents, pairs)
        pooled = [sum(f[k] for f in block["figures"]) for k in ("a", "b")]
        _ratio(*pooled, percents, pairs)
        for row in block["rows"] + block["questions"]:
            _ratio(*_measure(key, row), percents, pairs)
            if row.get("mean") is not None:
                decimals.add(round_half_up(row["mean"], 1))
            if key == "facts":
                _ratio(row["outdated"], row["given"], percents, pairs)
                _ratio(row["silent"], row["given"], percents, pairs)
            else:
                for n in row["bands"].values():
                    _ratio(n, row["judged"], percents, pairs)
                for _, n in row["foils"]:
                    _ratio(n, row["given"], percents, pairs)
        s = block["sources"]
        for n in (s["owned"], s["foil"], s["third"], *(d["answers"] for d in s["domains"])):
            _ratio(n, s["with_sources"], percents, pairs)
    return decimals, percents, pairs


def problems_of(folder, study, period, doc):
    if doc.get("schema") != SCHEMA:
        return [f"schema is not {SCHEMA}"]
    if "[[" in json.dumps(doc, ensure_ascii=False):
        return ["a text is left to write: replace every [[...]] marker"]
    lang = study["report_language"]
    m = build_model(folder, study, period, doc)
    problems = _structure(doc, m)
    names = period.get("names") or {}
    by_answer = _responses(folder, period)
    problems += _excerpts(doc, study, period, by_answer, names)
    for field, limit, text in _texts(doc):
        if len(text) > LIMITS[limit]:
            problems.append(f"{field} holds {len(text)} characters, at most {LIMITS[limit]}: {text[:60]!r}")
        if not text.strip():
            problems.append(f"{field} is empty")
    text = "\n".join(t for _, _, t in _texts(doc))
    problems += [f"a word about how the answers were scored appears: {w.group(0)}" for w in SCORING.finditer(text)]
    problems += leaks(folder, study, period, text, folder.binding)
    shown = [*names.values(), *(n.split(": ", 1)[-1] for n in names.values())]
    answers = [a for pool in by_answer.values() for a in pool]
    problems += _figures(_unquote(text, _quotable(study), answers, shown), lang, _allowed_figures(m, period))
    return problems


def check(root, path, date=None):
    path = Path(path)
    day = date or path.name.split(".")[0]
    folder, day, study, period, _ = load(root, day)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"{path} cannot be read ({exc})") from None
    problems = problems_of(folder, study, period, doc)
    if not problems:
        folder.record_report({"date": day, "status": "final", "period": {"from": period["from"], "to": period["to"]},
                              "runs": period["runs"], "previous": (period.get("comparison") or {}).get("previous"),
                              "file": _shown(folder, path)})
        folder.record_outcome("written", f"deck of {day} passed check")
    return problems


# --- the page ---------------------------------------------------------------

def _of(a, b, t):
    return f"{a} {t['of']} {b}"


def _head(cells, subject):
    return "".join(f'<div class="head">{esc(c.format(subject=subject))}</div>' for c in cells)


def _bar(parts):
    """A stacked bar: a part too narrow for its count leaves it to the row's other figures."""
    total = sum(n for n, _ in parts) or 1
    segments = "".join(f'<span class="seg {kind}" style="flex: {n} 0 0">{n if n / total >= 0.07 else ""}</span>'
                       for n, kind in parts if n)
    return f'<div class="bar">{segments}</div>'


def _meter(a, b, small=False):
    width = 100 * a / b if b else 0
    return f'<div class="meter{" small-meter" if small else ""}"><span style="width: {width:.1f}%"></span></div>'


def _legend(entries):
    return '<div class="legend">' + "".join(f'<span><i class="{kind}"></i>{esc(label)}</span>' for kind, label in entries) + "</div>"


def _rows(key, rows, t, lang, subject, grouped):
    long = " long" if any(len(r["label"]) > 60 for r in rows) else ""
    few = " few" if len(rows) <= 3 else " dense" if len(rows) > 5 else ""
    head = {"reach": t["reach_head"], "description": t["description_head"], "facts": t["facts_head"]}[key]
    out, group = [_head(head, subject)], None
    for row in rows:
        if grouped and row["project"] != group:
            group = row["project"]
            out.append(f'<div class="group">{esc(group)}</div>')
        label = f'<div>{esc(row["label"])}</div>'
        mean = fmt_decimal(row["mean"], lang) if row.get("mean") is not None else ""
        if key == "reach":
            foils = ", ".join(f"{name} {n}" for name, n in row["foils"]) or t["none"]
            out.append(f'{label}{_meter(row["named"], row["given"])}'
                       f'<div class="fig">{_of(row["named"], row["given"], t)}</div><div class="foils">{esc(foils)}</div>')
        elif key == "description":
            b = row["bands"]
            out.append(f'{label}{_bar([(b["4-5"], "good"), (b["3"], "mid"), (b["1-2"], "low")])}<div class="fig">{mean}</div>')
        else:
            out.append(f'{label}{_bar([(row["current"], "good"), (row["outdated"], "low"), (row["silent"], "mid")])}'
                       f'<div class="fig">{_of(row["current"], row["given"], t)}</div><div class="fig">{mean}</div>')
    grid = f'<div class="rows {key}-rows{long}{few}">' + "".join(out) + "</div>"
    legend = {"description": [("good", t["bands"]["4-5"]), ("mid", t["bands"]["3"]), ("low", t["bands"]["1-2"])],
              "facts": [("good", t["fact_parts"]["current"]), ("low", t["fact_parts"]["outdated"]),
                        ("mid", t["fact_parts"]["silent"])]}.get(key)
    return '<div class="chart">' + (_legend(legend) if legend else "") + grid + "</div>"


def _quotes(excerpts, t):
    if not excerpts:
        return ""
    cards = "".join(f'<figure class="quote"><blockquote>«{esc(e["text"])}»</blockquote><figcaption>'
                    f'<b>{esc(t["question"])}:</b> {esc(e["question"])}<br><b>{esc(t["assistant"])}:</b> {esc(_public(e["assistant"]))}'
                    "</figcaption></figure>" for e in excerpts)
    return f'<div class="quotes">{cards}</div>'


def _public(name):
    return name.split(": ", 1)[-1]


def _tile(key, block, t, subject):
    figures = block["figures"]
    if len(figures) == 1:
        f = figures[0]
        shown = f'<div class="tile-fig">{f["a"]} <small>{t["of"]} {f["b"]}</small></div>'
    else:
        shown = "".join(f'<div class="tile-row">{_of(f["a"], f["b"], t)} <span>{esc(f["project"])}</span></div>' for f in figures)
    return (f'<div class="tile"><div class="tile-head">{esc(t["blocks"][key])}</div>{shown}'
            f'<div class="tile-cap">{esc(t["tile"][key].format(subject=subject))}</div></div>')


def _order(doc, m):
    """The slides in reading order: (kind, block, slide)."""
    order = [("cover", None, None), ("found", None, None), ("actions", None, None)]
    for key in present(m):
        order += [(key, key, s) for s in (doc.get("blocks") or {}).get(key) or []]
    if _any_sources(m):
        order.append(("sources", None, None))
    return order + [("method", None, None)]


def _evidence(order, action, n):
    return next((i for i, (_, key, s) in enumerate(order, 1) if key == action.get("block") and s.get("action") == n),
                next((i for i, (_, key, _s) in enumerate(order, 1) if key == action.get("block")), ""))


def _actions_table(doc, order, t):
    head = "".join(f"<th>{esc(c)}</th>" for c in t["actions_head"])
    rows = "".join(f'<tr><td class="num">{n}</td><td class="class">{esc(t["classes"].get(a.get("class"), ""))}</td>'
                   f'<td>{esc(a.get("what"))}</td><td>{esc(a.get("rests_on"))}</td><td>{esc(a.get("read_next"))}</td>'
                   f'<td class="num">{_evidence(order, a, n)}</td></tr>' for n, a in enumerate(doc.get("actions") or [], 1))
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def _sources_table(m, t, subject):
    head = "".join(f"<th>{esc(c.format(subject=subject))}</th>" for c in t["sources_head"])
    rows = []
    for key in present(m):
        s = m["blocks"][key]["sources"]
        if not s["with_sources"]:
            continue
        n = s["with_sources"]
        cells = "".join(f'<td><span class="fig">{_of(s[k], n, t)}</span>{_meter(s[k], n, True)}</td>' for k in ("owned", "foil", "third"))
        domains = ", ".join(f'{d["domain"]} ({d["answers"]})' for d in s["domains"])
        rows.append(f'<tr><td class="class">{esc(t["blocks"][key])}</td><td class="num">{n}</td>{cells}<td>{esc(domains)}</td></tr>')
    return f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def _method(doc, m, t):
    head = "".join(f"<th>{esc(c)}</th>" for c in t["method_head"])
    rows = "".join(f'<tr><td class="class">{esc(r["name"])}</td><td class="num">{r["questions"]}</td>'
                   f'<td>{esc(", ".join(r["assistants"]))}</td><td class="num">{r["answers"]}</td>'
                   f'<td>{esc(t["frequency"].get(r["schedule"], ""))}</td></tr>' for r in m["method"])
    method = doc.get("method") or {}
    limits = method.get("limits") or []
    left = f'<h2>{esc(t["scores_title"])}</h2><p>{esc(t["scores"])}</p>'
    if limits:
        left += f'<h2>{esc(t["limits_title"])}</h2><ul>' + "".join(f"<li>{esc(x)}</li>" for x in limits) + "</ul>"
    right = (f'<h2>{esc(t["where_title"])}</h2><p>{esc(t["where"])}</p><h2>{esc(t["ask_title"])}</h2><ul>'
             + "".join(f"<li>{esc(x)}</li>" for x in method.get("ask") or []) + "</ul>")
    return (f'<h1>{esc(t["method_title"])}</h1><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
            f'<div class="method-cols"><div>{left}</div><div>{right}</div></div>')


def _slide_html(kind, key, slide, doc, m, order, t, lang, cover):
    subject = m["subject"]
    if kind == "found":
        found = doc.get("found") or {}
        tiles = "".join(_tile(b, m["blocks"][b], t, subject) for b in present(m))
        points = "".join(f"<li>{esc(p)}</li>" for p in found.get("points") or [])
        return f'<h1>{esc(found.get("title"))}</h1><div class="tiles">{tiles}</div><ul class="points">{points}</ul>'
    if kind == "actions":
        return f'<h1>{esc(doc.get("actions_title") or "")}</h1>{_actions_table(doc, order, t)}'
    if kind == "sources":
        sources = doc.get("sources") or {}
        return (f'<h1>{esc(sources.get("title"))}</h1><p class="read">{esc(sources.get("read"))}</p>'
                + _sources_table(m, t, subject))
    if kind == "method":
        return _method(doc, m, t)
    block = m["blocks"][key]
    rows = rows_of(key, block, slide)
    grouped = len({r["project"] for r in rows}) > 1 and not doc.get("same_audience")
    out = (f'<h1>{esc(slide.get("title"))}</h1><p class="read">{esc(slide.get("read"))}</p>'
           + _rows(key, rows, t, lang, subject, grouped) + _quotes(slide.get("excerpts"), t))
    n = slide.get("action")
    if n is not None and 1 <= n <= len(doc.get("actions") or []):
        label = t["action"].format(n=n)
        out += f'<div class="strip"><b>{esc(label)}:</b> {esc(doc["actions"][n - 1].get("what"))}</div>'
    return out


def page_of(root, date=None, option=None):
    """(the deck as one HTML page, its slides)."""
    folder, date, study, period, doc = load(root, date)
    if doc is None:
        raise Refused(f"no deck for {date}: run deck --date {date} and write its text first")
    chosen, _ = sentl_theme.resolve(folder, option)
    lang = study["report_language"]
    t = DECK[lang]
    m = build_model(folder, study, period, doc)
    order = _order(doc, m)
    subject = m["subject"]
    days = span(period["from"], period["to"], lang)
    logo = f'<img src="{html.escape(chosen["logo"], quote=True)}" alt="">' if chosen.get("logo") else ""
    cover = (f'<section class="slide cover"><div class="band"></div><div class="cover-body">{logo}'
             f'<h1>{esc(t["cover_title"].format(subject=subject))}</h1><div class="cover-kind">{esc(t["cover_kind"])} · {esc(days)}</div>'
             f'<div class="cover-line">{esc(t["cover_line"].format(**m["totals"]))}</div></div></section>')
    slides = [cover]
    for n, (kind, key, slide) in enumerate(order[1:], 2):
        foot = (f'<footer class="foot"><span>{logo}{esc(subject)} · {esc(days)}</span><span>{n} / {len(order)}</span></footer>')
        slides.append(f'<section class="slide {kind}">{_slide_html(kind, key, slide, doc, m, order, t, lang, cover)}{foot}</section>')
    font = f'<link rel="stylesheet" href="{html.escape(chosen["font_url"], quote=True)}">' if chosen.get("font_url") else ""
    style = sentl_theme.variables(chosen) + STYLE + (chosen.get("css") or "")
    text = (f'<!doctype html>\n<html lang="{html.escape(lang)}"><head><meta charset="utf-8"><title>{esc(subject)} · {esc(days)}</title>'
            f"{font}<style>{style}</style></head><body>\n" + "\n".join(slides) + "\n</body></html>\n")
    return text, len(order)


def pages(path):
    """The pages of a PDF: from pdfinfo where installed, otherwise from its page objects."""
    exe = shutil.which("pdfinfo")
    if exe:
        done = subprocess.run([exe, str(path)], capture_output=True, text=True)
        found = re.search(r"^Pages:\s+(\d+)", done.stdout, re.M)
        if found:
            return int(found.group(1))
    return len(re.findall(rb"/Type\s*/Page\b", Path(path).read_bytes()))


def _spilling(path, count, total):
    """The slides that run over their page, read from the numbers in the pages' feet, where pdftotext is installed."""
    exe = shutil.which("pdftotext")
    if not exe:
        return []
    out, last = [], 1
    for page in range(1, count + 1):
        text = subprocess.run([exe, "-f", str(page), "-l", str(page), str(path), "-"], capture_output=True, text=True).stdout
        found = re.search(rf"(\d+)\s*/\s*{total}\s*$", text.replace("\f", "").strip())
        if found:
            last = int(found.group(1))
        elif page > 1:
            out.append(last + 1)
    return sorted(set(out))


def render(root, date=None, option=None, printer=None, skip_check=False):
    """reports/<date>.deck.html and .pdf; the copy to send goes to reports/share/."""
    folder, date, study, period, doc = load(root, date)
    if doc is None:
        raise Refused(f"no deck for {date}: run deck --date {date} and write its text first")
    if not skip_check:
        found = problems_of(folder, study, period, doc)
        if found:
            raise Refused(f"the deck fails check on {len(found)} point(s): run check on it, then pdf --deck again")
    text, slides = page_of(root, date, option)
    target = folder.path("reports", f"{date}.deck.html")
    pdf = folder.path("reports", f"{date}.deck.pdf")
    write_text(target, text)
    engine, failures = (printer or report_pdf.print_pdf)(target, pdf, ENGINES)
    if not engine:
        why = "; ".join(failures) or "no PDF engine (chromium, google-chrome, weasyprint) is on this machine"
        return f"Wrote {target}. The PDF was not written ({why}): open the page in a browser and print it to PDF."
    count = pages(pdf)
    if count != slides:
        over = _spilling(pdf, count, slides)
        where = f" (slide {', '.join(map(str, over))} runs over)" if over else ""
        raise Refused(f"{count} pages for {slides} slides{where}: shorten the text of that slide, then pdf --deck again")
    name = report_pdf.share_name(folder, study, date, "monitoring deck")
    shared = folder.path("reports", "share")
    shared.mkdir(exist_ok=True)
    copy = shared / f"{name}.pdf"
    shutil.copyfile(pdf, copy)
    return f"Wrote {target} and {pdf} ({slides} slides, engine: {engine}). To send: {copy}"
