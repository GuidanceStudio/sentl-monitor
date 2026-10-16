"""`check`: refuse a report whose quotes, figures, sections or wording break the rules
of ARCHITECTURE.md §The report."""

import re
from pathlib import Path

from .common import Refused, Study, fmt_percent, load_json, match_key, norm, round_half_up
from .i18n import SECTIONS
from .method import measured, report_order

HEADING = re.compile(r"^## (\d+)\. (.+?)\s*$", re.M)
SUBHEADING = re.compile(r"^#{3,4} (.+?)\s*$")
QUOTED = re.compile(r"«[^»\n]*»|“[^”\n]*”|\"[^\"\n]*\"")
DECIMAL = re.compile(r"(?<![\w.,])(\d+)([.,])(\d+)(?![.,]?\d)")
PERCENT = re.compile(r"(?<![\w.,])(\d+(?:[.,]\d+)?)\s?%")
COUNT = re.compile(r"(?<![\w.,])(\d+)\s+((?:[^\W\d]+\s+){0,3}?)(su|of)\s+(\d+)(?!\w|[.,]\d)", re.I)
ANSWER_WORD = re.compile(r"rispost|answer", re.I)
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


def _order(keys, expected, lang):
    problems = [f"section missing: {SECTIONS[lang][k]}" for k in expected if k not in keys]
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
    return decimals, percents, pairs


def _unquote(text, questions, answers, names=()):
    """Drop the assistants' names, which can carry a version number, and «...» spans that
    quote a question or an answer; keep the words of any other span."""
    for name in sorted(names, key=len, reverse=True):
        text = text.replace(name, " ")
    def keep(m):
        inner = m.group(0)[1:-1]
        if match_key(inner) in questions or (_plain(inner) and any(_plain(inner) in a for a in answers)):
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


def _prose(body):
    """The lines a figure is read from: no blockquotes and no headings."""
    return "\n".join(ln for ln in body.splitlines()
                      if not ln.lstrip().startswith(">") and not ln.lstrip().startswith("#"))


def _findings_parts(findings, study, period):
    """Split the findings into (heading, text, scopes) parts, one per entry. A dimension's
    entry may cite figures of the dimension and its questions, and its project's overall
    figure; any other part, figures of the projects."""
    owners = {}
    for proj, dims in measured(study):
        block = period["projects"].get(proj["key"])
        for d in dims if block else []:
            dim = block["dimensions"][d["key"]]
            overall = {"total": block["total"], "by_model": {}}
            owners.setdefault(d["name"], []).extend([overall, dim, *dim["questions"].values()])
    projects = list(period["projects"].values())
    parts, heading, lines, scopes = [], None, [], projects

    def flush():
        parts.append((heading, "\n".join(lines), scopes))

    for line in findings.splitlines():
        m = SUBHEADING.match(line)
        if not m:
            lines.append(line)
            continue
        flush()
        heading, lines, scopes = m.group(1), [], projects
        for name, allowed in owners.items():
            if re.match(re.escape(name) + r"(?::|\s+[—-]|\s*$)", heading):
                scopes = allowed
    flush()
    return parts


# --- the check --------------------------------------------------------------

def check(root, report_path, date=None):
    folder = Study(root)
    study = folder.study
    report_path = Path(report_path)
    date = date or report_path.stem.split(".")[0]
    period_path = folder.path("history", "periods", f"{date}.json")
    if not period_path.exists():
        raise Refused(f"no period for {date}: pass --date with the report's period")
    period = load_json(period_path)
    binding = folder.binding
    lang = study["report_language"]
    text = report_path.read_text(encoding="utf-8")

    found, problems = _sections(text, lang)
    problems += _order([k for k, _ in found], report_order(study), lang)
    if "[[" in text:
        problems.append("an entry is left to write: replace every [[...]] marker")

    body = dict(found)
    findings = body.get("findings", "")
    for _, dims in measured(study):
        for d in dims:
            if not re.search(r"^#{3,4} " + re.escape(d["name"]) + r"(?::|\s+[—-]|\s*$)", findings, re.M):
                problems.append(f"dimension {d['name']} has no findings entry")

    answers = [_plain(r["answer"]) for key, ids in period["runs"].items() for run_id in ids
               for r in folder.run(key, run_id)["responses"] if r["match"] != "unmatched" and r["answer"]]
    questions = {match_key(q["text"]) for p in study["projects"] for d in p["dimensions"] for q in d["questions"]}
    names = list(period.get("names", {}).values())

    for k in ("findings", "changes"):
        for excerpt in _excerpts(body.get(k, "")):
            pieces = _pieces(excerpt)
            if not _quoted_in(pieces, answers):
                problems.append(f"excerpt not found verbatim in any answer of the period: {excerpt[:80]!r}; "
                                + _stops_matching(pieces[0] if pieces else "", answers))

    for heading, part, scopes in _findings_parts(findings, study, period):
        if heading and (DECIMAL.search(heading) or PERCENT.search(heading)):
            problems.append(f"a findings heading carries a figure: {heading!r}")
        problems += _figures(_unquote(_prose(part), questions, answers, names), lang, _allowed(scopes))
    every_scope = [s for b in period["projects"].values() for s in [b, *b["dimensions"].values()]]
    every_scope += [q for b in period["projects"].values() for d in b["dimensions"].values() for q in d["questions"].values()]
    problems += _figures(_unquote(_prose(body.get("changes", "")), questions, answers, names), lang,
                         _allowed(every_scope))

    question_keys = {q["key"] for p in study["projects"] for d in p["dimensions"] for q in d["questions"]}
    for key in sorted(question_keys):
        if re.search(r"(?<![\w-])" + re.escape(key) + r"(?![\w-])", text):
            problems.append(f"question key {key} appears")
    model_ids = {m for p in study["projects"] for m in p.get("models") or []}
    model_ids |= {m for b in period["projects"].values() for m in b["by_model"]}
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
