"""`check`: refuse a report whose quotes, figures, sections or wording break the rules
of ARCHITECTURE.md §The report."""

import datetime as dt
import os
import re
from pathlib import Path

from .common import MONTHS, Refused, Study, fmt_date, fmt_percent, load_json, match_key, norm, round_half_up
from .compare import dimension_entries
from .insights import fact_terms, tight
from .i18n import SECTIONS
from .method import halves_line, measured, report_order

HEADING = re.compile(r"^## (\d+)\. (.+?)\s*$", re.M)
SUBHEADING = re.compile(r"^#{3,4} (.+?)\s*$")
QUOTED = re.compile(r"«[^»\n]*»|“[^”\n]*”|\"[^\"\n]*\"")
DECIMAL = re.compile(r"(?<![\w.,])(\d+)([.,])(\d+)(?![.,]?\d)")
PERCENT = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s?%")
COUNT = re.compile(r"(?<![\w.,])(\d+)\s+((?:[^\W\d]+\s+){0,3}?)(su|of)\s+(\d+)(?!\w|[.,]\d)", re.I)
# A count of answers names them, or the citing they did: "N of M answers", "N su M citano".
ANSWER_WORD = re.compile(r"rispost|answer|\bcit(?:e|es|ing|a|ano)\b", re.I)
FILE_NAME = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:json|gz|md|py|csv|xlsx)\b", re.I)
CREDIT = re.compile(r"\d[\d.,]*\s*(?:crediti|credito|credits?)\b|\b(?:crediti|credito|credits?)\s*:?\s*\d", re.I)
ID_WORDS = r"(?:run|id|project|progetto|question|domanda|dimension|dimensione)"
ELLIPSIS = re.compile(r"\s*(?:\[…\]|\[\.\.\.\]|\(…\)|\(\.\.\.\))\s*")
CITATION = re.compile(r"\[\d+(?:\s*[,-]\s*\d+)*\]")
MARKUP = str.maketrans("", "", "*_`")
ONLY = {"it": ("solo", "soltanto", "solamente", "unicamente", "esclusivamente"),
        "en": ("only", "solely", "exclusively", "just")}
CLAUSE_REACH = 40
CLAUSE_END = re.compile(r"[,;:.!?]")
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
# Between the two days of a span: «14–16», «dal 2 all'8», «from 2 to 8», «tra il 2 e l'8».
SPAN_JOIN = r"\s*(?:[–—-]|all['’]|e\s+l['’]|(?:al|ai|a|e|ed|to|and|until|till|through)\b)\s*(?:il\s+|l['’])?"


def _plain(text):
    """Comparison form of answers and excerpts: markup and citation markers dropped."""
    return norm(CITATION.sub("", norm(text or "")).translate(MARKUP))


# --- sections ---------------------------------------------------------------

def _sections(text, lang):
    titles = {v: k for k, v in SECTIONS[lang].items()}
    found, problems = [], []
    marks = list(HEADING.finditer(text))
    for i, m in enumerate(marks):
        key = titles.get(m.group(2))
        if key is None:
            problems.append(f"section heading not recognised: {m.group(2)!r}")
            continue
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        found.append((key, text[m.end():end]))
    return found, problems


def _order(keys, expected, lang, snapshot=False):
    problems = [f"section missing: {SECTIONS[lang][k]}" for k in expected if k not in keys]
    if snapshot:
        problems += [f"a snapshot report has no section {SECTIONS[lang][k]}" for k in dict.fromkeys(keys)
                     if k not in expected]
    present = [k for k in keys if k in expected]
    if present != [k for k in expected if k in present]:
        problems.append("sections out of order: expected " + ", ".join(SECTIONS[lang][k] for k in expected))
    return problems


# --- quotes -----------------------------------------------------------------

def _excerpts(body):
    """Blockquote paragraphs, each joined into one excerpt."""
    out, current = [], []
    for line in body.splitlines() + [""]:
        if line.lstrip().startswith(">"):
            current.append(line.lstrip()[1:].strip())
        elif current:
            out.append(" ".join(current))
            current = []
    return out


