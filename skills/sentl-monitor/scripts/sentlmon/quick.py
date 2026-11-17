"""`deck --quick`: the period as a short summary deck, drawn from the same period as the full deck (DEVPLAN M33, M38).

A cover, a summary with each project's figure and one sentence, one slide per project of the period with one row per
topic, one to three suggested actions, and a last slide with the sites the answers cite most and how the answers were
counted. The code draws every figure; the writer fills, in `reports/<date>.quick.json`, the summary's title and
sentences, each slide's question and title, each row's sentence and excerpt, and each action's what and why, which
`check` reads against the period with the full deck's tests. An action works on the subject's own pages or checks a page
the answers cite, and rests on a count a row draws. The quick deck's actions are no earlier edition: a later full deck
compares its own only with a full deck's.
"""

import html
import json
import math
import re
import shutil
from collections import Counter
from itertools import zip_longest
from pathlib import Path

from . import deck, fit
from . import pdf as report_pdf
from . import theme as sentl_theme
from .adopt import missing_answers
from .check import COUNT, ELLIPSIS, _figures, _pieces, _quoted_in, _ratio, _stops_matching, _unquote, leaks
from .common import Refused, match_key, measured, require_language, span, write_json, write_text
from .i18n import DECK, QUICK
from .period import Reader

SCHEMA = "sentl-monitor/quick@2"
FIRST_SCHEMA = "sentl-monitor/quick@1"
TODO = deck.TODO
MAX_ROWS = 6
MAX_ACTIONS = 3
SITES = 8
# The slides' questions and titles keep their characters; the summary and the actions take the full deck's limits.
LIMITS = {"question": 120, "title": 160, "read": 170, "answer": 170, "what": 175, "why": 175}
SUMMARY_TITLE = "summary title"
# An action is the reader's own work: a request to a third party is the full deck's, which reads the page first.
TO = r"(?:a|al|alla|ai|agli|alle|all['’])"
OWNERS = r"(?:the\s+)?(?:owners?|editors?|staff|team|site|publisher|author)"
REQUEST = re.compile(rf"\b(?:chied\w*|richied\w*|richiest\w*|contattar\w*|contattando|sollecit\w*|segnal\w* {TO}|scriv\w* {TO}"
                     rf"|ask(?:s|ed|ing)?\b|request\w*|contact(?:s|ed|ing)? {OWNERS}|e-?mail(?:s|ed|ing)? {OWNERS}"
                     r"|reach(?:ing)? out|writ(?:e|es|ing) to)", re.I)
LINE = 15 * 1.28  # one line of a row's sentence, in px: .q-says in STYLE

STYLE = """
.q-slide h1 { font-size: 26px; }
.q-rows { display: flex; flex-direction: column; border-top: 1px solid var(--sl-line); }
.q-row { display: grid; grid-template-columns: 160px 170px 1fr; column-gap: 18px; padding: 6px 0 7px;
  border-bottom: 1px solid var(--sl-line); align-items: start; }
.q-dim { font-size: 15px; line-height: 1.25; font-weight: 700; color: var(--sl-text); padding-top: 2px; }
.q-figs { display: flex; flex-direction: column; gap: 8px; }
.q-fig { display: flex; flex-direction: column; gap: 3px; }
.q-n { font-size: 24px; line-height: 1; font-weight: 700; color: var(--sl-text); white-space: nowrap; }
.q-n span { font-size: 14px; font-weight: 600; color: var(--sl-muted); }
.q-lab { font-size: 11.5px; line-height: 1.25; color: var(--sl-muted); }
.q-fig .meter, .q-fig .bar { height: 7px; border-radius: 3px; }
.q-fig .seg { font-size: 0; }
.q-says { font-size: 15px; line-height: 1.28; margin: 0; }
.q-quote { font-size: 13.5px; line-height: 1.28; font-style: italic; color: var(--sl-text); margin: 3px 0 0;
  padding-left: 9px; border-left: 3px solid var(--sl-primary); }
.q-who { font-size: 11.5px; color: var(--sl-muted); font-style: normal; }
.q-cols { display: grid; grid-template-columns: 1fr 1fr; column-gap: 36px; }
.q-cols h2 { font-size: 16px; line-height: 1.25; margin: 0 0 6px; color: var(--sl-deep); }
.q-cols table { font-size: 14.5px; line-height: 1.3; }
.q-cols td { padding: 4px 0; }
.q-cols td.q-c { text-align: right; font-weight: 600; width: 70px; }
.q-own { color: var(--sl-muted); font-size: 12px; }
.q-method { font-size: 14.5px; line-height: 1.4; margin: 0; }
.sum-figs .sum-cap + .sum-fig { margin-top: 8px; }
"""


def esc(value):
    return html.escape(str(value), quote=False)


# --- what the period gives --------------------------------------------------

def _model(folder, study, period):
    """The full deck's model of the period. A quick deck compares with no earlier deck, so it cites no figure of one."""
    m = deck.build_model(folder, study, period)
    m["second"] = None
    return m


