"""The comparison of a period with the periods before it (ARCHITECTURE.md §Comparability,
§What counts as a change). Everything is computed from the period files' question–model
cells, so a figure restricted to the questions and models two periods share is exact."""

from collections import Counter

from .common import is_owned, mean
from .insights import TOP_SOURCES

K = 4
# A fact's current share is a rate, so it takes presence's steps.
STEPS = {"mean": (0.3, 0.5), "presence": (0.10, 0.20), "current_share": (0.10, 0.20)}
EPS = 1e-9
NEW_QUESTION = ("new_intent", "created")


def band(mean):
    if mean is None:
        return None
    m = round(mean, 9)
    return "unfavourable" if m < 2.5 else "mixed" if m < 3.5 else "favourable"


def called(now, values, kind):
    """A change: `now` outside the range of the K latest previous values (latest first) and
    at least a step from the latest; the step is larger with a single previous period."""
    values = values[:K]
    if now is None or not values:
        return False
    step = STEPS[kind][1 if len(values) == 1 else 0]
    return (now < min(values) - EPS or now > max(values) + EPS) and abs(now - values[0]) >= step - EPS


def _models(block):
    return {m for m, c in block["by_model"].items() if c["expected"]}


def _asked(dim):
    return [q for q, c in dim["questions"].items() if c["total"]["expected"]]


def _pool(dim, questions, models):
    judged, total, named, given, domains, stating, current = 0, 0.0, 0, 0, Counter(), 0, 0
    for q in questions:
        scope = dim["questions"].get(q, {})
        cells, facts = scope.get("by_model", {}), (scope.get("facts") or {}).get("by_model", {})
        for m in models:
            c = cells.get(m)
            if not c:
                continue
            if c["mean"] is not None:
                judged += c["judged"]
                total += c["mean"] * c["judged"]
            named, given = named + c["presence"]["named"], given + c["presence"]["given"]
            domains.update(c["domains"])
            f = facts.get(m)
            if f:
                stating, current = stating + f["stating"], current + f["current_only"] + f["both"]
    return {"mean": round(total / judged, 10) if judged else None,
            "presence": round(named / given, 10) if given else None, "domains": domains,
            "current_share": round(current / stating, 10) if stating else None}


def _metric(kind, now, values):
    if now is None or not values:
        return None
    return {"now": now, "previous": values[0], "delta": round(now - values[0], 10),
            "range": [min(values), max(values)], "periods": len(values), "changed": called(now, values, kind)}


def _version_max(period, key):
    return max((v for v in period["versions"].get(key, []) if v is not None), default=0)


def _version_min(period, key):
    """The version of a period's first run; 0 for a run older than every version."""
    return min((v or 0 for v in period["versions"].get(key, [])), default=0)


class _History:
    """The recorded versions of one project, read for what changed between two periods."""

    def __init__(self, versions):
        self.by_number = {v["version"]: v for v in versions}

    def changes(self, after, upto):
        return [(n, c) for n in sorted(self.by_number) if after < n <= upto for c in self.by_number[n]["changes"]]

    def blocked(self, after, upto):
        """Questions that start a new baseline between two versions, with the change that does it."""
        return {c["question"]: c["change"] for _, c in self.changes(after, upto)
                if c["change"] in ("criteria",) + NEW_QUESTION}

    def _question(self, number, key):
        v = self.by_number.get(number) or {}
        return next(((d["key"], q) for d in v.get("dimensions", []) for q in d["questions"] if q["key"] == key),
                    (None, {}))

    def measured(self, number):
        """The dimensions measured under a version; the first version for runs older than every one."""
        layout = self.by_number.get(number) or self.by_number.get(min(self.by_number, default=0), {})
        return {d["key"] for d in layout.get("dimensions", []) if not d["archived"]}

    def text(self, number, key):
        return self._question(number, key)[1].get("text")

    def dimension(self, number, key):
        return self._question(number, key)[0]