def _pieces(excerpt):
    text = excerpt.strip().strip("«»“”\"'").strip()
    text = re.sub(r"^(?:…|\.\.\.)\s*|\s*(?:…|\.\.\.)$", "", text)
    return [p for p in (_plain(x) for x in ELLIPSIS.split(text)) if p]


def _quoted_in(pieces, answers):
    for answer in answers:
        at = 0
        for piece in pieces:
            found = answer.find(piece, at)
            if found < 0:
                break
            at = found + len(piece)
        else:
            return True
    return False


def _stops_matching(piece, answers):
    """Where the piece stops matching its closest answer: the longest prefix found in any."""
    best = 0
    for answer in answers:
        lo, hi = best, len(piece)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if piece[:mid] in answer:
                lo = mid
            else:
                hi = mid - 1
        best = max(best, lo)
    char = piece[best:best + 1]
    code = f" (U+{ord(char):04X})" if char and ord(char) > 127 else ""
    return f"stops matching after {piece[max(0, best - 30):best]!r}, at {piece[best:best + 20]!r}{code}"


# --- figures ----------------------------------------------------------------

def _cells(scope):
    yield scope["total"]
    yield from scope["by_model"].values()


def _compared(entries, verdicts):
    """The decimals and percentages a comparison lets a report cite: the values of its
    entries (dimensions, questions, projects), their moves and ranges, and the pair means of
    its verdict changes."""
    decimals, percents = set(), set()
    for e in entries:
        if e.get("mean"):
            m = e["mean"]
            decimals |= {round_half_up(v, 1) for v in (m["now"], m["previous"], abs(m["delta"]), *m["range"])}
        for kind in ("presence", "current_share"):
            if e.get(kind):
                m = e[kind]
                percents |= {int(fmt_percent(v)[:-1]) for v in (m["now"], m["previous"], abs(m["delta"]), *m["range"])}
    decimals |= {round_half_up(v[k], 1) for v in verdicts for k in ("previous_mean", "mean")}
    return decimals, percents


def _allowed(scopes, extra=(set(), set())):
    decimals, percents, pairs = set(extra[0]), set(extra[1]), set()
    for scope in scopes:
        for c in _cells(scope):
            if not c["figure"]:
                continue
            for value in (c["mean"], c["presence"]["position"]):
                if value is not None:
                    decimals.add(round_half_up(value, 1))
            for ratio in (c["coverage"], c["presence"]["rate"]):
                if ratio is not None:
                    percents.add(int(fmt_percent(ratio)[:-1]))
        for c in _cells(scope):
            p = c["presence"]
            pairs |= {(c["judged"], c["expected"]), (c["judged"], c["received"]), (c["received"], c["expected"]),
                      (p["named"], p["given"]), (c["owned"]["citing"], c["owned"]["with_sources"])}
            if "readings" in c:
                pairs |= {(c["readings"], p["given"]), (c["readings"], c["received"])}
                a = c["authors"]
                for n in (a["owned"], a["foil"], a["third"]):
                    _ratio(n, a["with_sources"], percents, pairs)
        _insights(scope, decimals, percents, pairs)
    return decimals, percents, pairs


def _ratio(n, m, percents, pairs):
    pairs.add((n, m))
    if m:
        percents.add(int(fmt_percent(n / m)[:-1]))


def _insights(scope, decimals, percents, pairs):
    """The figures of a question's insights (DEVPLAN M2b). Counts and shares of answers may be
    cited whatever the coverage; means only where the question has a figure."""
    figure = scope.get("total", {}).get("figure")
    facts = scope.get("facts")
    if facts:
        cells = [facts["total"], *facts["by_model"].values()]
        cells += [c for run in facts["runs"] for c in (run["total"], *run["by_model"].values())]
        for c in cells:
            s = c["stating"]
            for n in (c["current_only"], c["outdated_only"], c["both"], c["current_only"] + c["both"],
                      c["outdated_only"] + c["both"]):
                _ratio(n, s, percents, pairs)
            for n in (s, c["current_only"], c["outdated_only"], c["both"]):
                _ratio(n, c["given"], percents, pairs)
    for e in (e for entries in (scope.get("group_sources") or {}).values() for e in entries):
        for g in (e, e["other"]):
            _ratio(g["citing"], g["answers"], percents, pairs)
    for r in scope.get("presence_runs") or []:
        _ratio(r["named"], r["given"], percents, pairs)
    for e in scope.get("episodes") or []:
        values = e["values"] + e["range"] + [x["value"] for x in e.get("later") or []]
        if e["measure"] != "mean":
            percents |= {int(fmt_percent(v)[:-1]) for v in values}
        elif figure:
            decimals |= {round_half_up(v, 1) for v in values}
    for m in (scope.get("missing") or {}).values():
        _ratio(m["answers"], m["given"], percents, pairs)
        _ratio(m["answers"], m["judged"], percents, pairs)
        if figure:
            decimals |= {round_half_up(v, 1) for v in (m["mean"], m["mean_without"]) if v is not None}