def _layout(m, study, period):
    """The projects of the period in study order, each with a row per topic that has answers: the presence figure of its
    questions that name no subject, the rating of the others, the texts of its questions."""
    found = {b: {(r["project"], r["dimension"]): r for r in m["blocks"][b]["rows"]} for b in ("reach", "description")}
    out = []
    for proj, dims in measured(study, period):
        name, rows = deck._short(proj["name"], m["subject"]), []
        for d in dims:
            reach, description = found["reach"].get((name, d["name"])), found["description"].get((name, d["name"]))
            reach = reach if reach and reach["given"] else None
            description = description if description and description["judged"] else None
            if reach or description:
                rows.append({"key": d["key"], "name": d["name"], "reach": reach, "description": description,
                             "questions": [q["text"] for q in d["questions"]]})
        if rows:
            out.append({"key": proj["key"], "name": name, "rows": rows})
    return out


def _split(rows, most=MAX_ROWS):
    """A project's rows in slides of at most `most`, as even as they come: 7 rows are 4 and 3, not 6 and 1."""
    parts = math.ceil(len(rows) / most) or 1
    size, extra = divmod(len(rows), parts)
    out, at = [], 0
    for n in range(parts):
        out.append(rows[at:at + size + (n < extra)])
        at += size + (n < extra)
    return out


def _expected(layout):
    """(project key, topic keys) of each slide of rows the period gives."""
    return [(p["key"], [r["key"] for r in part]) for p in layout for part in _split(p["rows"])]


def _skeleton(date, layout):
    return {"schema": SCHEMA, "date": date, "summary": _summary_skeleton(layout),
            "slides": [{"project": key, "question": TODO, "title": TODO,
                        "rows": [{"dimension": d, "says": TODO, "excerpt": {"text": TODO, "question": TODO, "assistant": TODO}}
                                 for d in dims]}
                       for key, dims in _expected(layout)],
            "actions": [{"what": TODO, "why": TODO}]}


def _summary_skeleton(layout):
    return {"title": TODO, "projects": {p["key"]: TODO for p in layout}}


def _upgraded(doc, layout):
    """A quick deck of the first schema with its slides kept, and the summary and the actions to write."""
    return {"schema": SCHEMA, "date": doc.get("date"), "summary": _summary_skeleton(layout), "slides": doc.get("slides"),
            "actions": [{"what": TODO, "why": TODO}]}


def _headlines(project):
    """A project's figures on the summary, its rows added up: the answers naming the subject of those to the questions
    that name no subject, and the favourable answers of those rated. [(kind, a, b)], a kind without answers left out."""
    out = []
    for kind, part, whole in (("reach", lambda r: r["named"], lambda r: r["given"]),
                              ("description", lambda r: r["bands"]["4-5"], lambda r: r["judged"])):
        rows = [r[kind] for r in project["rows"] if r.get(kind)]
        if rows and sum(map(whole, rows)):
            out.append((kind, sum(map(part, rows)), sum(map(whole, rows))))
    return out


def _cited(m, key):
    """(the answers of a block, its sites cited most with the answers citing each)."""
    block = m["blocks"][key]
    counts = Counter(d for r in block["responses"] for d in {s["domain"] for s in r["sources"] if s.get("domain")})
    return block["sources"]["answers"], sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:SITES]


def _rivals(foils):
    """The competitors named most, with their count; [] when none is named."""
    named = [(label, n) for label, n in foils if n]
    return [(label, n) for label, n in named if n == named[0][1]] if named else []


def _plan(layout, m, study, lang):
    """The quick deck's part of the figures file: each slide's rows, their figures and the questions an excerpt comes from."""
    of = DECK[lang]["of"]
    names = sorted({deck._assistant(model, m["names"]) for model in m["names"]})
    words = {"reach": "{subject} named in {a} {of} {b}", "description": ("faithful" if m.get("fidelity") else "favourable")
                                                                        + " {a} {of} {b}"}
    out = ["## Quick deck", "",
           "A summary, one slide per project and one row per topic, then the suggested actions, as "
           "reports/<date>.quick.json lists them. Fill each slide's `question` and `title`, and each row's `says` and "
           "`excerpt`: a passage copied verbatim from an answer to one of the row's questions, the question as given here and "
           "the assistant by its name.", "",
           f"Assistants: {', '.join(names)}.", "",
           "### Slide 2: summary", "",
           "`summary.title`: the period's main finding, at most 20 words. `summary.projects`: for each project one sentence "
           "of at most 25 words saying what its slides add up to; the code draws its figure beside it, so the sentence does "
           "not repeat that figure, nor the title of the project's slide.", ""]
    for p in layout:
        shown = [words[kind].format(subject=m["subject"], a=a, of=of, b=b) for kind, a, b in _headlines(p)]
        out.append(f"- {p['key']} ({p['name']}): {'; '.join(shown)}")
    out.append("")
    for n, (key, dims) in enumerate(_expected(layout), 3):
        project = next(p for p in layout if p["key"] == key)
        out += [f"### Slide {n}: {key} ({project['name']})", ""]
        rows = {r["key"]: r for r in project["rows"]}
        for d in dims:
            row, shown = rows[d], []
            if row["reach"]:
                r = row["reach"]
                rivals = ", ".join(f"{label} {count} {of} {r['given']}" for label, count in r["foils"])
                shown.append(f"{m['subject']} named in {r['named']} {of} {r['given']}"
                             + (f"; competitors named: {rivals}" if r["foils"] else ""))
            if row["description"]:
                r = row["description"]
                shown.append(", ".join(f"{word} {r['bands'][band]} {of} {r['judged']}" for word, band in
                                       (("favourable", "4-5"), ("neutral", "3"), ("unfavourable", "1-2")))
                             + (f", about a namesake {r['namesake']} {of} {r['judged']} ("
                                + ", ".join(f"{label} {n}" for label, n in r["namesakes"].items()) + ")"
                                if r.get("namesake") else ""))
            out.append(f"- {d} ({row['name']}): {'; '.join(shown)}")
            out += [f"  - «{text}»" for text in row["questions"]]
        out.append("")
    for key, label in (("reach", "the questions that name no subject"), ("description", "the questions on the subject")):
        if m["blocks"][key]["rows"]:
            answers, sites = _cited(m, key)
            listed = ", ".join(f"{d} ({n})" for d, n in sites) or "none"
            out += [f"Sites cited most in the {answers} answers to {label}: {listed}.", ""]
    owned = Reader(study).owned
    out += [f"### Slide {len(_expected(layout)) + 3}: suggested actions", "",
            f"`actions`: one to {MAX_ACTIONS}, in the order the reader should take them. Each `what`, at most 20 words, is work "
            f"on a page of {m['subject']}'s own site ({', '.join(owned) or 'none recorded'}), or starts with Verificare "
            "(Check) and names a site the answers cite, the one to check; never a request to a third party. Each `why`, at "
            "most 20 words, gives a count a row above draws (x su y).", ""]
    return out


