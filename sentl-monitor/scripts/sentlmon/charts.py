"""`charts`: a report's figures as md2 `:::chart` tables for the operator's deck
(ARCHITECTURE.md §Charts for a deck). The report does not include them."""

import datetime as dt
from collections import Counter

from .common import MONTHS, Refused, Study, fmt_date, load_json, parse_time, round_half_up, write_text
from .i18n import CHARTS, join, phrase

RADAR_AXES = range(3, 13)
SOURCE_PAIRS = (("outdated", "current", "sources_fact"), ("low", "high", "sources_score"))
NOT_COMPARED = {"new": "new in this period", "new_baseline": "a new baseline, not compared",
                "no_figure": "without a figure on one side"}


def _mean(value):
    """A mean as `check` rounds it, with a point whatever the report's language: md2 reads the
    value as a number."""
    return f"{round_half_up(value, 1):.1f}"


def _pct(ratio):
    return str(int(round_half_up(ratio * 100, 0)))


def _day(day, lang):
    return "1°" if lang == "it" and day.day == 1 else str(day.day)


def span(start, end, lang):
    """The days from `start` to `end`, written short: 8–19 ottobre 2026."""
    a, b = parse_time(start).date(), parse_time(end).date()
    month = MONTHS[lang]
    if a == b:
        return fmt_date(a, lang)
    if (a.year, a.month) == (b.year, b.month):
        return f"{_day(a, lang)}–{_day(b, lang)} {month[b.month - 1]} {b.year}"
    if a.year == b.year:
        return f"{_day(a, lang)} {month[a.month - 1]} – {_day(b, lang)} {month[b.month - 1]} {b.year}"
    return f"{fmt_date(a, lang)} – {fmt_date(b, lang)}"


def _project(t, lang, name, period, key):
    """The project's name, with the days of its own runs when they are not the period's: the
    series carry the period's bounds as the report prints them."""
    starts = sorted(period.get("starts", {}).get(key) or (), key=parse_time)
    if not starts or [parse_time(x).date() for x in (starts[0], starts[-1])] == \
            [parse_time(period[x]).date() for x in ("from", "to")]:
        return name
    first, last = (fmt_date(x, lang) for x in (starts[0], starts[-1]))
    days = phrase(lang, "span_day", start=first) if first == last else phrase(lang, "span", start=first, end=last)
    return f"{name} ({t['own_runs']} {days})"


def _labels(entries, starts, lang):
    """Each run's start day (8 ott, 8 Oct), and its start time where two runs started on the same
    day, both in UTC whatever offset a start carries. `entries` carry `run_id` and `date`; `starts`
    maps a run id to its start time."""
    times = [parse_time(starts[e["run_id"]]).astimezone(dt.timezone.utc) if e["run_id"] in starts else None
             for e in entries]
    days = [at.date() if at else dt.date.fromisoformat(e["date"][:10]) for at, e in zip(times, entries)]
    repeated = Counter(days)
    out = []
    for at, day in zip(times, days):
        label = f"{_day(day, lang)} {MONTHS[lang][day.month - 1][:3]}"
        out.append(label + (f" {at:%H:%M} UTC" if at and repeated[day] > 1 else ""))
    return out


def _cell(value):
    """md2 splits a table row on every |."""
    return " ".join(str(value).replace("|", "/").split())


class Charts:
    """The charts of one period, in the order they are written, and what was left out."""

    def __init__(self):
        self.written, self.left = [], []

    def add(self, heading, kind, title, header, rows, why="no data", dropped=0, by_run=None):
        """`dropped`: the runs left out of a chart by run, for the reason `why`. `by_run` says what
        a run of a chart by run shows (the fact is stated); md2 draws a line between runs, so such
        a chart needs two."""
        # md2 ends a title at the first double quote.
        heading, title = " ".join(heading.split()), " ".join(title.replace('"', "'").split())
        if not rows:
            self.left.append(f"{heading}: left out, {why}")
        elif by_run and len(rows) < 2:
            self.left.append(f"{heading}: left out, {by_run} in {len(rows)} run(s), and a chart by run needs two")
        else:
            self.written.append((heading, kind, title, header, rows))
            if dropped:
                self.left.append(f"{heading}: {dropped} run(s) left out, {why}")

    def lines(self):
        out = []
        for heading, kind, title, header, rows in self.written:
            out += [f"## {heading}", "", f':::chart {kind} --title "{title}"',
                    "| " + " | ".join(_cell(h) for h in header) + " |", "|" + "---|" * len(header)]
            out += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows] + [":::", ""]
        return out


