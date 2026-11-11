"""The text tests `check` applies to a deck (deck.py) and to a comparison of two snapshots (snapcompare.py): excerpts
found verbatim in the answers, figures that are the period's, sections in their order, and nothing of the machine."""

import re

from .common import fmt_percent, match_key, norm, round_half_up
from .insights import tight
from .i18n import SECTIONS

HEADING = re.compile(r"^## (\d+)\. (.+?)\s*$", re.M)
QUOTED = re.compile(r"«[^»\n]*»|“[^”\n]*”|\"[^\"\n]*\"")
DECIMAL = re.compile(r"(?<![\w.,])(\d+)([.,])(\d+)(?![.,]?\d)")
PERCENT = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s?%")
COUNT = re.compile(r"(?<![\w.,])(\d+)\s+((?:[^\W\d]+\s+){0,3}?)(su|of the|of|out of|delle|degli|dei)\s+(\d+)(?!\w|[.,]\d)", re.I)
# What else "x of y" may count: every other count is read as one of answers.
OTHER_UNIT = re.compile(r"\b(?:domand[ae]|questions?|assistent[ei]|assistants?|nom[ei]|names?|sit[io]|sites?|pagin[ae]|pages?"
                        r"|font[ei]|sources?|slide|temi|topics?|mes[ei]|months?|giorn[oi]|days?|ann[oi]|years?)\b", re.I)
FILE_NAME = re.compile(r"\b[\w-]+(?:\.[\w-]+)*\.(?:json|gz|md|py|csv|xlsx)\b", re.I)
CREDIT = re.compile(r"\d[\d.,]*\s*(?:crediti|credito|credits?)\b|\b(?:crediti|credito|credits?)\s*:?\s*\d", re.I)
ID_WORDS = r"(?:run|id|project|progetto|question|domanda|dimension|dimensione)"
ELLIPSIS = re.compile(r"\s*(?:\[…\]|\[\.\.\.\]|\(…\)|\(\.\.\.\))\s*")
CITATION = re.compile(r"\[\d+(?:\s*[,-]\s*\d+)*\]")
MARKUP = str.maketrans("", "", "*_`")


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


def _allowed(scopes):
    decimals, percents, pairs = set(), set(), set()
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
            pairs |= {(n, p["given"]) for n in (c.get("foils") or {}).values()}
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
        plain = _plain(inner)
        if tight(match_key(inner)) in questions or (plain and any(plain in a for a in answers)):
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
        if OTHER_UNIT.search(f"{m.group(2)} {' '.join(tail.split()[:1])}"):
            continue
        a, b = int(m.group(1)), int(m.group(4))
        if (a, b) not in pairs:
            problems.append(f"count {a} {m.group(3)} {b} is not in the period's figures for this part")
    return problems


def leaks(folder, study, period, text, binding):
    """What of the machine shows in a text the reader gets: keys, ids, file names, credit figures."""
    problems = []
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
    return problems


def _shown(folder, path):
    try:
        return path.resolve().relative_to(folder.root.resolve()).as_posix()
    except ValueError:
        return str(path)