def write(root, date=None):
    """The figures file and, the first time, the quick deck's text to fill; a second run keeps what is written."""
    folder, date, study, period, doc = deck.load(root, date, "quick")
    require_language(study)
    missing = missing_answers(study)
    if missing:
        raise Refused("the deck needs the operator's answers to:\n  " + "\n  ".join(missing))
    lang = study["report_language"]
    m = _model(folder, study, period)
    layout = _layout(m, study, period)
    if not layout:
        raise Refused(f"the period of {date} has no answers to draw: run period --date {date} after the runs are ingested")
    path = folder.path("reports", f"{date}.quick.json")
    if doc is None:
        path.parent.mkdir(exist_ok=True)
        write_json(path, _skeleton(date, layout))
    elif doc.get("schema") == FIRST_SCHEMA:
        write_json(path, _upgraded(doc, layout))
    figures = deck._figures_file(folder, study, date, m, lang, _plan(layout, m, study, lang))
    expected = _expected(layout)
    names = {p["key"]: p["name"] for p in layout}
    listed = ["1 cover", "2 summary"] + [f"{n} {names[key]} ({len(dims)} row{'s' * (len(dims) != 1)}: {', '.join(dims)})"
                                         for n, (key, dims) in enumerate(expected, 3)]
    total = len(expected) + 4
    listed += [f"{total - 1} suggested actions", f"{total} sites and method"]
    left = path.read_text(encoding="utf-8").count(TODO)
    return f"Slides: {'; '.join(listed)}; {total} slides. Figures: {figures}. To fill: {path}, {left} texts left."


# --- the check --------------------------------------------------------------

def _slides_of(doc):
    return [s if isinstance(s, dict) else {} for s in doc.get("slides") or []] if isinstance(doc.get("slides"), list) else []


def _rows_of(slide):
    rows = slide.get("rows")
    return [r if isinstance(r, dict) else {} for r in rows] if isinstance(rows, list) else []


def _summary_of(doc):
    summary = doc.get("summary") if isinstance(doc.get("summary"), dict) else {}
    projects = summary.get("projects") if isinstance(summary.get("projects"), dict) else {}
    return str(summary.get("title") or ""), {key: str(text or "") for key, text in projects.items()}


def _actions_of(doc):
    return [a if isinstance(a, dict) else {} for a in doc.get("actions") or []] if isinstance(doc.get("actions"), list) else []


def _texts(doc):
    """(field, limit name, text) of every text the writer fills, excerpts apart; the limit names are the full deck's, so
    its tests read them as they read its own."""
    title, projects = _summary_of(doc)
    yield SUMMARY_TITLE, "title", title
    for key, text in projects.items():
        yield f"summary of {key}", "answer", text
    for n, slide in enumerate(_slides_of(doc), 3):
        yield f"slide {n} question", "question", str(slide.get("question") or "")
        yield f"slide {n} title", "title", str(slide.get("title") or "")
        for row in _rows_of(slide):
            yield f"slide {n} {row.get('dimension')}.says", "read", str(row.get("says") or "")
    for n, action in enumerate(_actions_of(doc), 1):
        for field in ("what", "why"):
            yield f"action {n} {field}", field, str(action.get(field) or "")


