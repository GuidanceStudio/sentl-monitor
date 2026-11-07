"""`runs`: the arguments of list-runs-tool for a report's window, and, from a saved response, which
runs to fetch: for a report, the completed runs of its window not yet ingested, by start time; for
adopt, the latest completed run. Sentl's listing is newest first with exceptions."""

import json
from collections import Counter

from . import schema
from .common import FINAL, RUN_FLOOR, Refused, Study, load_json, parse_time
from .period import cadence, intervals, previous_cut


def _start(r):
    return parse_time(r["started_at"])


def _day(r):
    return r["started_at"][:10] if r["started_at"] else "no start time"


def _shown(r, note=None):
    note = note or r.get("error")
    return f"run {r['id']} ({r['status']}, started {_day(r)}{': ' + note if note else ''})"


def _state(rows, inside=None):
    """The lines on the runs not final yet, ended with no results and of statuses never seen: for a
    report, those of its window and those with no start time."""
    lines = []
    if inside:
        rows = [r for r in rows if not r["started_at"] or inside(r)]
    for start, wanted in (("Not final yet, read again at the next invocation: ", lambda s: s in schema.OPEN),
                          ("Ended with no results, left out of the period (tell the operator): ",
                           lambda s: s in schema.ENDED),
                          ("Status never seen, so the run is not fetched (tell the operator): ",
                           lambda s: s not in schema.STATUSES)):
        shown = [_shown(r) for r in rows if wanted(r["status"])]
        if shown:
            lines.append(start + "; ".join(shown) + ".")
    return lines


def _under_floor(r):
    """Whether the listing already shows a run under the judged floor. A listing without the counts
    says nothing, and the run is decided from its results."""
    return bool(r.get("expected")) and r.get("judged") is not None and r["judged"] / r["expected"] < RUN_FLOOR


def _for_adopt(rows):
    done = sorted((r for r in rows if r["status"] in FINAL), key=lambda r: (_start(r), r["id"]), reverse=True)
    if not done:
        return ["No completed run in the listing: adopt without --run, and tell the operator that the saved "
                "project could not be checked against a run."]
    latest = done[0]
    lines = [f"{len(done)} completed run{'s' if len(done) > 1 else ''}, started from {_day(done[-1])} to "
             f"{_day(latest)}.",
             f"Latest completed run: {latest['id']}, started {latest['started_at']}. Save its results for adopt."]
    if len(done) > 1:
        lines.append("If Sentl cannot return them, try the next completed runs in this order, newest first: "
                     + ", ".join(str(r["id"]) for r in done[1:]) + ".")
    return lines


def _ingested(folder, key):
    return {int(p.name.split(".")[0]) for p in folder.path("history", "runs", key).glob("*.json.gz")}


def _window(folder, key, date, through=False):
    """When the report's runs start from, whether that moment is left out, when they stop, and the last
    report it follows, if any. With `through`, a report dated `date` is the previous one."""
    reports = [e for e in folder.reports() if e["date"] < date or (through and e["date"] == date)]
    bounds = intervals(date, cadence(folder.study))
    if not reports:
        return bounds[-1][0], False, bounds[0][1], None
    last, ingested = reports[-1], _ingested(folder, key)
    started = {i: parse_time(folder.run(key, i)["started_at"]) for i in last["runs"].get(key, []) if i in ingested}
    return previous_cut(last, key, started), True, bounds[0][1], last


def _unavailable(folder, key):
    path = folder.path("history", "unavailable.json")
    return {e["run_id"] for e in (load_json(path)["runs"] if path.exists() else []) if e["project"] == key}


