"""The shape of each Sentl tool response the skill reads: the fields, their types and their
ranges (ARCHITECTURE.md §Responses from Sentl). A saved response that does not match is
refused before anything is written, naming the tool and the field (exit code 5). Fields the
skill does not read are accepted, so Sentl can add fields without breaking a report."""

import re
from pathlib import Path

from .common import FINAL, Refused, load_mcp, parse_time, read_mcp

# The nine statuses Sentl documents. A run in OPEN is not final yet and is read again at the next
# invocation; a run in ENDED is final with no results to fetch. Any other status is one the skill
# has never seen.
OPEN = ("queued", "pending", "researching", "running", "judging")
ENDED = ("failed", "stalled")
STATUSES = FINAL + ENDED + OPEN

_MISSING = object()


class Mismatch(Exception):
    """A Sentl response whose shape differs from what the skill reads; exit code 5."""


class _Leaf:
    def __init__(self, expected, ok):
        self.expected, self.ok = expected, ok

    def check(self, value, path, errors):
        if not self.ok(value):
            errors.append((path, self.expected, value))


class _Object:
    """An object with the fields the skill reads: {name: (spec, required)}. Other fields pass."""

    expected = "an object"

    def __init__(self, fields):
        self.fields = fields

    def check(self, value, path, errors):
        if not isinstance(value, dict):
            errors.append((path, self.expected, value))
            return
        for name, (spec, required) in self.fields.items():
            sub = f"{path}.{name}" if path else name
            if name in value:
                spec.check(value[name], sub, errors)
            elif required:
                errors.append((sub, spec.expected, _MISSING))


class _List:
    def __init__(self, item, expected, nullable=False):
        self.item, self.expected, self.nullable = item, expected, nullable

    def check(self, value, path, errors):
        if value is None and self.nullable:
            return
        if not isinstance(value, list):
            errors.append((path, self.expected, value))
            return
        for n, v in enumerate(value):
            self.item.check(v, f"{path}[{n}]", errors)


class _Map:
    """An object whose keys are ids, each holding the same kind of object."""

    def __init__(self, item, expected):
        self.item, self.expected = item, expected

    def check(self, value, path, errors):
        if not isinstance(value, dict):
            errors.append((path, self.expected, value))
            return
        for k, v in value.items():
            self.item.check(v, f"{path}[{k!r}]", errors)