def _structure(doc, layout):
    """Slides and rows other than those the period gives."""
    if not isinstance(doc.get("slides"), list):
        return ["slides is missing: run deck --quick again and keep its slides"]
    expected, problems = _expected(layout), []
    keys = [p["key"] for p in layout]
    if not isinstance(doc.get("summary"), dict):
        problems.append("summary is missing: run deck --quick again, which adds it")
    else:
        written = _summary_of(doc)[1]
        problems += [f"summary of {key} is missing: the period gives the project {key}" for key in keys if key not in written]
        problems += [f"summary of {key} is not a project of the period: it gives {', '.join(keys)}" for key in written
                     if key not in keys]
    for n, (slide, want) in enumerate(zip_longest(_slides_of(doc), expected), 3):
        if want is None:
            problems.append(f"slide {n} is not one the period gives: it gives {len(expected)} slide(s) of rows, "
                            + "; ".join(f"{key} with {', '.join(dims)}" for key, dims in expected))
        elif slide is None:
            problems.append(f"slide {n} is missing: the period gives {want[0]} with {', '.join(want[1])}")
        else:
            got = (slide.get("project"), [r.get("dimension") for r in _rows_of(slide)])
            if got != want:
                problems.append(f"slide {n} holds {got[0]} with {', '.join(map(str, got[1])) or 'no rows'}: the period "
                                f"gives {want[0]} with {', '.join(want[1])}")
    return problems


def _excerpts(doc, layout, by_answer, names):
    """Each row's excerpt: of one of its topic's questions, of an assistant of the period, verbatim, cut at a sentence."""
    topics = {(p["key"], r["key"]): r for p in layout for r in p["rows"]}
    models = {}
    for model, name in names.items():
        models[match_key(name)] = model
        models[match_key(name.split(": ", 1)[-1])] = model
    problems = []
    for n, slide in enumerate(_slides_of(doc), 3):
        for row in _rows_of(slide):
            where = f"slide {n} {row.get('dimension')}.excerpt"
            e = row.get("excerpt")
            if not isinstance(e, dict):
                problems.append(f"{where} is not a text, a question and an assistant")
                continue
            text, question, assistant = (str(e.get(k) or "") for k in ("text", "question", "assistant"))
            empty = [k for k, v in (("text", text), ("question", question), ("assistant", assistant)) if not v.strip()]
            if empty:
                problems.append(f"{where} has no {', '.join(empty)}")
                continue
            if len(ELLIPSIS.sub(" ", text).split()) > deck.MAX_WORDS:
                problems.append(f"{where} holds over {deck.MAX_WORDS} words: {text[:60]!r}")
            topic = topics.get((slide.get("project"), row.get("dimension")))
            if topic is None:
                continue
            if match_key(question) not in {match_key(q) for q in topic["questions"]}:
                problems.append(f"{where}: {question!r} is not a question of the topic {topic['name']}: copy one of its "
                                "questions as the figures file gives it")
                continue
            if match_key(assistant) not in models:
                problems.append(f"{where}: {assistant!r} is not an assistant of the period ({', '.join(names.values())})")
                continue
            pieces = _pieces(text)
            pool = by_answer.get((match_key(question), models[match_key(assistant)]), [])
            if not _quoted_in(pieces, pool):
                problems.append(f"{where} not found verbatim in the answers of {assistant} to this question: {text[:80]!r}; "
                                + _stops_matching(pieces[0] if pieces else "", pool))
                continue
            problems += [f"{where} {why}: mark the cut with […], and keep whole any condition or comparison its meaning "
                         f"rests on: {text[:80]!r}" for why in deck._cut(text, pieces, pool)]
    return problems


def _drawn(row):
    """The x of y a row draws: the answers naming the subject and those that do not, the competitors beside them, and
    the favourable, neutral, unfavourable and namesake answers."""
    pairs = set()
    reach, rated = row.get("reach"), row.get("description")
    if reach:
        pairs |= {(reach["named"], reach["given"]), (reach["given"] - reach["named"], reach["given"])}
        pairs |= {(n, reach["given"]) for _, n in reach.get("foils") or []}
    if rated:
        pairs |= {(n, rated["judged"]) for n in [*rated["bands"].values(), rated.get("namesake") or 0]}
    return pairs


def _restated(doc, layout):
    """A row's sentence giving a count its row draws: the sentence is for what lies behind the figure."""
    rows = {(p["key"], r["key"]): r for p in layout for r in p["rows"]}
    problems = []
    for n, slide in enumerate(_slides_of(doc), 3):
        for filled in _rows_of(slide):
            row = rows.get((slide.get("project"), filled.get("dimension")))
            if row is None:
                continue
            drawn = _drawn(row)
            problems += [f"slide {n} {filled.get('dimension')}.says says {a} of {b}, which its row draws: say what lies "
                         "behind it" for part in deck.SENTENCE.split(str(filled.get("says") or ""))
                         for _, _, a, b in deck._spans(part) if (a, b) in drawn]
    return problems


def _flat(text):
    return " ".join(re.sub(r"[^\w]+", " ", text.casefold()).split())


def _beside_summary(doc, layout):
    """A project's sentence on the summary says what lies behind the figure the code draws beside it, and is not the
    title of the project's slide again."""
    _, written = _summary_of(doc)
    titles = {}
    for n, slide in enumerate(_slides_of(doc), 3):
        titles.setdefault(slide.get("project"), []).append((n, _flat(str(slide.get("title") or ""))))
    problems = []
    for p in layout:
        sentence = written.get(p["key"]) or ""
        shown = {(a, b) for _, a, b in _headlines(p)}
        shown |= {(b - a, b) for a, b in shown}
        problems += [f"slide 2 summary of {p['key']} says {a} of {b}, which the summary draws beside it: say what lies "
                     "behind it" for part in deck.SENTENCE.split(sentence) for _, _, a, b in deck._spans(part) if (a, b) in shown]
        flat = _flat(sentence)
        problems += [f"slide 2 summary of {p['key']} repeats the title of slide {n}: say what the project's slides add up to"
                     for n, title in titles.get(p["key"], []) if flat and title and (title in flat or flat in title)]
    return problems