def _for_report(folder, key, rows, date, through=False, complete=False):
    """The lines of the report on `key`, the runs to fetch, the count of runs already ingested inside
    the window, and the count of runs left out with no read. With `through`, a report dated `date` is
    the previous one; `complete` says the listing states its total, so nothing older can be missing."""
    every = cadence(folder.study)
    ingested = _ingested(folder, key)
    start, later, end, last = _window(folder, key, date, through)
    if last:
        lines = [f"Report of {date} on {key}: the completed runs started after the last run of the report of "
                 f"{last['date']} ({start.isoformat().replace('+00:00', 'Z')}) and up to the end of {date}."]
    else:
        lines = [f"First report of {date} on {key}: the completed runs started from {start.date()} to {date}, the "
                 f"report's {'week' if every == 'weekly' else 'month'} and the four before it, rebuilt for the "
                 "comparison."]

    def inside(r):
        at = _start(r)
        return (at > start if later else at >= start) and at < end

    unavailable = _unavailable(folder, key)
    done = [r for r in rows if r["status"] in FINAL]
    wanted = [r for r in done if r["id"] not in ingested and (inside(r) or r["id"] in unavailable)]
    # A snapshot keeps every answer it got: the floor is for a monitored period.
    under = [] if folder.study.get("kind") == "snapshot" else [r for r in wanted if _under_floor(r)]
    fetch = sorted((r for r in wanted if r not in under), key=lambda r: (_start(r), r["id"]))
    if fetch:
        lines.append(f"Runs to fetch with get-run-results-tool, by start time ({len(fetch)}):")
        for r in fetch:
            notes = []
            if r["id"] in unavailable:
                notes.append("unavailable before: request it again")
            saved = folder.path("inbox", f"run-{r['id']}.json")
            if saved.exists():
                notes.append(f"already saved: ingest inbox/{saved.name}")
            lines.append(f"  run {r['id']}, started {r['started_at']}, {r['status']}"
                         + "".join(f"; {n}" for n in notes))
    else:
        lines.append("No run to fetch.")
    already = sum(1 for r in done if r["id"] in ingested and inside(r))
    if already:
        lines.append(f"Already ingested: {already} run{'s' if already > 1 else ''} of the window.")
    if under:
        lines.append(f"Under the {RUN_FLOOR:.0%} floor in the listing, so not fetched (tell the operator): "
                     + "; ".join(_shown(r, f"{r['judged']} of {r['expected']} judged") for r in under) + ".")
    lines += _state(rows, inside)
    starts = [_start(r) for r in rows if r["started_at"]]
    if not starts:
        lines.append("Warning: the listing holds no run with a start time; tell the operator.")
    elif min(starts) > start and not complete:
        first = min(starts).date()
        lines.append(f"Warning: the oldest run in the listing started on {first}, after the window's start, "
                     f"{start.date()}. Either the project has no run before {first}, or the listing, saved without "
                     f"its total and its paging, stops there and runs before {first} cannot be read: tell the operator.")
    lines.append("Fetch: " + (" ".join(str(r["id"]) for r in fetch) or "none"))
    left = Counter({f"under the {RUN_FLOOR:.0%} floor": len(under),
                    "ended with no results": sum(1 for r in rows if r["status"] in schema.ENDED and r["started_at"]
                                                 and inside(r))})
    return lines, fetch, already, left


def _bound_listing(folder, key, saved):
    listing = schema.run_listing(saved)
    folder.project(key)
    listing["complete"] = listing.get("total") is not None
    bound = folder.binding["projects"].get(key)
    if bound is None:
        raise Refused(f"project {key!r} has no binding in sentl.json: run adopt first")
    if listing["project_id"] != bound["project_id"]:
        raise Refused(f"the saved listing is of project {listing['project_id']}, but {key} is bound to project "
                      f"{bound['project_id']}: save list-runs-tool's response for the right project")
    return listing


def arguments(folder, key, date):
    """What to pass to list-runs-tool for a report, before there is a listing to read."""
    folder.project(key)
    bound = folder.binding["projects"].get(key)
    if bound is None:
        raise Refused(f"project {key!r} has no binding in sentl.json: run adopt first")
    args = {"project_id": bound["project_id"]}
    note = "Read the whole answer; on a host that cuts large responses pass page and page_size too, and every page to --saved."
    if _unavailable(folder, key):
        note = "A run recorded as unavailable is read again whenever it started, so the listing is not narrowed. " + note
    else:
        args["started_after"] = _window(folder, key, date)[0].isoformat().replace("+00:00", "Z")
    return f"list-runs-tool arguments for the report of {date} on {key}: {json.dumps(args)}\n{note}"


def runs(root, saved, key=None, date=None):
    if key is None:
        if not saved:
            raise Refused("pass --saved with list-runs-tool's response, or --project for the arguments to call it with")
        rows = schema.run_listing(saved)["runs"]
        return "\n".join(_for_adopt(rows) + _state(rows))
    folder = Study(root)
    if not saved:
        return arguments(folder, key, date)
    listing = _bound_listing(folder, key, saved)
    return "\n".join(_for_report(folder, key, listing["runs"], date, complete=listing["complete"])[0])


def pending(root, date):
    """Whether an unattended report has a completed run to report on, from the listings saved as
    inbox/runs-<project id>.json. With none, `nothing_new` is recorded and the report stops."""
    folder = Study(root)
    fetch, already, waiting, left = 0, 0, 0, Counter()
    for key, bound in folder.binding["projects"].items():
        saved = folder.path("inbox", f"runs-{bound['project_id']}.json")
        if not saved.is_file():
            raise Refused(f"inbox/{saved.name} not found: save list-runs-tool's response for project "
                          f"{bound['project_id']} there first")
        pages = [saved, *sorted(folder.path("inbox").glob(f"runs-{bound['project_id']}.p*.json"))]
        listing = _bound_listing(folder, key, pages)
        rows = listing["runs"]
        _, to_fetch, ingested, skipped = _for_report(folder, key, rows, date, through=True, complete=listing["complete"])
        fetch, already, left = fetch + len(to_fetch), already + ingested, left + skipped
        waiting += sum(1 for r in rows if r["status"] in schema.OPEN)
    if fetch or already:
        return (f"{fetch} run{'s' if fetch != 1 else ''} to fetch, {already} already ingested and not yet reported: "
                f"write the report of {date}.")
    earlier = [e for e in folder.reports() if e["date"] <= date]
    detail = (f"no completed run is new since the report of {earlier[-1]['date']}" if earlier
              else "no completed run in the window of the first report")
    detail += f"; {waiting} not final yet" if waiting else ""
    detail += "".join(f"; {n} {what}" for what, n in left.items())
    folder.record_outcome("nothing_new", detail)
    return f"nothing_new: {detail}. Stop: write nothing."
