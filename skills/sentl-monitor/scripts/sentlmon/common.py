"""Files, text normalization and number formatting shared by every command."""

import datetime as dt
import functools
import gzip
import json
import os
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import urlparse

from .i18n import SECTIONS

FINAL = ("completed", "completed_with_warnings")
RUN_FLOOR = 0.90
FIGURE_FLOOR = 0.80
OUTCOMES = ("written", "draft", "nothing_new", "below_floor")


class Refused(Exception):
    """Input the command cannot act on; exit code 2."""


def require_language(study):
    """Refuse a report language the report has no wording for; an unset one is the operator's to answer."""
    lang = study.get("report_language")
    if lang is not None and lang not in SECTIONS:
        raise Refused(f"report_language {lang!r} is not supported; supported: {', '.join(sorted(SECTIONS))}")


# --- files ------------------------------------------------------------------

def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def read_mcp(path):
    """Read a saved MCP response, as the tool returned it.

    A host saves either the tool's JSON text or the MCP content list around it
    ([{"type": "text", "text": ...}]); both are accepted. A file that cannot be read,
    or a response that does not parse, is refused, because a host that truncates
    output cuts it mid-string.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise Refused(f"{path} cannot be read ({exc.strerror or exc}): save the tool's response to it again") from None
    except UnicodeDecodeError:
        raise Refused(f"{path} is not UTF-8 text: save the tool's response to it again") from None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise Refused(f"{path} is not complete JSON ({exc.msg} at character {exc.pos}): "
                      "save the tool's response again, from the file the host wrote if it was large") from None
    for _ in range(3):
        if isinstance(data, dict) and isinstance(data.get("content"), list):
            data = data["content"]
        if isinstance(data, list) and data and all(isinstance(b, dict) and "text" in b for b in data):
            try:
                data = json.loads("".join(b["text"] for b in data))
            except json.JSONDecodeError as exc:
                raise Refused(f"{path} holds text that is not complete JSON ({exc.msg})") from None
            continue
        break
    return data


def load_mcp(path, key, data=None):
    """The object under `key` of a saved MCP response (`data`, when it was read already)."""
    data = read_mcp(path) if data is None else data
    if isinstance(data, dict) and key in data and isinstance(data[key], dict):
        return data[key]
    if isinstance(data, dict):
        return data
    raise Refused(f"{path} does not hold a {key} object")


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def write_gz(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    # mtime=0 keeps the bytes identical for identical content.
    with gzip.GzipFile(tmp, "wb", mtime=0) as fh:
        fh.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    os.replace(tmp, path)


class Study:
    """Paths and the two design files of a study folder."""

    def __init__(self, root):
        self.root = Path(root)

    def path(self, *parts):
        return self.root.joinpath(*parts)

    @property
    def study(self):
        return self._require("study.json")

    @property
    def binding(self):
        return self._require("sentl.json")

    def _require(self, name):
        p = self.path(name)
        if not p.exists():
            raise Refused(f"{name} not found in {self.root}: run adopt first")
        return load_json(p)

    def project(self, key):
        for proj in self.study["projects"]:
            if proj["key"] == key:
                return proj
        raise Refused(f"no project {key!r} in study.json; projects: "
                      + ", ".join(p["key"] for p in self.study["projects"]))

    def versions(self, key):
        folder = self.path("history", "versions")
        return [load_json(p) for p in sorted(folder.glob(f"{key}-[0-9][0-9][0-9].json"))]

    def runs(self, key):
        folder = self.path("history", "runs", key)
        return [read_gz(p) for p in sorted(folder.glob("*.json.gz"))]

    def run(self, key, run_id):
        return read_gz(self.path("history", "runs", key, f"{run_id}.json.gz"))

    def reports(self):
        """history/reports.json: one entry per report, in date order."""
        path = self.path("history", "reports.json")
        return load_json(path) if path.exists() else []

    def require_runs(self, periods, date):
        """Refuse when `periods` list runs that history/runs does not hold. A study folder never
        deletes a run; one unpacked from a pack written without --full holds the runs the next
        period reads, and not those of the periods before the latest one."""
        lacking = sorted({(key, run_id) for period in periods for key, ids in (period.get("runs") or {}).items()
                          for run_id in ids if not self.path("history", "runs", key, f"{run_id}.json.gz").is_file()},
                         key=str)
        if lacking:
            shown = ", ".join(f"run {i} of {k}" for k, i in lacking[:5]) + (", ..." if len(lacking) > 5 else "")
            raise Refused(f"the period of {date} reads runs this folder does not hold ({shown}): the folder was "
                          "unpacked from a pack written without --full, which holds what the next period reads. "
                          f"To build the period of {date} again, unpack a pack written with --full")

    def record_report(self, entry):
        """One entry per date. An entry written again keeps the deck an earlier check recorded beside it."""
        old = next((e for e in self.reports() if e["date"] == entry["date"]), {})
        if "deck" in old and "deck" not in entry:
            entry = {**entry, "deck": old["deck"]}
        entries = [e for e in self.reports() if e["date"] != entry["date"]] + [entry]
        write_json(self.path("history", "reports.json"), sorted(entries, key=lambda e: e["date"]))

    def record_period(self, date, period, **fields):
        """The entry of the period of `date`: the runs it read, so the next period starts after them, and the period it
        compared with. `fields` adds to it or replaces what it holds (`status`, `deck`)."""
        self.record_report({"date": date, "status": "final", "period": {"from": period["from"], "to": period["to"]},
                            "runs": period["runs"], "previous": (period.get("comparison") or {}).get("previous"),
                            **fields})

    def record_outcome(self, outcome, detail):
        """history/last-report.json: how the latest report invocation ended."""
        if outcome not in OUTCOMES:
            raise ValueError(f"unknown outcome {outcome!r}")
        write_json(self.path("history", "last-report.json"),
                   {"at": now_iso(), "outcome": outcome, "detail": " ".join(detail.split())})


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


def passed_deck(entry):
    """Whether the reports.json entry has a deck that passed check: one recorded in `deck`, or one an earlier version
    recorded in the report's place, as a final `file`. A long report an earlier version wrote is no deck."""
    return bool(entry.get("deck")) or (entry.get("status") == "final" and entry.get("file", "").endswith(".deck.json"))


