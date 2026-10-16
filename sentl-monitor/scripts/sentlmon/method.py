"""`method`: write the report's method sections from the study and the period,
in the order the report takes, with an entry per dimension left for the findings."""

from .adopt import missing_answers
from .common import Refused, Study, fmt_date, load_json, load_mcp, public_name, write_text
from .i18n import AUDIENCE, FIRST_ORDER, LATER_ORDER, ORIGINS, SECTIONS, TEXT, join


def report_order(folder, date):
    """The later-report order once a final report precedes this one in history/reports.json."""
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
    t = TEXT[lang]
    models = sorted({m for b in period["projects"].values() for m in b["by_model"]})
    shown = [public_name(m, names) for m in models]
    questions = sum(len(d["questions"]) for _, dims in projects for d in dims)
    received = sum(b["total"]["received"] for b in period["projects"].values())
    judged = sum(b["total"]["judged"] for b in period["projects"].values())
    asked = t["asked"] if len(shown) != 1 else t["asked_one"]
    lines = [study["narrative"]["purpose"], "",
             asked.format(questions=questions, count=len(shown), names=join(shown, lang))]
    if any(q.get("pair") for _, dims in projects for d in dims for q in d["questions"]):
        lines.append(t["paired"])
    lines.append(t["collected"].format(received=received, judged=judged) + " " + t["sources"])
    return lines


def _themes(study, projects, root, lang):
    asked = {d["key"] for _, dims in projects for d in dims}
    by_kind = {}
    for theme in (t for t in study["themes"] if t.get("dimension") in asked or not t.get("dimension")):
        for origin in theme.get("origins") or []:
            by_kind.setdefault(origin["kind"], []).append(f"{theme['label']}: {origin['detail']}")
    lines = []
    for kind, label in ORIGINS[lang].items():
        if kind in by_kind:
            lines += [f"**{label}**", ""] + [f"- {item}" for item in by_kind[kind]] + [""]
    if not root.path("search-demand.json").exists():
        lines.append(TEXT[lang]["no_search"])
    return lines


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
            sources = [t["from_theme"].format(theme=th["label"], origins=join(
                dict.fromkeys(ORIGINS[lang][o["kind"]].lower() for o in th["origins"]), lang))
                for th in themes.get(d["key"], [])]
            lines.append(f"- **{d['name']}**" + (", " + "; ".join(sources) if sources else "") + ".")
        lines.append("")
    for item in study["narrative"].get("design_rationale") or []:
        lines.append(f"- {item['choice']}: {item['reason']}")
    audience = study["narrative"]["audience"]
    lines.append(t["who_asks"].format(audience=AUDIENCE[lang][audience["choice"]], reason=audience["reason"]))
    if any(q.get("persona") for _, dims in projects for d in dims for q in d["questions"]):
        lines.append(t["persona_beside"])
    return lines


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
    t = TEXT[lang]
    criteria = study["narrative"]["criteria"]
    subject = study["subject"]["label"]
    lines = [t["judge"].format(by=criteria["by"], date=fmt_date(criteria["date"], lang)), ""]
    for _, dims in projects:
        for d in dims:
            lines += [f"**{d['name']}**", ""]
            for q in d["questions"]:
                r = q.get("rubric") or {}
                lines.append(f"- «{q['text']}»" + (" " + t["anchors"].format(a5=r.get("5", ""), a3=r.get("3", ""),
                                                                            a1=r.get("1", "")) if r else ""))
            lines.append("")
    axis = study["narrative"].get("score_axis")
    lines += [t["figures"], "", t["change_rule"], "",
              t[f"axis_{axis}" if axis in ("stance", "fidelity") else "axis_none"].format(subject=subject)]
    return lines


def _design_line(change, names, lang):
    t, kind = TEXT[lang], change["change"]
    if kind == "models":
        def shown(models):
            return join([names.get(m) or public_name(m, {}) for m in models], lang)
        out = [t[k][len(change[field]) > 1].format(names=shown(change[field]))
               for k, field in (("models_added", "added"), ("models_removed", "removed")) if change[field]]
        basis = change["basis"]
        return " ".join(out + [t["models_basis"][len(basis) > 1].format(names=shown(basis)) if basis
                               else t["models_none"]])
    if kind.startswith("dimension_"):
        return t[kind].format(name=change["name"])
    return t[kind].format(since=fmt_date(change["since"], lang) if change.get("since") else "",
                          text=change.get("text"), previous=change.get("previous_text"))


def _changes(period, lang):
    """The comparison line, the entry the agent writes on the answers, then the design changes."""
    t, c = TEXT[lang], period["comparison"]
    if c["previous"] is None:
        return [t["first"]]
    before = c["previous_period"]
    start, end = fmt_date(before["from"], lang), fmt_date(before["to"], lang)
    intro = (t["compared_day"] if start == end else t["compared_period"]).format(start=start, end=end)
    lines = [intro + (" " + t["rebuilt_previous"] if before["rebuilt"] else ""), "", t["changes_marker"], ""]
    for change in c["design_changes"]:
        lines += [_design_line(change, period.get("names", {}), lang), ""]
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
    names = load_mcp(models_file, "researcher_models") if models_file else {}
    lang = study["report_language"]

    start, end = (fmt_date(period[k], lang) for k in ("from", "to"))
    when = fmt_date(date, lang)
    subtitle = TEXT[lang]["title_day" if start == end else "title_period"].format(
        subject=study["subject"]["label"], start=start, end=end, date=when)
    projects = measured(study, period)
    builders = {
        "purpose": lambda: _purpose(study, projects, period, names, lang),
        "themes": lambda: _themes(study, projects, folder, lang),
        "dimensions": lambda: _dimensions(study, projects, lang),
        "questions": lambda: _questions(projects, lang),
        "scoring": lambda: _scoring(study, projects, lang),
        "findings": lambda: _findings(projects, lang),
        "changes": lambda: _changes(period, lang),
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
