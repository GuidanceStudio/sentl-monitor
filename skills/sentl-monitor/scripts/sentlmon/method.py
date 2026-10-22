"""`method`: write the report's method sections from the study and the period,
in the order the report takes, with an entry per dimension left for the findings."""

from .adopt import missing_answers
from . import demand, schema
from .common import Refused, Study, fmt_date, load_json, match_key, norm, public_name, require_language, write_text
from .i18n import (AUDIENCE, FIRST_ORDER, LATER_ORDER, ORIGINS, ORIGINS_INLINE, SECTIONS, SNAPSHOT_ORDER, TEXT, join,
                   phrase)


def report_order(folder, date):
    """A snapshot's order; otherwise the later-report order once a final report precedes this one in
    history/reports.json."""
    if folder.study.get("kind") == "snapshot":
        return SNAPSHOT_ORDER
    later = any(e["status"] == "final" and e["date"] < date for e in folder.reports())
    return LATER_ORDER if later else FIRST_ORDER


def measured(study, period):
    """(project, dimensions) pairs of what the period asked: each dimension and question named
    and worded as the period's runs had them, with the study's other fields for it."""
    out = []
    for proj in study["projects"]:
        asked = period.get("asked", {}).get(proj["key"])
        if not asked:
            continue
        dims = {d["key"]: d for d in proj["dimensions"]}
        questions = {q["key"]: q for d in proj["dimensions"] for q in d["questions"]}
        out.append((proj, [{**dims.get(d["key"], {}), "key": d["key"], "name": d["name"],
                            "questions": [{**questions.get(q["key"], {}), **q} for q in d["questions"]]}
                           for d in asked]))
    return out


def _purpose(study, projects, period, names, lang):
    """The purpose, then what was asked: one sentence, or one line per project when the
    projects differ in how many questions, which assistants, rounds or schedule."""
    t = TEXT[lang]
    models = sorted({m for b in period["projects"].values() for m in b["by_model"]})
    shown = [public_name(m, names) for m in models]
    questions = sum(len(d["questions"]) for _, dims in projects for d in dims)
    received = sum(b["total"]["received"] for b in period["projects"].values())
    judged = sum(b["total"]["judged"] for b in period["projects"].values())
    lines = [study["narrative"]["purpose"], ""]
    rows = [(proj["name"], sum(len(d["questions"]) for d in dims), *_settings(period, proj["key"]))
            for proj, dims in projects]
    if len({row[1:] for row in rows}) > 1:
        lines.append(t["asked_projects"].format(count=len(rows)))
        for name, count, models_of, rounds, schedule in rows:
            assistants = [public_name(m, names) for m in models_of]
            parts = [t["project_questions"][count != 1].format(n=count),
                     t["project_assistants"][len(assistants) != 1].format(count=len(assistants),
                                                                          names=join(assistants, lang))]
            line = " ".join(parts) + ", " + t["project_rounds"][rounds != 1].format(rounds=rounds)
            lines.append(f"- **{name}**: {line}" + (f", {t['schedule'][schedule]}" if schedule in t["schedule"] else "")
                         + ".")
        lines.append("")
    else:
        asked = t["asked"] if len(shown) != 1 else t["asked_one"]
        lines.append(asked.format(questions=questions, count=len(shown), names=join(shown, lang)))
    if any(q.get("pair") for _, dims in projects for d in dims for q in d["questions"]):
        lines.append(t["paired"])
    lines.append(t["collected"].format(received=received, judged=judged) + " " + t["sources"])
    return lines


def _settings(period, key):
    s = (period.get("settings") or {}).get(key) or {}
    return tuple(s.get("models") or ()), s.get("rounds"), s.get("schedule")