def _unquote(text, questions, answers, names=()):
    """Drop the assistants' names, which can carry a version number, and «...» spans that
    quote a question, a fact term of the study or an answer; keep the words of any other span."""
    for name in sorted(names, key=len, reverse=True):
        text = text.replace(name, " ")
    def keep(m):
        inner = m.group(0)[1:-1]
        if tight(match_key(inner)) in questions or (_plain(inner) and any(_plain(inner) in a for a in answers)):
            return " "
        return " " + inner + " "
    return QUOTED.sub(keep, text)


def _figures(text, lang, allowed):
    decimals, percents, pairs = allowed
    problems = []
    for m in PERCENT.finditer(text):
        value = float(m.group(1).replace(",", "."))
        if value != int(value) or int(value) not in percents:
            problems.append(f"percentage {m.group(0).strip()} is not in the period's figures for this part")
    text = PERCENT.sub(" ", text)
    point = "," if lang == "it" else "."
    for m in DECIMAL.finditer(text):
        whole, sep, frac = m.groups()
        if sep != point and len(frac) == 3:
            continue  # a thousands separator: an integer, not checked
        if sep != point:
            problems.append(f"figure {m.group(0)} uses the wrong decimal separator for this report's language")
        elif len(frac) != 1 or round_half_up(float(f"{whole}.{frac}"), 1) not in decimals:
            problems.append(f"figure {m.group(0)} is not in the period's figures for this part")
    for m in COUNT.finditer(text):
        tail = text[m.end():m.end() + 40]
        if not ANSWER_WORD.search(m.group(2) + " " + tail):
            continue
        a, b = int(m.group(1)), int(m.group(4))
        if (a, b) not in pairs:
            problems.append(f"count {a} {m.group(3)} {b} is not in the period's figures for this part")
    return problems


def _day_number(day):
    return "1°?" if day.day == 1 else str(day.day)


def _date(day, lang):
    """A date as a report writes it, the year optional: «14 ottobre», «14 October», «October 14»;
    the first of the month also as «1°». A numeric date or an abbreviated month is not read: the
    report's own date formatter writes neither."""
    d = dt.date.fromisoformat(day)
    month = MONTHS[lang][d.month - 1]
    forms = [r"(?<!\d)" + _day_number(d) + r"\s+" + month + r"\b"]
    if lang == "en":
        forms.append(r"\b" + month + r"\s+" + str(d.day) + r"(?!\d)")
    return re.compile("|".join(forms), re.I)


def _span(episode):
    """An episode's days written as a span, the month optional: «14–16», «dal 2 all'8»,
    «from 2 to 8», «tra il 2 e l'8»."""
    first, last = (dt.date.fromisoformat(episode[k]) for k in ("first", "last"))
    return re.compile(r"(?<!\d)" + _day_number(first) + SPAN_JOIN + _day_number(last) + r"(?!\d)", re.I)


def _sentences(text):
    """The sentences of a section's prose: the lines of a paragraph joined, then split at blank
    lines, list items, headings, blockquotes and sentence ends."""
    paragraphs, lines = [], []
    for line in text.splitlines() + [""]:
        bare, item = line.strip(), LIST_ITEM.match(line)
        if not bare or bare.startswith(("#", ">")) or item:
            if lines:
                paragraphs.append(" ".join(lines))
            lines = [LIST_ITEM.sub("", line).strip()] if item else []
        else:
            lines.append(bare)
    return [s for paragraph in paragraphs for s in SENTENCE_END.split(paragraph) if s]