def _integer(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _time(v):
    if not isinstance(v, str):
        return False
    try:
        parse_time(v)
    except ValueError:
        return False
    return True


INTEGER = _Leaf("an integer", _integer)
COUNT = _Leaf("an integer of 1 or more", lambda v: _integer(v) and v >= 1)
TALLY = _Leaf("an integer of 0 or more, or null", lambda v: v is None or (_integer(v) and v >= 0))
ID_OR_NULL = _Leaf("an integer, or null", lambda v: v is None or _integer(v))
TEXT = _Leaf("a non-empty text", lambda v: isinstance(v, str) and bool(v.strip()))
STRING = _Leaf("a text", lambda v: isinstance(v, str))
TEXT_OR_NULL = _Leaf("a text, or null", lambda v: v is None or isinstance(v, str))
BOOLEAN = _Leaf("true or false", lambda v: isinstance(v, bool))
TIME = _Leaf("an ISO 8601 date and time", _time)
TIME_OR_NULL = _Leaf("an ISO 8601 date and time, or null", lambda v: v is None or _time(v))
SCORE = _Leaf("an integer from 1 to 5, or null", lambda v: v is None or (_integer(v) and 1 <= v <= 5))
RUN_SCORE = _Leaf("a number from 1 to 5, or null", lambda v: v is None or (_number(v) and 1 <= v <= 5))
# Sentl does not require every anchor: a rubric may be null, empty or partial.
RUBRIC = _Leaf("null, or an object whose keys are anchors from 1 to 5, each a text or null",
               lambda v: v is None or (isinstance(v, dict) and set(v) <= set("12345")
                                       and all(t is None or isinstance(t, str) for t in v.values())))
STATUS = _Leaf("one of the statuses the skill knows: " + ", ".join(FINAL) + " (final); " + ", ".join(ENDED)
               + " (final, no results); " + ", ".join(OPEN) + " (not final yet)", lambda v: v in STATUSES)

# get-project-tool, under "project".
PROJECT = _Object({
    "id": (INTEGER, True),
    "name": (TEXT, True),
    "schedule_frequency": (TEXT_OR_NULL, True),
    "rounds": (COUNT, True),
    "is_active": (BOOLEAN, False),
    "kind": (_Leaf("project or snapshot", lambda v: v in ("project", "snapshot")), False),
    "archived": (BOOLEAN, False),
    "researcher_model_ids": (_List(TEXT, "a list of model ids"), True),
    "dimensions": (_List(_Object({
        "id": (INTEGER, True),
        "name": (TEXT, True),
        "archived": (BOOLEAN, False),
        "questions": (_List(_Object({
            "id": (INTEGER, True),
            "question": (TEXT, True),
            "label": (TEXT_OR_NULL, False),
            "grading_rubric": (RUBRIC, True),
            "additional_instructions": (TEXT_OR_NULL, False),
            "updated_at": (TIME_OR_NULL, False),
        }), "a list of questions"), True),
    }), "a list of dimensions"), True),
})

# get-run-results-tool, under "run". Sources are url and title, in citation order. Fields the
# skill only copies into the run snapshot (trigger, finished_at, error, sentiment) take any value.
RUN = _Object({
    "id": (INTEGER, True),
    "project_id": (INTEGER, True),
    "status": (STATUS, True),
    "started_at": (TIME, True),
    "reputation_score": (RUN_SCORE, True),
    "responses": (_List(_Object({
        "id": (INTEGER, True),
        "model_id": (TEXT, True),
        "round": (COUNT, False),
        "question_id": (ID_OR_NULL, False),
        "dimension_id": (ID_OR_NULL, False),
        "dimension": (TEXT, True),
        "question": (TEXT, True),
        "answer": (TEXT_OR_NULL, True),
        "judge_score": (SCORE, True),
        "sources": (_List(_Object({"url": (STRING, True), "title": (TEXT_OR_NULL, False)}),
                          "a list of sources, or null", nullable=True), True),
        # The rubric and instructions the answer was judged under, when Sentl returns them.
        "grading_rubric": (RUBRIC, False),
        "additional_instructions": (TEXT_OR_NULL, False),
    }), "a list of responses"), True),
})

# The results of a run not final yet, or ended with none: only what says so is read.
RUN_OPEN = _Object({"id": (INTEGER, True), "status": (STATUS, True)})

# list-runs-tool, at the top level. A status is any text here: `runs` reports one it has never
# seen instead of refusing the listing.
LISTING = _Object({
    "project_id": (INTEGER, True),
    "total": (TALLY, False),
    "next_page": (ID_OR_NULL, False),
    "runs": (_List(_Object({
        "id": (INTEGER, True),
        "status": (TEXT, True),
        "started_at": (TIME_OR_NULL, True),
        "expected": (TALLY, False),
        "judged": (TALLY, False),
    }), "a list of runs"), True),
})

# list-ai-models, under "researcher_models": each model id with its public name.
# `credits` is the tariff per call; only `review` reads it.
CREDITS = _Leaf("a number of 0 or more", lambda v: _number(v) and v >= 0)
MODELS = _Map(_Object({"name": (TEXT, True), "credits": (CREDITS, False)}), "an object of model ids")


def _found(value):
    if isinstance(value, dict):
        return "an object"
    if isinstance(value, list):
        return "a list"
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _unit(group):
    """The kind of item a field repeats over: the name before its last []."""
    names = re.findall(r"([A-Za-z_]+)\[\]", group)
    return names[-1].split("_")[-1] if names else "items"


def _refuse(tool, path, errors):
    groups = {}
    for field, expected, value in errors:
        group = re.sub(r"\[[^\]]*\]", "[]", field)
        if group not in groups:
            groups[group] = [field, expected, value, 0]
        groups[group][3] += 1
    lines = [f"Sentl's {tool} response in {path} does not have the shape this skill reads:"]
    for group, (field, expected, value, count) in list(groups.items())[:10]:
        where = f" (in {count} {_unit(group)})" if count > 1 else ""
        if value is _MISSING:
            lines.append(f"  {field}: missing, expected {expected}{where}")
        else:
            lines.append(f"  {field}: expected {expected}, found {_found(value)}{where}")
    if len(groups) > 10:
        lines.append(f"  and {len(groups) - 10} more fields")
    lines.append("Fields the skill does not read are accepted; a field it reads that is missing, renamed, of "
                 "another type or out of range is not. Nothing was written.")
    raise Mismatch("\n".join(lines))


# The top-level key of each tool's response, to tell a file saved from another tool.
TOOL_KEYS = {"project": "get-project-tool", "run": "get-run-results-tool", "runs": "list-runs-tool",
             "researcher_models": "list-ai-models", "projects": "list-projects-tool"}


# What the skill does on each error code of the read tools.
ERROR_RULE = {"internal": "call the tool once more", "not_found": "stop and check the id",
              "invalid_argument": "stop: the skill needs an update"}


def _sentl_error(raw, path, tool):
    """A saved error is Sentl's answer, not a response of another shape (exit 2)."""
    error = raw.get("error") if isinstance(raw, dict) else None
    if isinstance(error, dict) and error.get("code"):
        code = error["code"]
        raise Refused(f"{path} holds Sentl's error, not {tool}'s response: {code}: {error.get('message')} "
                      f"Tell the operator; {ERROR_RULE.get(code, 'stop')}. Nothing was written.")


def _read(path, tool, key):
    """The object under `key`. A file holding another tool's response is input to save again
    (exit 2), not a change in Sentl."""
    raw = read_mcp(path)
    _sentl_error(raw, path, tool)
    if isinstance(raw, dict) and key not in raw:
        other = next((name for k, name in TOOL_KEYS.items() if k in raw and name != tool), None)
        if other:
            raise Refused(f"{path} holds a {other} response, not {tool}'s: save {tool}'s response to it and run "
                          "the command again")
    return load_mcp(path, key, raw)


def _load(path, tool, key, spec, extra=None, data=None):
    data = _read(path, tool, key) if data is None else data
    errors = []
    spec.check(data, key or "", errors)
    if extra and not errors:
        extra(data, errors)
    if errors:
        _refuse(tool, path, errors)
    return data


def project(path):
    return _load(path, "get-project-tool", "project", PROJECT)


def run_results(path):
    """A run's results; a run not final yet is read only for its id and status."""
    data = _read(path, "get-run-results-tool", "run")
    spec = RUN_OPEN if data.get("status") in OPEN + ENDED else RUN
    return _load(path, "get-run-results-tool", "run", spec, data=data)


def _started(listing, errors):
    for n, r in enumerate(listing["runs"]):
        if r["status"] in FINAL and r["started_at"] is None:
            errors.append((f"runs[{n}].started_at", "an ISO 8601 date and time on a completed run", None))


def run_listing(paths):
    """A list-runs-tool response, from one file or from the files of its pages. A listing that
    says it holds more runs than were read is refused, naming the page to read."""
    paths = [paths] if isinstance(paths, (str, Path)) else list(paths)
    pages = [_load(p, "list-runs-tool", "runs", LISTING, _started) for p in paths]
    projects = {p["project_id"] for p in pages}
    if len(projects) > 1:
        raise Refused(f"the saved listings are of projects {', '.join(map(str, sorted(projects)))}: pass the pages of "
                      "one project")
    rows = list({r["id"]: r for p in pages for r in p["runs"]}.values())
    total = max((p["total"] for p in pages if p.get("total") is not None), default=None)
    if total is not None and len(rows) < total:
        following = sorted(p["next_page"] for p in pages if p.get("next_page"))
        ask = f"read page {following[-1]} and the ones after it" if following else "read the listing again"
        raise Refused(f"the saved listing holds {len(rows)} of the {total} runs: {ask} with list-runs-tool and pass "
                      "every page")
    return {**pages[0], "runs": rows}


def models(path):
    return _load(path, "list-ai-models", "researcher_models", MODELS)


def check_project(data, where):
    """A project object already read, as an export holds it."""
    return _load(where, "get-project-tool", "project", PROJECT, data=data)


def check_run(data, where):
    """A run object already read, as an export holds it; a run not final yet is read for its id and status only."""
    spec = RUN_OPEN if isinstance(data, dict) and data.get("status") in OPEN + ENDED else RUN
    return _load(where, "get-run-results-tool", "run", spec, data=data)