def _series(kind, key, dkey, questions, models, prevs, history, upto, figure_of):
    """The values of the earlier periods, latest first, back to the last new baseline or to
    the first period missing one of the questions or the models compared."""
    values = []
    for p in prevs:
        dim = p["projects"].get(key, {}).get("dimensions", {}).get(dkey)
        if dim is None or set(history.blocked(_version_max(p, key), upto)) & set(questions) \
                or not set(questions) <= set(_asked(dim)) or not models <= _models(p["projects"][key]):
            break
        if figure_of(dim):
            value = _pool(dim, questions, models)[kind]
            if value is not None:
                values.append(value)
    return values


def compare(study, current, prevs, versions, answers, owned, within=None):
    """`prevs`: the earlier periods, latest first. `answers(period, key, q, m)` lists the
    judged responses of a pair in a period, each with its run's start. `within`, when the two
    halves of one period are compared: that whole `period`, whose design changes are those made
    inside it rather than between the two halves."""
    out = {"previous": None, "previous_period": None, "range_of": [], "dimensions": {}, "projects": {},
           "verdict_changes": [], "domains": {"new": [], "lost": []}, "design_changes": []}
    if not prevs:
        return out
    prev = prevs[0]
    out.update(previous=prev["date"], range_of=sorted(p["date"] for p in prevs),
               previous_period={"from": prev["from"], "to": prev["to"], "rebuilt": bool(prev.get("rebuilt"))})
    names = {d["key"]: d["name"] for vs in versions.values() for v in vs for d in v["dimensions"]}
    names.update({d["key"]: d["name"] for p in study["projects"] for d in p["dimensions"]})
    for proj in study["projects"]:
        key = proj["key"]
        block, pblock = current["projects"].get(key), prev["projects"].get(key)
        if block is None:
            continue
        history = _History(versions.get(key, []))
        upto = _version_max(current, key)
        since = _since(within["period"] if within else current, key, history)
        if pblock is None:
            for dkey in block["dimensions"]:
                out["dimensions"][dkey] = {"project": key, "status": "new"}
            continue
        now_models, prev_models = _models(block), _models(pblock)
        basis = now_models & prev_models
        blocked = history.blocked(_version_max(prev, key), upto)
        design, dims_design, entries = [], [], {}
        gone = {q for qs in prev.get("dropped", {}).get(key, {}).values() for q in qs}
        for dkey, dim in block["dimensions"].items():
            pdim = pblock["dimensions"].get(dkey)
            if (pdim is None or not _asked(pdim)) and gone & set(dim["questions"]):
                # Asked then, with its questions dropped from those runs (criteria changed): nothing to
                # compare, and nothing new.
                out["dimensions"][dkey] = {"project": key, "status": "new_baseline"}
                continue
            if pdim is None or not _asked(pdim):
                out["dimensions"][dkey] = {"project": key, "status": "new"}
                dims_design.append({"project": key, "change": "dimension_added", "dimension": dkey,
                                    "name": names.get(dkey, dkey)})
                continue
            entry, verdicts, domains = _dimension(key, dkey, dim, pdim, prevs, basis, blocked, history, upto,
                                                  answers, owned, current, prev)
            out["dimensions"][dkey] = entries[dkey] = entry
            out["verdict_changes"] += verdicts
            out["domains"]["new"] += domains["new"]
            out["domains"]["lost"] += domains["lost"]
        project = _project(key, block, entries, prevs, basis, history, upto)
        if project:
            out["projects"][key] = project
        measured = history.measured(upto)
        archived = {dkey for dkey, pdim in pblock["dimensions"].items()
                    if dkey not in block["dimensions"] and dkey not in measured and _asked(pdim)}
        if within:
            # Archived inside the period, before either half's latest version.
            archived |= history.measured(_version_min(within["period"], key)) - measured - set(block["dimensions"])
        dims_design += [{"project": key, "change": "dimension_archived", "dimension": dkey,
                         "name": names.get(dkey, dkey)} for dkey in sorted(archived)]
        new_dims = {d["dimension"] for d in dims_design if d["change"] == "dimension_added"}
        changes = history.changes(_version_min(within["period"], key) if within else _version_max(prev, key), upto)
        replaced = {c.get("replaces") for _, c in changes}
        for number, c in changes:
            kind, q = c["change"], c.get("question")
            if kind not in ("reworded", "new_intent", "criteria", "created", "retired"):
                continue
            dkey = history.dimension(number - 1 if kind == "retired" else number, q)
            if (kind == "created" and dkey in new_dims) or \
                    (kind == "retired" and (q in replaced or dkey not in block["dimensions"])):
                continue
            item = {"project": key, "change": kind, "question": q}
            if kind == "new_intent":
                item["replaces"] = c["replaces"]
            if kind != "retired":
                item["text"] = history.text(number, q)
            if kind in ("reworded", "new_intent", "retired"):
                item["previous_text"] = history.text(number - 1, c.get("replaces", q))
            if kind != "retired":
                item["since"] = since(number)
            design.append(item)
        if within:
            # Inside one period: the models changes detect recorded, and, for runs older than every
            # version, whose model lists are only who answered, the second half against the first.
            added = {m for _, c in changes if c["change"] == "models" for m in c["added"]}
            removed = {m for _, c in changes if c["change"] == "models" for m in c["removed"]}
            if None in within["period"]["versions"].get(key, []):
                added, removed = added | (now_models - prev_models), removed | (prev_models - now_models)
        else:
            added, removed = now_models - prev_models, prev_models - now_models
        if added or removed:
            design.append({"project": key, "change": "models", "added": sorted(added), "removed": sorted(removed),
                           "basis": sorted(basis)})
        out["design_changes"] += dims_design + design
    for kind in ("new", "lost"):
        out["domains"][kind] = sorted(out["domains"][kind], key=lambda d: (-d["answers"], d["domain"], d["project"],
                                                                           d["dimension"]))[:TOP_SOURCES]
    return out