def _themes(study, projects, root, lang):
    """Themes by origin; the themes that share an identical origin (kind and detail) are
    listed together."""
    asked = {d["key"] for _, dims in projects for d in dims}
    by_kind = {}
    for theme in (t for t in study["themes"] if t.get("dimension") in asked or not t.get("dimension")):
        for origin in theme.get("origins") or []:
            labels = by_kind.setdefault(origin["kind"], {}).setdefault(origin["detail"], [])
            if theme["label"] not in labels:
                labels.append(theme["label"])
    lines = []
    for kind, label in ORIGINS[lang].items():
        if kind in by_kind:
            lines += [f"**{label}**", ""] + [f"- {join(labels, lang)}: {detail}"
                                             for detail, labels in by_kind[kind].items()] + [""]
    path = root.path("search-demand.json")
    shown = [(t["id"], t["label"]) for t in study["themes"] if t.get("dimension") in asked or not t.get("dimension")]
    found = demand.report_lines(load_json(path), shown, lang) if path.exists() else []
    return lines + found if found else lines + [TEXT[lang]["no_search"]]


def _dimensions(study, projects, lang):
    t = TEXT[lang]
    themes = {}
    for theme in study["themes"]:
        themes.setdefault(theme.get("dimension"), []).append(theme)
    lines = []
    for proj, dims in projects:
        lines += [f"**{proj['name']}**", ""]
        if proj.get("question"):
            lines.append(t["project_question"].format(question=proj["question"]))
        if proj.get("decision"):
            lines.append(t["project_decision"].format(decision=proj["decision"]))
        if proj.get("question") or proj.get("decision"):
            lines.append("")
        for d in dims:
            sources = []
            for th in themes.get(d["key"], []):
                origins = join(dict.fromkeys(ORIGINS_INLINE[lang][o["kind"]] for o in th["origins"]), lang)
                # An adopted study's theme carries its dimension's name: the origins alone, then.
                same = (th["label"] or "").strip().casefold() == d["name"].strip().casefold()
                sources.append(t["from_origins"].format(origins=origins) if same
                               else t["from_theme"].format(theme=th["label"], origins=origins))
            lines.append(f"- **{d['name']}**" + (", " + "; ".join(sources) if sources else "") + ".")
        lines.append("")
    for item in study["narrative"].get("design_rationale") or []:
        lines.append(f"- {item['choice']}: {item['reason']}")
    audience = study["narrative"]["audience"]
    lines.append(t["who_asks"].format(audience=AUDIENCE[lang][audience["choice"]], reason=audience["reason"]))
    if any(q.get("persona") for _, dims in projects for d in dims for q in d["questions"]):
        lines.append(t["persona_beside"])
    return lines


def _snapshot_dimensions(study, projects, lang):
    """Each dimension, what it measures and why it was chosen for the subject."""
    t = TEXT[lang]
    reasons = {match_key(c["choice"]): c["reason"] for c in study["narrative"].get("design_rationale") or []}
    lines = []
    for proj, dims in projects:
        if proj.get("question"):
            lines.append(t["project_question"].format(question=proj["question"]))
        if proj.get("decision"):
            lines.append(t["project_decision"].format(decision=proj["decision"]))
        lines.append("")
        for d in dims:
            line = f"- **{d['name']}**: {d['measures'].rstrip('.')}."
            reason = reasons.get(match_key(d["name"]))
            lines.append(line + (f" {t['snapshot_why']}: {reason.rstrip('.')}." if reason else ""))
    return lines


def _limits(period, lang):
    first, second = TEXT[lang]["limits_body"]
    return [first.format(date=fmt_date(period["from"], lang)), "", second]


def _questions(projects, lang):
    lines = []
    for _, dims in projects:
        for d in dims:
            lines += [f"**{d['name']}**", ""]
            shown = set()
            for q in d["questions"]:
                if q["key"] in shown:
                    continue
                partner = next((o for o in d["questions"] if q.get("pair") and o is not q
                                and o.get("pair") == q.get("pair")), None)
                text = q["text"] if partner is None else f"{q['text']} / {partner['text']}"
                shown.update({q["key"]} | ({partner["key"]} if partner else set()))
                persona = f" ({TEXT[lang]['asked_by'].format(persona=q['persona'])})" if q.get("persona") else ""
                lines.append(f"- {text}{persona}")
            lines.append("")
    return lines