def _summary_figures(doc):
    """The summary is read in seconds: few figures on each text, and none said again and again."""
    title, written = _summary_of(doc)
    texts = [(SUMMARY_TITLE, title, deck.MAX_TITLE_FIGURES)] + [(f"summary of {k}", t, deck.MAX_READ_FIGURES)
                                                                 for k, t in written.items()]
    problems = [f"{field} holds {len(COUNT.findall(text))} figures, at most {most}: keep the one that makes the point"
                for field, text, most in texts if len(COUNT.findall(text)) > most]
    seen = Counter((c.group(1), c.group(4)) for _, text, _ in texts for c in COUNT.finditer(text))
    return problems + [f"{a} of {b} appears {n} times on the summary, at most {deck.MAX_REPEATS}: say it once and say "
                       "something else" for (a, b), n in seen.items() if n > deck.MAX_REPEATS]


def _summary_words(doc):
    """The summary whose writer's texts hold more words than the full deck's summary allows, with the longest of them.
    The names and figures the code draws are not counted: the page-fit check guards them."""
    title, written = _summary_of(doc)
    texts = sorted(((f, deck.words(x)) for f, x in [(SUMMARY_TITLE, title)] + [(f"summary of {k}", x) for k, x in written.items()]
                    if deck.words(x)), key=lambda fx: -fx[1])
    count = sum(w for _, w in texts)
    if count <= deck.SUMMARY_WORDS:
        return []
    longest = ", ".join(f"{f} ({w} words)" for f, w in texts[:3])
    return [f"slide 2 holds {count} words of the writer's texts, at most {deck.SUMMARY_WORDS} on the summary: shorten {longest}"]


def _owns(action, m):
    return any(m["author"](d.lower()) == "owned" for d in deck.DOMAIN.findall(action.get("what") or ""))


def _actions(doc, layout, m, study):
    """One to three actions, each the reader's own work: on the subject's pages, or a check of a page the answers cite;
    each resting on a count a row of the deck draws."""
    actions = _actions_of(doc)
    if not actions:
        return ["the quick deck has no action: give one to three, each on the subject's own pages or a check of a page the "
                "answers cite"]
    problems = [f"{len(actions)} actions: a quick deck holds at most {MAX_ACTIONS}"] if len(actions) > MAX_ACTIONS else []
    cited = deck._cited_domains(m)
    drawn = set().union(*(_drawn(r) for p in layout for r in p["rows"]))
    for n, action in enumerate(actions, 1):
        what = str(action.get("what") or "")
        asked = REQUEST.search(what)
        if asked:
            problems.append(f"action {n} asks a third party for a change ({asked.group(0)!r}): the quick deck suggests work "
                            f"on {m['subject']}'s own pages, or what the reader checks on a page the answers cite")
        sites = list(dict.fromkeys(d.lower() for d in deck.DOMAIN.findall(what)))
        if not sites:
            problems.append(f"action {n} names no site: give the page of {m['subject']} it works on, or the site it checks")
        for site in sites:
            if m["author"](site) != "third":
                continue
            if not deck.CHECK_FIRST.search(what):
                problems.append(f"action {n} works on {site}, a page {m['subject']} does not own: act on its own pages, or "
                                "start the action with what the reader checks there")
            elif not any(c == site or c.endswith("." + site) for c in cited):
                problems.append(f"action {n} checks {site}, which no answer cites: choose a site the answers read")
        why = str(action.get("why") or "")
        if not any((a, b) in drawn for part in deck.SENTENCE.split(why) for _, _, a, b in deck._spans(part)):
            problems.append(f"action {n} why gives no count a row of the deck draws: give the count it rests on, as the "
                            "row draws it (x su y)")
    return problems + deck._competitor_sites(doc, study)


def _allowed(m, period, layout):
    """The figures a text may cite: the full deck's, the sites the last slide lists and each project's figure on the
    summary."""
    decimals, percents, pairs = deck._allowed_figures(m, period)
    for key in ("reach", "description"):
        answers, sites = _cited(m, key)
        for _, n in sites:
            _ratio(n, answers, percents, pairs)
    for p in layout:
        for _, a, b in _headlines(p):
            _ratio(a, b, percents, pairs)
    return decimals, percents, pairs


