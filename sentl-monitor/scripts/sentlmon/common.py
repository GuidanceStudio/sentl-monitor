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

FINAL = ("completed", "completed_with_warnings")
RUN_FLOOR = 0.90
FIGURE_FLOOR = 0.80


class Refused(Exception):
    """Input the command cannot act on; exit code 2."""


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


def load_mcp(path, key):
    """Read a saved MCP response and return the object under `key`.

    A host saves either the tool's JSON text or the MCP content list around it
    ([{"type": "text", "text": ...}]); both are accepted. A response that does
    not parse is refused, because a host that truncates output cuts it mid-string.
    """
    raw = Path(path).read_text(encoding="utf-8")
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

    def record_report(self, entry):
        entries = [e for e in self.reports() if e["date"] != entry["date"]] + [entry]
        write_json(self.path("history", "reports.json"), sorted(entries, key=lambda e: e["date"]))


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
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def fmt_date(value, lang):
    """A date as the report writes it; Italian writes the first of the month as 1°."""
    day = value if isinstance(value, dt.date) else parse_time(value) if "T" in value else dt.date.fromisoformat(value)
    number = "1°" if lang == "it" and day.day == 1 else str(day.day)
    return f"{number} {MONTHS[lang][day.month - 1]} {day.year}"


def now_iso():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
