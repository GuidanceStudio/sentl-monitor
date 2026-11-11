"""`compare`: what changed between two snapshots of one subject that were not promoted. `report` compares a
promoted study with its snapshot, so this serves only two one-off reads with no study between them. The figures
come from the two periods, restricted to the assistants both sides asked, and a change follows §What counts as a
change with one run on each side."""

from pathlib import Path

from .check import _order, _sections, leaks
from .common import (Refused, Study, fmt_date, fmt_decimal, fmt_percent, load_json, match_key, measured, public_name, write_json,
                     write_text)
from .compare import STEPS, _models, _pool, called
from .i18n import COMPARE, COMPARE_ORDER, SECTIONS, join


class _Side:
    """One snapshot folder: its period, its project and its questions as the run asked them."""

    def __init__(self, root):
        self.folder = Study(root)
        self.study = self.folder.study
        if self.study.get("kind") != "snapshot":
            raise Refused(f"{root} is not a snapshot: a monitored study compares its periods with report")
        dated = [p for p in self.folder.path("history", "periods").glob("*.json") if "." not in p.stem]
        if not dated:
            raise Refused(f"{root} has no period: run period there first")
        self.period = load_json(max(dated))
        self.date = self.period["date"]
        self.project, dimensions = measured(self.study, self.period)[0]
        self.bound = self.folder.binding["projects"][self.project["key"]]
        self.block = self.period["projects"][self.project["key"]]
        self.dimensions = dimensions
        self.questions = {q["key"]: {"text": q["text"], "dimension": d["key"], "id": self.bound["questions"].get(q["key"])}
                          for d in dimensions for q in d["questions"]}

    def name(self, model):
        return self.period.get("names", {}).get(model) or public_name(model, {})


def _pairs(first, second):
    """The two keys of each question: by Sentl's id within one project, by text across two."""
    same = first.bound["project_id"] == second.bound["project_id"]

    def index(side):
        return {(q["id"] if same else match_key(q["text"])): k for k, q in side.questions.items()}

    a, b = index(first), index(second)
    only = [(side, [side.questions[keys[x]]["text"] for x in keys if x not in other])
            for side, keys, other in ((first, a, b), (second, b, a))]
    if any(texts for _, texts in only):
        shown = "; ".join(f"only on {side.date}: " + ", ".join(f"«{t}»" for t in texts) for side, texts in only if texts)
        raise Refused(f"the two snapshots do not ask the same questions ({shown}): compare needs the same questions on "
                      "both sides")
    return [(a[x], b[x]) for x in a]


def _dimensions(first, second, pairs):
    """Each dimension of the first side with its questions and the one dimension that holds them on the second."""
    grouped = {}
    for ka, kb in pairs:
        grouped.setdefault(first.questions[ka]["dimension"], []).append((ka, kb))
    out = []
    for d in first.dimensions:
        keys = grouped.get(d["key"], [])
        others = {second.questions[kb]["dimension"] for _, kb in keys}
        if len(others) != 1:
            raise Refused(f"the questions of the dimension {d['name']} sit in {len(others)} dimensions of the snapshot of "
                          f"{second.date}: compare needs the same dimensions on both sides")
        out.append((d, others.pop(), [ka for ka, _ in keys], [kb for _, kb in keys]))
    return out


def _figures(side, key, questions, models):
    block = side.block["dimensions"][key]
    pooled = _pool(block, questions, models)
    return (pooled["mean"] if block["total"].get("figure") else None), pooled["presence"]


def _change(before, now, kind, words):
    if before is None or not called(now, [before], kind):
        return None
    return words[0] if now > before else words[1]


def _row(name, a, b, t, lang):
    score = [fmt_decimal(v, lang) if v is not None else t["no_figure"] for v in (a[0], b[0])]
    presence = [fmt_percent(v) if v is not None else t["no_figure"] for v in (a[1], b[1])]
    changes = [c for c in (_change(a[0], b[0], "mean", (t["higher_score"], t["lower_score"])),
                           _change(a[1], b[1], "presence", (t["higher_presence"], t["lower_presence"]))) if c]
    return f"| {name} | {score[0]} | {score[1]} | {presence[0]} | {presence[1]} | {join(changes, lang) if changes else t['no_change']} |"


def write(first_root, second_root):
    first, second = _Side(first_root), _Side(second_root)
    if first.date >= second.date:
        raise Refused(f"{first_root} is of {first.date} and {second_root} of {second.date}: pass the earlier snapshot "
                      "first")
    lang = second.study["market"]["language"]
    t = COMPARE[lang]
    a_models, b_models = _models(first.block), _models(second.block)
    models = sorted(a_models & b_models)
    if not models:
        raise Refused("the two snapshots share no assistant: nothing can be compared")
    pairs = _pairs(first, second)
    dates = [fmt_date(s.date, lang) for s in (first, second)]
    rows = [_row(d["name"], _figures(first, d["key"], qa, models), _figures(second, other, qb, models), t, lang)
            for d, other, qa, qb in _dimensions(first, second, pairs)]
    limits = [t["limits"]]
    if a_models != b_models:
        limits.append(t["shared"].format(models=join([second.name(m) for m in models], lang)))
    head = [t["dimension"], *[t["score"].format(date=d) for d in dates], *[t["presence"].format(date=d) for d in dates],
            t["change"]]
    subject = second.study["subject"]["label"]
    sections = SECTIONS[lang]
    text = [f"# {t['title'].format(subject=subject)}", "",
            f"## 1. {sections['purpose']}", "",
            t["purpose"].format(subject=subject, first=dates[0], second=dates[1], questions=len(pairs),
                                models=join([second.name(m) for m in models], lang)), "",
            f"## 2. {sections['changes']}", "",
            "| " + " | ".join(head) + " |", "|" + "---|" * len(head), *rows, "",
            t["rule"].format(subject=subject, score=fmt_decimal(STEPS["mean"][1], lang),
                             presence=round(STEPS["presence"][1] * 100)), "",
            f"## 3. {sections['limits']}", "", *limits, ""]
    report = second.folder.path("reports", f"{second.date}.compare.md")
    write_text(report, "\n".join(text))
    write_json(second.folder.path("history", "compare", f"{second.date}.json"),
               {"schema": "sentl-monitor/compare@1", "first": {"folder": str(Path(first_root).resolve()), "date": first.date},
                "second": {"date": second.date}, "rows": rows, "limits": limits})
    return f"Wrote {report}: {len(rows)} dimensions, {len(pairs)} questions. Run check on it."


def check(root, report):
    """The problems of a compare report: its order, its rows as `compare` wrote them, its limits, and nothing of the
    machine in the text."""
    side = _Side(root)
    path = Path(report)
    saved = side.folder.path("history", "compare", f"{path.name.split('.')[0]}.json")
    if not saved.exists():
        raise Refused(f"{path.name} has no record in history/compare: run compare again")
    data = load_json(saved)
    text = path.read_text(encoding="utf-8")
    lang = side.study["market"]["language"]
    found, problems = _sections(text, lang)
    problems += _order([k for k, _ in found], COMPARE_ORDER, lang)
    problems += [f"a row differs from the two snapshots: {row}" for row in data["rows"] if row not in text]
    limits = dict(found).get("limits", "")
    problems += [f"the limits lost this line: {line}" for line in data["limits"] if line not in limits]
    return problems + leaks(side.folder, side.study, side.period, text, side.folder.binding)