# --- text -------------------------------------------------------------------

_QUOTES = str.maketrans({
    **dict.fromkeys("‘’‚‛′´", "'"),
    **dict.fromkeys("“”„‟″«»", '"'),
    **dict.fromkeys("‐‑‒–—―−", "-"),
})


def norm(text):
    """The comparison form of a text: NFKC, plain quotes, collapsed whitespace."""
    if text is None:
        return ""
    return " ".join(unicodedata.normalize("NFKC", text).translate(_QUOTES).split())


def match_key(text):
    return norm(text).casefold()


def fold(text):
    """Case- and accent-folded, for finding aliases in answers."""
    decomposed = unicodedata.normalize("NFKD", norm(text).casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


@functools.lru_cache(maxsize=None)
def folded(text):
    """`fold`, computed once per text: each answer is read by several figures. `period`
    clears the cache when it starts."""
    return fold(text)


def slug(text):
    words = re.findall(r"[a-z0-9]+", fold(text))
    return "-".join(words) or "project"


# A Markdown link, inline or by reference: its label, then its target. One level of brackets in a label and of
# parentheses in an address (a wiki page's "Name_(company)") is read.
_LINK = re.compile(r"!?\[((?:[^\[\]]|\[[^\[\]]*\])*)\]"
                   r"(?:\(\s*(?:<[^<>]*>|(?:[^()\s]|\([^()\s]*\))*)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^()]*\)))?\s*\)"
                   r"|\[[^\[\]]*\])")
_LINK_DEFINITION = re.compile(r"^[ \t]*\[[^\[\]]+\]:[ \t]*\S.*$", re.M)
_ADDRESS = re.compile(r"(?:https?://)?(?:www\.)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?::\d+)?(?:[/?#]\S*)?", re.I)
_BARE_ADDRESS = re.compile(r"(?<![\w@.-])(?:https?://|www\.)[^\s<>\[\]\"]+", re.I)


@functools.lru_cache(maxsize=None)
def prose(text):
    """The text of an answer as its reader reads it, where a name counts: a link keeps its label and loses its address,
    a link whose label is itself a domain or an address goes whole, and so do bare addresses (http://, https://, www.)
    and the definitions of reference links. A domain written in a sentence stays. `period` clears the cache."""
    if not text:
        return ""

    def label(m):
        return "" if _ADDRESS.fullmatch(m.group(1).strip(" *_`")) else m.group(1)
    return _BARE_ADDRESS.sub("", _LINK.sub(label, _LINK_DEFINITION.sub("", text)))


def first_mention(folded_answer, aliases):
    """Character offset of the first alias found on word boundaries, or None."""
    best = None
    for alias in aliases:
        a = folded(alias)
        if not a:
            continue
        m = re.search(r"(?<!\w)" + re.escape(a) + r"(?!\w)", folded_answer)
        if m and (best is None or m.start() < best):
            best = m.start()
    return best


REDIRECT_HOSTS = ("vertexaisearch.cloud.google.com",)
HOSTNAME = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")


def domain_of(url, title=None):
    """The cited site's domain, without www. A grounding redirect hides the site in its
    URL; its title carries the site's domain, and is used when it looks like one."""
    host = (urlparse(url or "").hostname or "").lower()
    named = (title or "").strip().lower()
    if host in REDIRECT_HOSTS and HOSTNAME.fullmatch(named):
        host = named
    return host[4:] if host.startswith("www.") else host


def is_owned(domain, owned):
    return any(domain == o or domain.endswith("." + o) for o in (d.lower().removeprefix("www.") for d in owned))


def public_name(model, names):
    """The model's public name from a list-ai-models response; from its id when the model
    is no longer listed."""
    info = names.get(model)
    if info and info.get("name"):
        return info["name"]
    provider, _, rest = model.partition("/")
    return f"{rest} ({provider})" if rest else model


# --- numbers and dates ------------------------------------------------------

def round_half_up(value, places=1):
    q = Decimal(1).scaleb(-places)
    return float(Decimal(str(value)).quantize(q, rounding=ROUND_HALF_UP))


def mean(values):
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def fmt_decimal(value, lang, places=1):
    text = f"{round_half_up(value, places):.{places}f}"
    return text.replace(".", ",") if lang == "it" else text


def fmt_percent(ratio):
    return f"{int(round_half_up(ratio * 100, 0))}%"


MONTHS = {
    "it": ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
           "settembre", "ottobre", "novembre", "dicembre"],
    "en": ["January", "February", "March", "April", "May", "June", "July", "August",
           "September", "October", "November", "December"],
}


def parse_time(text):
    """An ISO 8601 time; one written without a time zone is read as UTC."""
    at = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    return at if at.tzinfo else at.replace(tzinfo=dt.timezone.utc)


def fmt_date(value, lang):
    """A date as the report writes it; Italian writes the first of the month as 1°."""
    day = value if isinstance(value, dt.date) else parse_time(value) if "T" in value else dt.date.fromisoformat(value)
    number = "1°" if lang == "it" and day.day == 1 else str(day.day)
    return f"{number} {MONTHS[lang][day.month - 1]} {day.year}"


def span(start, end, lang):
    """The days from `start` to `end`, written short: 8–19 ottobre 2026."""
    a, b = parse_time(start).date(), parse_time(end).date()
    month = MONTHS[lang]

    def day(d):
        return "1°" if lang == "it" and d.day == 1 else str(d.day)
    if a == b:
        return fmt_date(a, lang)
    if (a.year, a.month) == (b.year, b.month):
        return f"{day(a)}–{day(b)} {month[b.month - 1]} {b.year}"
    if a.year == b.year:
        return f"{day(a)} {month[a.month - 1]} – {day(b)} {month[b.month - 1]} {b.year}"
    return f"{fmt_date(a, lang)} – {fmt_date(b, lang)}"


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
