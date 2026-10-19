"""`runs`: read a saved list-runs-tool response and say which runs to fetch: for a report,
the completed runs of its window not yet ingested, by start time; for adopt, the latest
completed run. Sentl's listing is newest first with exceptions, and has no paging."""

from . import schema
from .common import FINAL, Refused, Study, load_json, parse_time
from .period import cadence, intervals, previous_cut


def _start(r):
    return parse_time(r["started_at"])


def _day(r):
    return r["started_at"][:10] if r["started_at"] else "no start time"


def _state(rows, inside=None):
    """The lines on the runs not final yet and on statuses never seen: for a report, those of
    its window and those with no start time."""
    lines = []
    if inside:
        rows = [r for r in rows if not r["started_at"] or inside(r)]
    waiting = [r for r in rows if r["status"] in schema.OPEN]
    unseen = [r for r in rows if r["status"] not in schema.STATUSES]
    if waiting:
        lines.append("Not final yet, read again at the next invocation: "
                     + "; ".join(f"run {r['id']} ({r['status']}, started {_day(r)})" for r in waiting) + ".")
    if unseen:
        lines.append("Status never seen, so the run is not fetched (tell the operator): "
                     + "; ".join(f"run {r['id']} ({r['status']}, started {_day(r)})" for r in unseen) + ".")
    return lines


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


def _for_report(folder, key, rows, date):
    every = cadence(folder.study)
    reports = [e for e in folder.reports() if e["date"] < date]
    bounds = intervals(date, every)
    end = bounds[0][1]
    ingested = {int(p.name.split(".")[0]) for p in folder.path("history", "runs", key).glob("*.json.gz")}
    if reports:
        last = reports[-1]
        started = {i: parse_time(folder.run(key, i)["started_at"]) for i in last["runs"].get(key, []) if i in ingested}
        start, later = previous_cut(last, key, started), True
        lines = [f"Report of {date} on {key}: the completed runs started after the last run of the report of "
                 f"{last['date']} ({start.isoformat().replace('+00:00', 'Z')}) and up to the end of {date}."]
    else:
        start, later = bounds[-1][0], False
        lines = [f"First report of {date} on {key}: the completed runs started from {start.date()} to {date}, the "
                 f"report's {'week' if every == 'weekly' else 'month'} and the four before it, rebuilt for the "
                 "comparison."]

    def inside(r):
        at = _start(r)
        return (at > start if later else at >= start) and at < end

    path = folder.path("history", "unavailable.json")
    unavailable = {e["run_id"] for e in (load_json(path)["runs"] if path.exists() else []) if e["project"] == key}
    done = [r for r in rows if r["status"] in FINAL]
    fetch = sorted((r for r in done if r["id"] not in ingested and (inside(r) or r["id"] in unavailable)),
                   key=lambda r: (_start(r), r["id"]))
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
    lines += _state(rows, inside)
    starts = [_start(r) for r in rows if r["started_at"]]
    if not starts:
        lines.append("Warning: the listing holds no run with a start time; tell the operator.")
    elif min(starts) > start:
        first = min(starts).date()
        lines.append(f"Warning: the oldest run in the listing started on {first}, after the window's start, "
                     f"{start.date()}. Either the project has no run before {first}, or Sentl's listing, which has no "
                     f"paging, stops there and runs before {first} cannot be read: tell the operator.")
    lines.append("Fetch: " + (" ".join(str(r["id"]) for r in fetch) or "none"))
    return lines


def runs(root, saved, key=None, date=None):
    listing = schema.run_listing(saved)
    rows = listing["runs"]
    if key is None:
        return "\n".join(_for_adopt(rows) + _state(rows))
    folder = Study(root)
    folder.project(key)
    bound = folder.binding["projects"].get(key)
    if bound is None:
        raise Refused(f"project {key!r} has no binding in sentl.json: run adopt first")
    if listing["project_id"] != bound["project_id"]:
        raise Refused(f"the saved listing is of project {listing['project_id']}, but {key} is bound to project "
                      f"{bound['project_id']}: save list-runs-tool's response for the right project")
    return "\n".join(_for_report(folder, key, rows, date))