def problems_of(folder, study, period, doc, layout=True):
    """What check refuses; `layout` adds the slides the estimate finds taller than their page."""
    if doc.get("schema") != SCHEMA:
        return [f"schema is not {SCHEMA}" + (": run deck --quick again, which adds the summary and the actions"
                                             if doc.get("schema") == FIRST_SCHEMA else "")]
    if "[[" in json.dumps(doc, ensure_ascii=False):
        left = deck._left(doc)
        return [f"a text is left to write: replace every [[...]] marker, {len(left)} left: {', '.join(left[:12])}"]
    lang = study["report_language"]
    m = _model(folder, study, period)
    plan = _layout(m, study, period)
    structure = _structure(doc, plan)
    texts = list(_texts(doc))
    names = period.get("names") or {}
    by_answer = deck._responses(folder, period)
    problems = structure + _excerpts(doc, plan, by_answer, names)
    for field, limit, text in texts:
        most = LIMITS["answer"] if field == SUMMARY_TITLE else LIMITS[limit]
        if len(text) > most:
            problems.append(f"{field} holds {len(text)} characters, at most {most}: {text[:60]!r}")
        # The summary, a row's sentence and an action are held to the full deck's ceilings; a slide's title keeps its own.
        ceiling = deck.WORD_LIMITS.get(limit) if limit != "title" or field == SUMMARY_TITLE else None
        if ceiling and deck.words(text) > ceiling:
            problems.append(f"{field} holds {deck.words(text)} words, at most {ceiling}: {text[:60]!r}")
        if not text.strip():
            problems.append(f"{field} is empty")
    problems += _restated(doc, plan) + _beside_summary(doc, plan) + _summary_figures(doc) + _actions(doc, plan, m, study)
    problems += deck._unseen_pages(doc, study, folder, period, texts)
    text = "\n".join(t for _, _, t in texts)
    allowed = _allowed(m, period, plan)
    problems += [f"a word about how the deck was built appears: {w.group(0)}" for w in deck.UNSAID.finditer(text)]
    problems += deck._reader_words(doc, m, study, texts) + deck._sweeping(doc, allowed[2], texts)
    problems += leaks(folder, study, period, text, folder.binding)
    shown = [*names.values(), *(n.split(": ", 1)[-1] for n in names.values())]
    answers = [a for pool in by_answer.values() for a in pool]
    quotable = deck._quotable(study)
    tied, read = deck._tied_counts(doc, m, lambda t: _unquote(t, quotable, answers), texts)
    problems += tied
    problems += _figures(_unquote(text, quotable, answers, shown), lang, (*allowed[:2], allowed[2] | read))
    # A deck whose slides are not the period's is not laid out: its rows would be drawn from what is missing.
    if structure:
        return problems
    problems += _summary_words(doc)
    return problems + (_overflowing(folder, study, period, doc, m, plan) if layout else [])


def _overflowing(folder, study, period, doc, m, plan):
    """The slides the estimate finds taller than their page; `pdf --quick` keeps the page count as the final word."""
    chosen = sentl_theme.resolve(folder)[0]
    slides = _slides(study, period, doc, m, plan, chosen)
    out = []
    for n, height in enumerate(fit.heights("".join(slides), deck.STYLE + STYLE + (chosen.get("css") or "")), 1):
        if height > fit.PAGE_HEIGHT:
            lines = math.ceil((height - fit.PAGE_HEIGHT) / LINE)
            what = ("shorten the summary's title or its sentences" if n == 2
                    else "shorten the actions' what and why" if n == len(slides) - 1
                    else "shorten its title, its rows' sentences or their excerpts" if 2 < n < len(slides)
                    else "it holds no text of the writer's: report it")
            out.append(f"slide {n} runs over its page by about {lines} line{'s' * (lines > 1)} of text: {what}")
    return out


def check(root, path, date=None, unattended=False):
    """The quick deck's problems. One that passes is the record of its period in history/reports.json, as a full deck
    is; `unattended`, one that fails is recorded as a draft of its period."""
    path = Path(path)
    day = date or path.name.split(".")[0]
    folder, day, study, period, _ = deck.load(root, day, "quick")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"{path} cannot be read ({exc})") from None
    if not isinstance(doc, dict):
        raise Refused(f"{path} is not a quick deck: it holds no object")
    problems = problems_of(folder, study, period, doc)
    deck._record(folder, day, period, path, problems, unattended, what="quick deck")
    return problems


# --- the page ---------------------------------------------------------------

def _figures_html(row, m, t, q):
    """A row's figures: the answers naming the subject, beside the competitor named most, for the questions that name no
    subject; the favourable answers, beside the neutral and unfavourable ones, for the others."""
    out = []
    reach = row.get("reach")
    if reach:
        rivals = _rivals(reach["foils"])
        rival = (q["rival_one" if len(rivals) == 1 else "rival_many"].format(names=", ".join(f"{label} {n}" for label, n in rivals))
                 if rivals else q["no_rival"] if reach["foils"] else "")
        label = q["naming"].format(subject=m["subject"]) + (f" · {rival}" if rival else "")
        out.append(f'<div class="q-fig"><div class="q-n">{reach["named"]} <span>{esc(t["of"])} {reach["given"]}</span></div>'
                   f'{deck._meter(reach["named"], reach["given"])}<div class="q-lab">{esc(label)}</div></div>')
    rated = row.get("description")
    if rated:
        bands, judged, other = rated["bands"], rated["judged"], rated.get("namesake") or 0
        label = q["bands_fidelity" if m.get("fidelity") else "bands"].format(mid=bands["3"], bad=bands["1-2"])
        label += f' · {q["bands_namesake"].format(n=other)}' if other else ""
        out.append(f'<div class="q-fig"><div class="q-n">{bands["4-5"]} <span>{esc(t["of"])} {judged}</span></div>'
                   f'{deck._bar([(bands["4-5"], "good"), (bands["3"], "mid"), (bands["1-2"], "low"), (other, "namesake")])}'
                   f'<div class="q-lab">{esc(label)}</div></div>')
    return "".join(out)