def _since(period, key, history):
    """The date of the period's first run of version `number` or later."""
    starts = sorted(zip(period.get("starts", {}).get(key, []), period["versions"].get(key, [])))

    def since(number):
        found = next((s for s, v in starts if v is not None and v >= number), None)
        return (found or history.by_number[number]["recorded_at"])[:10]
    return since


def _dimension(key, dkey, dim, pdim, prevs, basis, blocked, history, upto, answers, owned, current, prev):
    asked_now, asked_prev = _asked(dim), set(_asked(pdim))
    shared = [q for q in asked_now if q in asked_prev and blocked.get(q) not in NEW_QUESTION]
    compared = [q for q in shared if q not in blocked]
    entry = {"project": key, "status": "compared" if compared else "new_baseline", "models": sorted(basis),
             "compared_questions": compared, "questions": {}}
    for q in asked_now:
        if q not in asked_prev and blocked.get(q) != "new_intent":
            entry["questions"][q] = {"status": "new"}
        elif q in blocked:
            entry["questions"][q] = {"status": "new_baseline", "reason": blocked[q]}
        elif not (dim["questions"][q]["total"]["figure"] and pdim["questions"][q]["total"]["figure"]):
            entry["questions"][q] = {"status": "no_figure"}
        else:
            entry["questions"][q] = {"status": "compared", **_metrics(
                [q], dkey, key, dim, prevs, basis, history, upto, lambda d, q=q: d["questions"][q]["total"]["figure"])}
            share = _current_share(q, dkey, key, dim, prevs, basis, history, upto)
            if share:
                entry["questions"][q]["current_share"] = share
    if compared and not (dim["total"]["figure"] and pdim["total"]["figure"]):
        entry["status"] = "no_figure"
    elif compared:
        entry.update(_metrics(compared, dkey, key, dim, prevs, basis, history, upto, lambda d: d["total"]["figure"]))

    verdicts = []
    for q in compared:
        # A band crossed by a small move is noise: the pair's mean must move by the step a
        # change of the question's mean needs.
        periods = (entry["questions"][q].get("mean") or {}).get("periods", len(prevs))
        step = STEPS["mean"][1 if periods == 1 else 0]
        for m in sorted(basis):
            before = pdim["questions"][q]["by_model"].get(m, {}).get("mean")
            after = dim["questions"][q]["by_model"].get(m, {}).get("mean")
            if band(before) and band(after) and band(before) != band(after) and abs(after - before) >= step - EPS:
                verdicts.append({"project": key, "dimension": dkey, "question": q, "model": m,
                                 "from": band(before), "to": band(after), "previous_mean": before, "mean": after,
                                 "previous_answer": _closest(answers(prev, key, q, m), before),
                                 "answer": _closest(answers(current, key, q, m), after)})

    def cited(here, there):
        """Domains at least two answers cite here and none there."""
        return [{"project": key, "dimension": dkey, "domain": d, "answers": n, "owned": is_owned(d, owned)}
                for d, n in sorted(here.items(), key=lambda kv: (-kv[1], kv[0])) if n >= 2 and not there.get(d)]
    now_d, prev_d = _pool(dim, shared, basis)["domains"], _pool(pdim, shared, basis)["domains"]
    return entry, verdicts, {"new": cited(now_d, prev_d), "lost": cited(prev_d, now_d)}