def _scoring(study, projects, lang):
    """Who wrote the criteria and how they read. A rubric that several questions share is
    stated once for them with all five anchors; a question's own rubric with 5, 3 and 1."""
    t = TEXT[lang]
    criteria = study["narrative"]["criteria"]
    subject = study["subject"]["label"]
    lines = [phrase(lang, "judge", by=criteria["by"], date=fmt_date(criteria["date"], lang)), ""]

    def anchors(q):
        r = q.get("rubric") or {}
        return tuple(norm(r.get(k)) for k in "12345") if r else None
    # A rubric is shared when at least two distinct question texts use it; the same question
    # asked in two projects is one text.
    groups = {}
    for _, dims in projects:
        for q in (q for d in dims for q in d["questions"]):
            if anchors(q):
                groups.setdefault(anchors(q), {}).setdefault(match_key(q["text"]), q)
    shared = {key: list(texts.values()) for key, texts in groups.items() if len(texts) > 1}
    if shared:
        lines[0] += " " + t["shared_note"]
        lines += [f"**{t['shared_rubric']}**", ""]
        for qs in shared.values():
            r = qs[0]["rubric"]
            quoted = ["«" + q["text"] + "»" for q in qs]
            lines.append(f"- {join(quoted, lang)}: "
                         + t["anchors_all"].format(**{f"a{k}": r.get(k) or "" for k in "12345"}))
        lines.append("")
    for _, dims in projects:
        for d in dims:
            own = [q for q in d["questions"] if anchors(q) not in shared]
            if not own:
                continue
            lines += [f"**{d['name']}**", ""]
            for q in own:
                r = q.get("rubric") or {}
                lines.append(f"- «{q['text']}»" + (" " + t["anchors"].format(a5=r.get("5") or "", a3=r.get("3") or "",
                                                                            a1=r.get("1") or "") if r else ""))
            lines.append("")
    if study.get("kind") == "snapshot":
        axes = dict.fromkeys(d.get("axis", "stance") for _, dims in projects for d in dims)
        lines += [t["figures_snapshot"], "", t["snapshot_reading"].format(subject=subject)]
        return lines + [line for axis in axes for line in ("", t[f"axis_{axis}"].format(subject=subject))]
    axis = study["narrative"].get("score_axis")
    lines += [t["figures"], "", t["change_rule"], "",
              t[f"axis_{axis}" if axis in ("stance", "fidelity") else "axis_none"].format(subject=subject)]
    return lines


def _design_line(change, names, lang, halves=False):
    t, kind = TEXT[lang], change["change"]
    if kind == "models":
        def shown(models):
            return join([names.get(m) or public_name(m, {}) for m in models], lang)
        out = [t[k][len(change[field]) > 1].format(names=shown(change[field]))
               for k, field in (("models_added", "added"), ("models_removed", "removed")) if change[field]]
        basis, both = change["basis"], "_halves" if halves else ""
        return " ".join(out + [t["models_basis" + both][len(basis) > 1].format(names=shown(basis)) if basis
                               else t["models_none" + both]])
    if kind.startswith("dimension_"):
        return t[kind].format(name=change["name"])
    return phrase(lang, kind, since=fmt_date(change["since"], lang) if change.get("since") else "",
                  text=change.get("text"), previous=change.get("previous_text"))


def halves_line(halves, lang, projects):
    """The line naming the two halves of a first period, their dates, and each project's runs
    and answers in each, which `check` requires. `projects`: the study's projects, in order."""
    t = TEXT[lang]

    def span(half):
        start, end = fmt_date(half["from"], lang), fmt_date(half["to"], lang)
        return phrase(lang, "span_day" if start == end else "span", start=start, end=end)

    def counts(half, key):
        c = halves[half]["projects"].get(key, {})
        return c.get("runs", 0), c.get("answers", 0)
    line = [t["halves"].format(first=span(halves["first"]), second=span(halves["second"]))]
    for p in projects:
        (r1, a1), (r2, a2) = counts("first", p["key"]), counts("second", p["key"])
        if r1 and r2:
            line.append(t["half_counts"].format(project=p["name"], runs1=t["runs_n"][r1 != 1].format(n=r1),
                                                answers1=t["answers_n"][a1 != 1].format(n=a1),
                                                runs2=t["runs_n"][r2 != 1].format(n=r2), answers2=a2))
        elif r1 or r2:
            half, (runs, answers) = ("first", (r1, a1)) if r1 else ("second", (r2, a2))
            line.append(t["half_counts_one"].format(project=p["name"], runs=t["runs_n"][runs != 1].format(n=runs),
                                                    answers=t["answers_n"][answers != 1].format(n=answers),
                                                    half=t["half_names"][half]))
    return " ".join(line)