def _row_html(row, filled, m, t, q):
    e = filled.get("excerpt") if isinstance(filled.get("excerpt"), dict) else {}
    who = q["quote_who"].format(assistant=deck._public(e.get("assistant") or "", m["names"]), question=e.get("question") or "")
    return (f'<div class="q-row"><div class="q-dim">{esc(row["name"])}</div><div class="q-figs">{_figures_html(row, m, t, q)}</div>'
            f'<div><p class="q-says">{esc(filled.get("says") or "")}</p><p class="q-quote">«{esc(e.get("text") or "")}»'
            f'<span class="q-who"> — {esc(who)}</span></p></div></div>')


def _summary_html(doc, m, t, plan):
    """Slide 2: per project its figures, drawn by the code, and the writer's sentence on what lies behind them."""
    title, written = _summary_of(doc)
    captions = t["summary_caption"]
    rows = ""
    for p in plan:
        shown = _headlines(p)
        figures = "".join(f'<div class="sum-fig">{a} <small>{esc(t["of"])} {b}</small></div><div class="sum-cap">'
                          + esc(captions["description_fidelity" if kind == "description" and m["fidelity"] else kind]
                                .format(subject=m["subject"])) + "</div>" for kind, a, b in shown)
        many = " many" if len(shown) > 1 else ""
        rows += (f'<div class="sum-row"><div class="sum-group">{esc(p["name"])}</div><div class="sum-figs{many}">{figures}</div>'
                 f'<p class="sum-a">{esc(written.get(p["key"]) or "")}</p></div>')
    size = " one" if len(plan) == 1 else ""
    return f'{deck._kicker(t["found_kicker"])}<h1>{esc(title)}</h1><div class="summary{size}">{rows}</div>'


def _actions_html(doc, m, t, q):
    """The suggested actions, each marked as work on the subject's own pages or a check of a page the answers cite."""
    head = "".join(f"<th>{esc(c)}</th>" for c in t["actions_head"][:3])
    rows = ""
    for n, a in enumerate(_actions_of(doc), 1):
        who = t["action_who"]["owned"].format(subject=m["subject"]) if _owns(a, m) else q["action_check"]
        rows += (f'<tr><td class="num">{n}</td><td><span class="who">{esc(who)}</span><br>{esc(a.get("what") or "")}</td>'
                 f'<td>{esc(a.get("why") or "")}</td></tr>')
    return f'<h1>{esc(t["actions_kicker"])}</h1><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'


def _method(m, q, lang):
    """How the answers were read, without naming what rates them."""
    first = [q["count_note"], q["assistants"].format(makers=m["makers"])]
    if m["repeated"]:
        always = min(n for n, _ in m["spread"]) > max(len(r["assistants"]) for r in m["method"])
        first.append(q["asked_always" if always else "asked_some"])
    second = []
    if m["blocks"]["description"]["rows"]:
        bands = q["rating_bands_fidelity" if m["fidelity"] else "rating_bands"]
        second.append(q["rating"].format(subject=m["subject"], bands=bands))
    if m["blocks"]["reach"]["rows"]:
        names = [m["subject"], *(a for a in m["aliases"] if a != m["subject"])]
        listed = ", ".join(names[:-1]) + f" {DECK[lang]['or']} " + names[-1] if len(names) > 1 else names[0]
        second.append(q["presence"].format(subject=m["subject"], names=listed))
    return "".join(f'<p class="q-method">{esc(" ".join(p))}</p>' for p in (first, second) if p)


def _sites_html(m, q, lang):
    cols = []
    for key, head in (("reach", "reach_col"), ("description", "description_col")):
        if not m["blocks"][key]["rows"]:
            continue
        answers, sites = _cited(m, key)
        own = f' <span class="q-own">{esc(q["own_site"].format(subject=m["subject"]))}</span>'
        rows = "".join(f'<tr><td>{esc(d)}{own if m["author"](d) == "owned" else ""}</td><td class="q-c">{n}</td></tr>'
                       for d, n in sites) or f'<tr><td>{esc(q["no_sites"])}</td></tr>'
        cols.append(f'<div><h2>{esc(q[head].format(n=answers, subject=m["subject"]))}</h2><table>{rows}</table></div>')
    return (f'<div class="kicker">{esc(q["sources_kicker"])}</div><h1>{esc(q["sources_title"])}</h1>'
            f'<div class="q-cols">{"".join(cols)}</div>{_method(m, q, lang)}')