def _basis(t, lang, key, dims, entries, sides, names, halves):
    """What the profile's two series rest on when it differs from either side's own figures: the
    assistants of both sides, and the questions of the dimensions shown that are not compared."""
    shown = [(d, entries[d["key"]]) for d in dims if (entries.get(d["key"]) or {}).get("mean")]
    basis = shown[0][1]["models"]
    notes = []
    if any({m for m, c in s["projects"][key]["by_model"].items() if c["expected"]} != set(basis)
           for s in sides if s and key in s.get("projects", {})):
        notes.append(t["basis_models"][halves][len(basis) > 1].format(names=join([names.get(m, m) for m in basis],
                                                                                   lang)))
    left = []
    for d, entry in shown:
        asked = {}
        # The questions asked now, then those asked only on the earlier side.
        for s in reversed([s for s in sides if s]):
            for ad in (a for a in s.get("asked", {}).get(key, []) if a["key"] == d["key"]):
                for q in ad["questions"]:
                    asked.setdefault(q["key"], q["text"])
        left += [f"«{text}»" for q, text in asked.items() if q not in entry["compared_questions"]]
    if left:
        notes.append(t["basis_questions"][halves][len(left) > 1].format(questions=join(left, lang)))
    return notes


def _profile(charts, t, lang, name, label, key, dims, block, period, sides, whole):
    """The dimension means as a radar and a bar: the previous period and this one, or the two
    halves, on the questions and assistants the comparison rests on; this period alone when no
    dimension of the project is compared."""
    c = period.get("comparison") or {}
    entries = {d: e for d, e in c.get("dimensions", {}).items() if e["project"] == key}
    rows, notes = [], []
    if any(e.get("mean") for e in entries.values()):
        halves = c.get("halves")
        if halves:
            parts = [(t["half"][h], span(halves[h]["from"], halves[h]["to"], lang)) for h in ("first", "second")]
            series = [f"{half[0].upper()}{half[1:]} ({days})" for half, days in parts]
            covers = join([f"{half} ({days})" for half, days in parts], lang)
        else:
            before = c["previous_period"]
            series = [span(before["from"], before["to"], lang), whole]
            covers = join(series, lang)
        for d in dims:
            entry = entries.get(d["key"]) or {}
            if entry.get("mean"):
                rows.append([d["name"], _mean(entry["mean"]["previous"]), _mean(entry["mean"]["now"])])
            else:
                charts.left.append(f"{d['name']} ({name}) is left out of the profile: "
                                   + NOT_COMPARED.get(entry.get("status"), "not compared"))
        notes = _basis(t, lang, key, dims, entries, sides, period.get("names") or {}, bool(halves))
    else:
        series, covers = [whole], whole
        for d in dims:
            cell = block["dimensions"][d["key"]]["total"]
            if cell["figure"]:
                rows.append([d["name"], _mean(cell["mean"])])
            else:
                charts.left.append(f"{d['name']} ({name}) is left out of the profile: no figure, under 80% of its "
                                   "answers judged")
    heading = "; ".join([t["profile"].format(project=label, covers=covers), *notes])
    header = [t["dimension"], *series]
    if len(rows) in RADAR_AXES:
        charts.add(heading, "radar", t["profile_title"], header, rows)
    elif rows:
        charts.left.append(f"{heading}: the radar is left out, md2 draws one on 3 to 12 dimensions and {len(rows)} "
                           "have a value; the bar holds them")
    charts.add(heading, "bar", t["profile_title"], header, rows)


def _by_model(charts, t, name, label, dims, block, names, whole):
    models = list(block["by_model"])
    if len(models) < 2:
        return
    rows = []
    for d in dims:
        cells = block["dimensions"][d["key"]]["by_model"]
        missing = [names.get(m, m) for m in models if not cells[m]["figure"]]
        if missing:
            charts.left.append(f"{d['name']} ({name}) is left out of the chart by assistant: no figure for "
                               + ", ".join(missing))
        else:
            rows.append([d["name"], *(_mean(cells[m]["mean"]) for m in models)])
    charts.add(t["by_model"].format(project=label, covers=whole), "bar", t["by_model_title"],
               [t["dimension"], *(names.get(m, m) for m in models)], rows)