def _changes(period, lang, projects):
    """The comparison line, the entry the agent writes on the answers, then the design changes."""
    t, c = TEXT[lang], period["comparison"]
    marker = t["changes_marker"]
    if c.get("halves"):
        intro, marker = halves_line(c["halves"], lang, projects), t["changes_marker_halves"]
    elif c["previous"] is None:
        return [t["first"]]
    else:
        before = c["previous_period"]
        start, end = fmt_date(before["from"], lang), fmt_date(before["to"], lang)
        intro = phrase(lang, "compared_day" if start == end else "compared_period", start=start, end=end)
        intro += (" " + t["rebuilt_previous"]) if before["rebuilt"] else ""
    lines = [intro, "", marker, ""]
    for change in c["design_changes"]:
        lines += [_design_line(change, period.get("names", {}), lang, bool(c.get("halves"))), ""]
    return lines


def _findings(projects, lang):
    t = TEXT[lang]
    level = "###" if len(projects) == 1 else "####"
    lines = []
    for proj, dims in projects:
        if len(projects) > 1:
            lines += [f"### {proj['name']}", ""]
        for d in dims:
            lines += [f"{level} {d['name']}: {t['finding_title']}", "",
                      t["finding_body"].format(dimension=d["name"]), ""]
    return lines


def write(root, date, models_file, force=False):
    folder = Study(root)
    study = folder.study
    require_language(study)
    missing = missing_answers(study)
    if missing:
        raise Refused("the report needs the operator's answers to:\n  " + "\n  ".join(missing))
    period_path = folder.path("history", "periods", f"{date}.json")
    if not period_path.exists():
        raise Refused(f"no period for {date}: run period --date {date} first")
    target = folder.path("reports", f"{date}.md")
    if target.exists() and not force:
        raise Refused(f"{target} exists; pass --force to write the method sections again over it")
    period = load_json(period_path)
    names = schema.models(models_file) if models_file else {}
    lang = study["report_language"]

    start, end = (fmt_date(period[k], lang) for k in ("from", "to"))
    when = fmt_date(date, lang)
    subtitle = phrase(lang, "title_day" if start == end else "title_period",
                      subject=study["subject"]["label"], start=start, end=end, date=when)
    projects = measured(study, period)
    builders = {
        "purpose": lambda: _purpose(study, projects, period, names, lang),
        "themes": lambda: _themes(study, projects, folder, lang),
        "dimensions": lambda: (_snapshot_dimensions if study.get("kind") == "snapshot" else _dimensions)(
            study, projects, lang),
        "questions": lambda: _questions(projects, lang),
        "scoring": lambda: _scoring(study, projects, lang),
        "findings": lambda: _findings(projects, lang),
        "changes": lambda: _changes(period, lang, study["projects"]),
        "summary": lambda: ["[[summary]]"],
        "limits": lambda: _limits(period, lang),
    }
    out = [f"# {study['narrative']['research_question']}", "", subtitle, ""]
    for n, key in enumerate(report_order(folder, date), 1):
        out += [f"## {n}. {SECTIONS[lang][key]}", ""] + builders[key]() + [""]
    text = "\n".join(out).rstrip() + "\n"
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    write_text(target, text)
    return (f"Wrote the method sections of {target.relative_to(folder.root)}. Write each findings entry, "
            f"replacing the [[...]] markers, then run check.")
