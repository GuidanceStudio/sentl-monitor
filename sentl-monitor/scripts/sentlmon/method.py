"""`method`: write the report's method sections from the study and the period,
in the order the report takes, with an entry per dimension left for the findings."""

from .adopt import missing_answers
from .common import Refused, Study, fmt_date, load_json, load_mcp, public_name, write_text
from .i18n import AUDIENCE, FIRST_ORDER, ORIGINS, SECTIONS, TEXT, join


def report_order(study):
    return FIRST_ORDER


def measured(study):
    """(project, its measured dimensions) pairs."""
    return [(p, [d for d in p["dimensions"] if not d.get("archived")]) for p in study["projects"]]


def _purpose(study, period, names, lang):
    t = TEXT[lang]
    models = sorted({m for b in period["projects"].values() for m in b["by_model"]})
    shown = [public_name(m, names) for m in models]
    questions = sum(len(d["questions"]) for _, dims in measured(study) for d in dims)
    received = sum(b["total"]["received"] for b in period["projects"].values())
    judged = sum(b["total"]["judged"] for b in period["projects"].values())
    asked = t["asked"] if len(shown) != 1 else t["asked_one"]
    lines = [study["narrative"]["purpose"], "",
             asked.format(questions=questions, count=len(shown), names=join(shown, lang))]
    if any(q.get("pair") for _, dims in measured(study) for d in dims for q in d["questions"]):
        lines.append(t["paired"])
    lines.append(t["collected"].format(received=received, judged=judged) + " " + t["sources"])
    return lines


def _themes(study, root, lang):
    by_kind = {}
    for theme in study["themes"]:
        for origin in theme.get("origins") or []:
            by_kind.setdefault(origin["kind"], []).append(f"{theme['label']}: {origin['detail']}")
    lines = []
    for kind, label in ORIGINS[lang].items():
        if kind in by_kind:
            lines += [f"**{label}**", ""] + [f"- {item}" for item in by_kind[kind]] + [""]
    if not root.path("search-demand.json").exists():
        lines.append(TEXT[lang]["no_search"])
    return lines


def _dimensions(study, lang):
    t = TEXT[lang]
    themes = {}
    for theme in study["themes"]:
        themes.setdefault(theme.get("dimension"), []).append(theme)
    lines = []
    for proj, dims in measured(study):
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
    if any(q.get("persona") for _, dims in measured(study) for d in dims for q in d["questions"]):
        lines.append(t["persona_beside"])
    return lines


def _questions(study, lang):
    lines = []
    for _, dims in measured(study):
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


def _scoring(study, lang):
    t = TEXT[lang]
    criteria = study["narrative"]["criteria"]
    subject = study["subject"]["label"]
    lines = [t["judge"].format(by=criteria["by"], date=fmt_date(criteria["date"], lang)), ""]
    for _, dims in measured(study):
        for d in dims:
            lines += [f"**{d['name']}**", ""]
            for q in d["questions"]:
                r = q.get("rubric") or {}
                lines.append(f"- «{q['text']}» " + t["anchors"].format(a5=r.get("5", ""), a3=r.get("3", ""),
                                                                      a1=r.get("1", "")))
            lines.append("")
    axis = study["narrative"].get("score_axis")
    lines += [t["figures"], "", t[f"axis_{axis}" if axis in ("stance", "fidelity") else "axis_none"].format(subject=subject)]
    return lines


def _findings(study, lang):
    t = TEXT[lang]
    projects = measured(study)
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
    builders = {
        "purpose": lambda: _purpose(study, period, names, lang),
        "themes": lambda: _themes(study, folder, lang),
        "dimensions": lambda: _dimensions(study, lang),
        "questions": lambda: _questions(study, lang),
        "scoring": lambda: _scoring(study, lang),
        "findings": lambda: _findings(study, lang),
        "changes": lambda: [TEXT[lang]["first"]],
    }
    out = [f"# {study['narrative']['research_question']}", "", subtitle, ""]
    for n, key in enumerate(report_order(study), 1):
        out += [f"## {n}. {SECTIONS[lang][key]}", ""] + builders[key]() + [""]
    text = "\n".join(out).rstrip() + "\n"
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    write_text(target, text)
    return (f"Wrote the method sections of {target.relative_to(folder.root)}. Write each findings entry, "
            f"replacing the [[...]] markers, then run check.")