def _closed_episodes(scopes):
    """The closed episodes of the questions under `scopes` (projects, dimensions or questions), once each."""
    found = {}

    def walk(scope):
        found.update({id(e): e for e in scope.get("episodes") or [] if e.get("closed")})
        for child in (*(scope.get("dimensions") or {}).values(), *(scope.get("questions") or {}).values()):
            walk(child)
    for scope in scopes:
        walk(scope)
    return list(found.values())


def _only_beside_episodes(text, episodes, lang):
    """An episode's close date is the first run back inside its range; it says nothing about the
    runs after it. A sentence is refused when a word for «only» comes before an episode's span,
    first, last or close date in the same clause (no , ; : . ! ? between them, the date starting
    within CLAUSE_REACH characters), later runs of the period lie on the episode's side, and the
    sentence does not name every one of them. `episodes`: the closed episodes the text may speak of.
    Quoted spans are not read."""
    words = re.compile(r"\b(?:" + "|".join(ONLY[lang]) + r")\b", re.I)
    problems = []
    for sentence in _sentences(text):
        plain = QUOTED.sub(" ", sentence)
        found = next(((word, e) for word in words.finditer(plain) for e in episodes if e.get("later")
                      and _before_episode(CLAUSE_END.split(plain[word.end():], maxsplit=1)[0], e, lang)
                      and not all(_date(x["date"], lang).search(plain) for x in e["later"])), None)
        if found:
            word, e = found
            later = ", ".join(fmt_date(x["date"], lang) for x in e["later"])
            problems.append(f"«{word.group(0)}» beside the episode from {e['first']} to {e['last']}, but later "
                            f"runs of the period lie on its side ({later}): {sentence.strip()[:80]!r}; state those "
                            f"runs instead of «{word.group(0)}»")
    return problems


def _before_episode(clause, episode, lang):
    """Whether the clause after the word opens, within CLAUSE_REACH characters, on the episode's span
    or on its first, last or close date."""
    refs = [_span(episode)] + [_date(episode[k], lang) for k in ("first", "last", "closed")]
    return any(m and m.start() <= CLAUSE_REACH for m in (ref.search(clause) for ref in refs))


def _prose(body):
    """The lines a figure is read from: no blockquotes and no headings."""
    return "\n".join(ln for ln in body.splitlines()
                      if not ln.lstrip().startswith(">") and not ln.lstrip().startswith("#"))


def _hide_figures(block):
    """A project's block with its figures withheld and its counts kept: a snapshot reads each
    dimension on its own and states no figure for the whole project."""
    return {**block, "total": {**block["total"], "figure": False},
            "by_model": {m: {**c, "figure": False} for m, c in block["by_model"].items()}}


def _findings_parts(findings, projects, period, extras, snapshot=False):
    """Split the findings into (owner, heading, text, scopes, extra) parts, one per entry.
    With several projects, a `### <project>` heading opens each project's chapter. An entry's
    owner is its (project, dimension); it may cite figures of that dimension and its
    questions, their comparison (`extras`), and its project's overall
    figure. Any other part may cite figures of the projects. `extras` is keyed by project and
    dimension key, since two projects may share a dimension key."""
    owners = {}
    for proj, dims in projects:
        block = period["projects"][proj["key"]]
        overall = {"total": (_hide_figures(block) if snapshot else block)["total"], "by_model": {}}
        for d in dims:
            dim = block["dimensions"][d["key"]]
            owners[(proj["name"], d["name"])] = ([overall, dim, *dim["questions"].values()],
                                                 extras.get((proj["key"], d["key"]), (set(), set())))
    titles = {proj["name"] for proj, _ in projects} if len(projects) > 1 else set()
    fallback = ([_hide_figures(b) if snapshot else b for b in period["projects"].values()], (set(), set()))
    project = projects[0][0]["name"] if len(projects) == 1 else None
    parts, owner, heading, lines = [], None, None, []

    def flush():
        parts.append((owner, heading, "\n".join(lines), *owners.get(owner, fallback)))

    for line in findings.splitlines():
        m = SUBHEADING.match(line)
        if not m:
            lines.append(line)
            continue
        flush()
        owner, heading, lines = None, m.group(1), []
        if line.startswith("### ") and heading in titles:
            project, heading = heading, None
            continue
        owner = next((key for key in owners if key[0] == project
                      and re.match(re.escape(key[1]) + r"(?::|\s+[—-]|\s*$)", heading)), None)
    flush()
    return parts