def _question(charts, t, lang, where, scope, starts):
    """A question's insights by run, and the sources behind its fact or its score."""
    facts = scope.get("facts")
    if facts and facts["terms"]["current"]:
        kept = [r for r in facts["runs"] if r["total"]["current_share"] is not None]
        rows = [[label, _pct(r["total"]["current_share"])] for label, r in zip(_labels(kept, starts, lang), kept)]
        charts.add(t["currency"].format(**where), "line", t["currency_title"], [t["run"], where["covers"]], rows,
                   "no answer states the fact, current or outdated", len(facts["runs"]) - len(rows),
                   by_run="the fact is stated")
    if "presence_runs" in scope:
        runs = scope["presence_runs"]
        kept = [r for r in runs if r["rate"] is not None]
        rows = [[label, _pct(r["rate"])] for label, r in zip(_labels(kept, starts, lang), kept)]
        charts.add(t["presence"].format(**where), "column", t["presence_title"].format(subject=where["subject"]),
                   [t["run"], where["covers"]], rows, "no answer given", len(runs) - len(rows),
                   by_run="answers are given")
    listed = scope.get("group_sources") or {}
    for one, other, kind in SOURCE_PAIRS:
        if one in listed and other in listed:
            shares = {e["domain"]: [_pct(e["share"]), _pct(e["other"]["share"])] for e in listed[one]}
            for e in listed[other]:
                shares.setdefault(e["domain"], [_pct(e["other"]["share"]), _pct(e["share"])])
            charts.add(t[kind].format(**where), "bar", t["sources_title"],
                       [t["domain"], t["groups"][one], t["groups"][other]], [[d, *v] for d, v in shares.items()])


def write(root, date):
    folder = Study(root)
    study = folder.study
    periods = folder.path("history", "periods")
    if not (periods / f"{date}.json").exists():
        raise Refused(f"no period for {date}: run period --date {date} first")
    period = load_json(periods / f"{date}.json")

    def side(name):
        path = periods / f"{name}.json"
        return load_json(path) if path.exists() else None
    # The two sides of the comparison, for what each side measured.
    c = period.get("comparison") or {}
    if c.get("halves"):
        sides = (side(f"{date}.first"), side(f"{date}.second"))
    else:
        sides = (side(c["previous"]) if c.get("previous") else None, period)
    lang = study.get("report_language") or "en"
    t, subject = CHARTS[lang], study["subject"]["label"]
    charts = Charts()
    for proj in study["projects"]:
        key, name = proj["key"], proj["name"]
        block = period["projects"].get(key)
        if not block:
            continue
        dims = period["asked"][key]
        whole, label = span(period["from"], period["to"], lang), _project(t, lang, name, period, key)
        starts = dict(zip(period["runs"].get(key, []), period["starts"].get(key, [])))
        _profile(charts, t, lang, name, label, key, dims, block, period, sides, whole)
        _by_model(charts, t, name, label, dims, block, period.get("names") or {}, whole)
        for d in dims:
            for q in d["questions"]:
                where = {"project": label, "dimension": d["name"], "question": q["text"], "covers": whole,
                         "subject": subject}
                _question(charts, t, lang, where, block["dimensions"][d["key"]]["questions"][q["key"]], starts)
    target = folder.path("reports", f"{date}.charts.md")
    write_text(target, "\n".join([f"# {t['file_title'].format(subject=subject, date=fmt_date(date, lang))}", "",
                                  *charts.lines()]).rstrip() + "\n")
    out = [f"Wrote reports/{date}.charts.md: {len(charts.written)} chart(s) for the operator's deck; the report "
           "does not include them."]
    out += [f"  {kind} {len(rows)}×{len(header) - 1}: {heading}" for heading, kind, _, header, rows in charts.written]
    if charts.left:
        out += ["Left out (tell the operator):"] + [f"  - {line}" for line in charts.left]
    return "\n".join(out)