def _metrics(questions, dkey, key, dim, prevs, basis, history, upto, figure_of):
    now = _pool(dim, questions, basis)
    return {kind: _metric(kind, now[kind], _series(kind, key, dkey, questions, basis, prevs, history, upto, figure_of))
            for kind in ("mean", "presence")}


def _current_share(q, dkey, key, dim, prevs, basis, history, upto):
    """A question's share of answers stating a current term, against the earlier periods that
    counted the same terms."""
    terms = (dim["questions"][q].get("facts") or {}).get("terms")
    if not terms:
        return None

    def same(d):
        return d["questions"][q]["total"]["figure"] and (d["questions"][q].get("facts") or {}).get("terms") == terms
    return _metric("current_share", _pool(dim, [q], basis)["current_share"],
                   _series("current_share", key, dkey, [q], basis, prevs, history, upto, same))


def _project(key, block, entries, prevs, basis, history, upto):
    """The project's mean on the dimensions compared, each on its compared questions and the
    models of both periods, against the earlier periods that hold all of them."""
    dims = {d: e["compared_questions"] for d, e in entries.items() if e.get("mean")}
    if not dims:
        return None

    def value(b):
        means = [_pool(b["dimensions"][d], qs, basis)["mean"] for d, qs in dims.items()]
        return None if None in means else mean(means)
    values = []
    for p in prevs:
        pb = p["projects"].get(key)
        blocked = set(history.blocked(_version_max(p, key), upto))
        if pb is None or not basis <= _models(pb) or any(
                d not in pb["dimensions"] or blocked & set(qs) or not set(qs) <= set(_asked(pb["dimensions"][d]))
                for d, qs in dims.items()):
            break
        v = value(pb) if all(pb["dimensions"][d]["total"]["figure"] for d in dims) else None
        if v is not None:
            values.append(v)
    metric = _metric("mean", value(block), values)
    return {"dimensions": sorted(dims), "mean": metric} if metric else None


def _closest(responses, target):
    """Of a pair's (run start, run id, response), the one whose score is nearest the pair's
    mean `target`; the latest on a tie."""
    if not responses:
        return None
    start, run_id, r = max(responses, key=lambda x: (-abs(x[2]["score"] - target), x[0]))
    return {"run_id": run_id, "response_id": r["response_id"], "score": r["score"]}