def _slides(study, period, doc, m, plan, chosen):
    """Each slide's <section>, in reading order."""
    lang = study["report_language"]
    t, q = DECK[lang], QUICK[lang]
    subject = m["subject"]
    days = span(period["from"], period["to"], lang)
    logo = f'<img src="{html.escape(chosen["logo"], quote=True)}" alt="">' if chosen.get("logo") else ""
    slides = _slides_of(doc)
    total = len(slides) + 4

    def foot(n):
        return f'<footer class="foot"><span>{logo}{esc(subject)} · {esc(days)}</span><span>{n} / {total}</span></footer>'

    totals = m["totals"]
    by_block = totals.get("by_block") or {}
    parts = (t["cover_parts"].format(reach=by_block["reach"], description=by_block["description"], subject=subject)
             if by_block.get("reach") and by_block.get("description") else "")
    what = q["cover_what_repeated" if m["repeated"] else "cover_what"].format(
        questions=totals["questions"], answers=totals["answers"], parts=parts,
        assistants=t["assistant_one"] if totals["assistants"] == 1 else t["assistant_many"])
    by = f'<div class="cover-line">{esc(t["cover_by"].format(by=m["by"]))}</div>' if m["by"] else ""
    out = [f'<section class="slide cover"><div class="band"></div><div class="cover-body">{logo}'
           f'<h1>{esc(t["cover_title"].format(subject=subject))}</h1><div class="cover-what">{esc(what)}</div>'
           f'<div class="cover-kind">{esc(q["kind"])} · {esc(days)}</div>{by}</div></section>',
           f'<section class="slide found">{_summary_html(doc, m, t, plan)}{foot(2)}</section>']
    topics = {(p["key"], r["key"]): r for p in plan for r in p["rows"]}
    for n, slide in enumerate(slides, 3):
        rows = "".join(_row_html(topics[slide.get("project"), r.get("dimension")], r, m, t, q) for r in _rows_of(slide)
                       if (slide.get("project"), r.get("dimension")) in topics)
        out.append(f'<section class="slide q-slide">{deck._kicker(slide.get("question") or "")}'
                   f'<h1>{esc(slide.get("title") or "")}</h1><div class="q-rows">{rows}</div>{foot(n)}</section>')
    out.append(f'<section class="slide actions few-actions">{_actions_html(doc, m, t, q)}{foot(total - 1)}</section>')
    out.append(f'<section class="slide q-sites">{_sites_html(m, q, lang)}{foot(total)}</section>')
    return [deck._tight_units(s) for s in out]


def page_of(root, date=None, option=None):
    """(the quick deck as one HTML page, its slides)."""
    folder, date, study, period, doc = deck.load(root, date, "quick")
    if doc is None:
        raise Refused(f"no quick deck for {date}: run deck --quick --date {date} and write its text first")
    chosen, _ = sentl_theme.resolve(folder, option)
    lang = study["report_language"]
    m = _model(folder, study, period)
    slides = _slides(study, period, doc, m, _layout(m, study, period), chosen)
    days = span(period["from"], period["to"], lang)
    font = f'<link rel="stylesheet" href="{html.escape(chosen["font_url"], quote=True)}">' if chosen.get("font_url") else ""
    style = sentl_theme.variables(chosen) + deck.STYLE + STYLE + (chosen.get("css") or "")
    text = (f'<!doctype html>\n<html lang="{html.escape(lang)}"><head><meta charset="utf-8">'
            f'<title>{esc(m["subject"])} · {esc(QUICK[lang]["share_kind"])} · {esc(days)}</title>'
            f"{font}<style>{style}</style></head><body>\n" + "\n".join(slides) + "\n</body></html>\n")
    return deck._tight_units(text), len(slides)


def render(root, date=None, option=None, printer=None):
    """reports/<date>.quick.html and .pdf; the copy to send goes to reports/share/."""
    folder, date, study, period, doc = deck.load(root, date, "quick")
    if doc is None:
        raise Refused(f"no quick deck for {date}: run deck --quick --date {date} and write its text first")
    # The estimate of each slide's height is left to the print, whose page count is the final word.
    found = problems_of(folder, study, period, doc, layout=False)
    if found:
        raise Refused(f"the quick deck fails check on {len(found)} point(s): run check on it, then pdf --quick again")
    text, slides = page_of(root, date, option)
    notes = "".join(f"{note}. " for note in sentl_theme.resolve(folder, option)[1])
    target = folder.path("reports", f"{date}.quick.html")
    pdf = folder.path("reports", f"{date}.quick.pdf")
    write_text(target, text)
    engine, failures = (printer or report_pdf.print_pdf)(target, pdf, deck.ENGINES)
    if not engine:
        why = "; ".join(failures) or "no PDF engine (chromium, google-chrome, weasyprint) is on this machine"
        return f"{notes}Wrote {target}. The PDF was not written ({why}): open the page in a browser and print it to PDF."
    count = deck.pages(pdf)
    if count != slides:
        over = deck._spilling(pdf, count, slides)
        where = f" (slide {', '.join(map(str, over))} runs over)" if over else ""
        raise Refused(f"{count} pages for {slides} slides{where}: shorten the text of that slide, then pdf --quick again")
    name = report_pdf.share_name(folder, study, date, QUICK[study["report_language"]]["share_kind"])
    shared = folder.path("reports", "share")
    shared.mkdir(exist_ok=True)
    copy = shared / f"{name}.pdf"
    shutil.copyfile(pdf, copy)
    return f"{notes}Wrote {target} and {pdf} ({slides} slides, engine: {engine}). To send: {copy}"