def _answers(folder, period):
    return [_plain(r["answer"]) for key, ids in period["runs"].items() for run_id in ids
            for r in folder.run(key, run_id)["responses"] if r["match"] != "unmatched" and r["answer"]]


# --- the check --------------------------------------------------------------

def check(root, report_path, date=None, unattended=False):
    folder = Study(root)
    study = folder.study
    report_path = Path(report_path)
    date = date or report_path.stem.split(".")[0]
    period_path = folder.path("history", "periods", f"{date}.json")
    if not period_path.exists():
        raise Refused(f"no period for {date}: pass --date with the report's period")
    period = load_json(period_path)
    if any("later" not in e for e in _closed_episodes(period["projects"].values())):
        raise Refused(f"the period of {date} was built before episodes recorded the runs after their close: run "
                      f"period --date {date} again, then check the report")
    comparison = period.get("comparison") or {}
    previous_path = folder.path("history", "periods", f"{comparison.get('previous')}.json")
    previous = load_json(previous_path) if comparison.get("previous") and previous_path.exists() else None
    folder.require_runs([period] + ([previous] if previous else []), date)
    binding = folder.binding
    lang = study["report_language"]
    text = report_path.read_text(encoding="utf-8")

    found, problems = _sections(text, lang)
    snapshot = study.get("kind") == "snapshot"
    problems += _order([k for k, _ in found], report_order(folder, date), lang, snapshot)
    if "[[" in text:
        problems.append("an entry is left to write: replace every [[...]] marker")

    body = dict(found)
    findings = body.get("findings", "")
    projects = measured(study, period)
    entries = {at: [e, *e.get("questions", {}).values()] for at, e in dimension_entries(comparison).items()}
    verdicts = comparison.get("verdict_changes", [])
    extras = {at: _compared(es, [v for v in verdicts if (v["project"], v["dimension"]) == at])
              for at, es in entries.items()}
    parts = _findings_parts(findings, projects, period, extras, snapshot)
    written = {owner for owner, *_ in parts}
    for proj, dims in projects:
        problems += [f"dimension {d['name']} has no findings entry" + (f" under {proj['name']}" if len(projects) > 1 else "")
                     for d in dims if (proj["name"], d["name"]) not in written]

    answers = _answers(folder, period)
    # The changes section may quote the previous period, where a verdict change starts.
    earlier = _answers(folder, previous) if previous else []
    questions = {match_key(q["text"]) for p in study["projects"] for d in p["dimensions"] for q in d["questions"]}
    questions |= {match_key(q["text"]) for p in study["projects"] for v in folder.versions(p["key"])
                  for d in v["dimensions"] for q in d["questions"]}
    # A fact term quoted in «» is named, not cited as a figure: the current price no answer gives.
    terms = (fact_terms(q) or {} for p in study["projects"] for d in p["dimensions"] for q in d["questions"])
    questions = {tight(t) for t in questions} | {tight(match_key(t)) for found in terms for ts in found.values()
                                                 for t in ts}
    names = list(period.get("names", {}).values())

    for k, pool in (("findings", answers), ("changes", answers + earlier)):
        for excerpt in _excerpts(body.get(k, "")):
            pieces = _pieces(excerpt)
            if not _quoted_in(pieces, pool):
                problems.append(f"excerpt not found verbatim in any answer of the period: {excerpt[:80]!r}; "
                                + _stops_matching(pieces[0] if pieces else "", pool))

    for _, heading, part, scopes, extra in parts:
        if heading and (DECIMAL.search(heading) or PERCENT.search(heading)):
            problems.append(f"a findings heading carries a figure: {heading!r}")
        problems += _figures(_unquote(_prose(part), questions, answers, names), lang, _allowed(scopes, extra))
    # The summary may cite any figure of the period and of its comparison, never an excerpt.
    summary = body.get("summary", "")
    if any(line.lstrip().startswith(">") for line in summary.splitlines()):
        problems.append("the summary quotes an answer: state each point in a plain sentence with its figure")
    every_scope = [s for b in period["projects"].values() for s in [b, *b["dimensions"].values()]]
    every_scope += [q for b in period["projects"].values() for d in b["dimensions"].values() for q in d["questions"].values()]
    every_scope += list((previous or {}).get("projects", {}).values())
    compared = _compared([e for es in entries.values() for e in es] + list(comparison.get("projects", {}).values()),
                         verdicts)
    # A first period with no earlier one compares its two halves: the changes may cite the
    # overall figures of both, and must name them.
    halves = comparison.get("halves")
    half_blocks = []
    if halves:
        if halves_line(halves, lang, study["projects"]) not in body.get("changes", ""):
            problems.append("the changes section does not name the two halves of the period and their dates: keep "
                            "the line method wrote above the changes in the answers")
        for half in ("first", "second"):
            path = folder.path("history", "periods", f"{date}.{half}.json")
            if not path.exists():
                raise Refused(f"the {half} half of the period of {date} is missing from history/periods: "
                              f"run period --date {date} again, then method --force and the report's entries")
            half_blocks += list(load_json(path)["projects"].values())
    problems += _figures(_unquote(_prose(body.get("changes", "")), questions, answers + earlier, names), lang,
                         _allowed(every_scope + half_blocks, compared))
    period_scopes = [s for s in every_scope if s not in list((previous or {}).get("projects", {}).values())]
    problems += _figures(_unquote(_prose(summary), questions, answers, names), lang, _allowed(period_scopes, compared))
    every_episode = _closed_episodes(period["projects"].values())
    for _, _, part, scopes, _ in parts:
        problems += _only_beside_episodes(part, _closed_episodes(scopes), lang)
    for key in ("summary", "changes"):
        problems += _only_beside_episodes(body.get(key, ""), every_episode, lang)

    question_keys = {q["key"] for p in study["projects"] for d in p["dimensions"] for q in d["questions"]}
    for key in sorted(question_keys):
        if re.search(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", text):
            problems.append(f"question key {key} appears")
    model_ids = {m for p in study["projects"] for m in p.get("models") or []}
    model_ids |= {m for b in period["projects"].values() for m in b["by_model"]}
    model_ids |= set(period.get("names", {}))
    problems += [f"model id {m} appears" for m in sorted(model_ids) if m in text]
    ids = {str(run_id) for ids in period["runs"].values() for run_id in ids}
    for proj in binding["projects"].values():
        ids.add(str(proj["project_id"]))
        ids.update(str(v) for v in proj["dimensions"].values())
        ids.update(str(v) for v in proj["questions"].values())
    for m in re.finditer(ID_WORDS + r"\s*(?:n\.\s*|#\s*)?(\d+)\b|#(\d+)\b", text, re.I):
        if (m.group(1) or m.group(2)) in ids:
            problems.append(f"an id appears: {m.group(0)!r}")
    problems += [f"a file name appears: {m.group(0)}" for m in FILE_NAME.finditer(text)]
    problems += [f"a credit figure appears: {m.group(0)}" for m in CREDIT.finditer(text)]

    entry = {"date": date, "status": "final",
             "period": {"from": period["from"], "to": period["to"]}, "runs": period["runs"],
             "previous": comparison.get("previous")}
    if not problems:
        entry["file"] = _shown(folder, report_path)
        folder.record_report(entry)
        folder.record_outcome("written", f"report of {date} passed check")
    elif unattended:
        # An unattended report that fails check is kept beside the final ones and counts as the
        # previous report, so the next invocation finds no run it has not seen.
        draft = report_path.with_name(f"{date}.draft.md")
        if draft != report_path:
            os.replace(report_path, draft)
        folder.record_report({**entry, "file": _shown(folder, draft), "status": "draft"})
        shown = "; ".join(problems[:3]) + (f"; and {len(problems) - 3} more" if len(problems) > 3 else "")
        folder.record_outcome("draft", f"check found {len(problems)} problem(s): {shown}")
    return problems


def _shown(folder, path):
    try:
        return path.resolve().relative_to(folder.root.resolve()).as_posix()
    except ValueError:
        return str(path)
