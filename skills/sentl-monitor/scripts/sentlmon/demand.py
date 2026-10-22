"""Search demand: Google's suggestions for a theme's seeds, volumes from a keyword-data source,
keyword classes, and the lines the report's themes section prints.

The suggestion endpoint is the only network call the skill makes. Volumes are never fetched:
they come from a file the assistant saved from a keyword-data server, or from an export file.
"""

import csv
import datetime as dt
import json
import re
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from .common import MONTHS, Refused, Study, fmt_date, first_mention, folded, load_json, now_iso, write_json
from .i18n import TEXT, join, phrase

SEEDS_SCHEMA = "sentl-monitor/seeds@1"
DEMAND_SCHEMA = "sentl-monitor/search-demand@1"
ENDPOINT = "https://suggestqueries.google.com/complete/search"
TIMEOUT = 10
DELAY = 0.4
CLASSES = ("subject", "foil", "component", "generic")
TOP = 5

STEMS = {
    "it": ["è", "fa", "come", "perché", "quanto", "quale", "si può"],
    "en": ["is", "does", "how", "why", "can", "which", "vs"],
}

# Words that carry no topic: a related search sharing only these with its seed is off topic.
STOPWORDS = frozenset("""
    il lo la i gli le un uno una di a da in con su per tra fra e o ed che del dello della dei degli delle
    al allo alla ai agli alle nel nello nella nei negli nelle sul sulla d l s t è fa come perché quanto
    quale si può non ma se
    the an of to on for with and or is does how why can which vs you your it do what are be i my
""".split())

NO_VOLUME = ("The counts are Google suggestions: they measure how many ways a theme is phrased, "
             "not how many people search it.")


class Incomplete(Exception):
    """Some prefixes could not be fetched; exit code 1."""


# --- Google suggestions -------------------------------------------------------

def suggest_url(prefix, hl, gl):
    return ENDPOINT + "?" + urlencode({"client": "firefox", "q": prefix, "hl": hl, "gl": gl, "oe": "utf-8"})


def _get(url):
    request = urllib.request.Request(url, headers={"User-Agent": "sentl-monitor"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - https endpoint above
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset)


def parse_suggestions(text):
    """The suggestions in a response: `[prefix, [suggestion, ...], ...]`."""
    data = json.loads(text)
    if not (isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list)
            and all(isinstance(s, str) for s in data[1])):
        raise ValueError("not a list of suggestions")
    return data[1]


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _load_seeds(path):
    try:
        seeds = load_json(path)
    except (OSError, ValueError) as exc:
        raise Refused(f"{path} cannot be read as JSON ({exc}): write seeds.json first") from None
    if not isinstance(seeds, dict) or seeds.get("schema") != SEEDS_SCHEMA:
        raise Refused(f"{path} is not a seeds file: its schema must be {SEEDS_SCHEMA!r}")
    themes = seeds.get("themes")
    if not (isinstance(themes, dict) and themes and all(
            isinstance(v, list) and v and all(isinstance(s, str) and s.strip() for s in v) for v in themes.values())):
        raise Refused(f"{path}: themes must map each theme id to a non-empty list of seed queries")
    return seeds


def terms_of(seeds):
    """The words that class a keyword: the subject's aliases, the foils' aliases, the components' terms."""
    return {"subject": list((seeds.get("subject") or {}).get("aliases") or []),
            "foil": [a for f in seeds.get("foils") or [] for a in f.get("aliases") or []],
            "component": [t for c in seeds.get("components") or [] for t in c.get("terms") or []]}


def classify(keyword, terms):
    """subject, foil, component or generic; the first that applies, in that order."""
    text = folded(keyword)
    for cls in CLASSES[:3]:
        if first_mention(text, terms[cls]) is not None:
            return cls
    return "generic"


def _load_demand(root, seeds):
    path = Study(root).path("search-demand.json")
    if not path.exists():
        return {"schema": DEMAND_SCHEMA, "market": seeds.get("market"), "themes": {}, "volume_source": None}
    data = load_json(path)
    if data.get("schema") != DEMAND_SCHEMA:
        raise Refused(f"{path} has schema {data.get('schema')!r}, not {DEMAND_SCHEMA!r}")
    return data


def _theme(data, theme):
    return data["themes"].setdefault(theme, {"seeds": [], "autocomplete": [], "volumes": []})


def autocomplete(root, seeds_file, hl, gl, stems=None):
    seeds = _load_seeds(seeds_file)
    stems = stems if stems is not None else STEMS.get(hl)
    if not stems:
        raise Refused(f"no question stems for language {hl!r}: pass --stems with the question words of the "
                      f"language, separated by commas (built in: {', '.join(sorted(STEMS))})")
    data = _load_demand(root, {**seeds, "market": {"country": gl.upper(), "language": hl.lower()}})
    source = f"google autocomplete hl={hl} gl={gl}"
    today = now_iso()[:10]
    failed, fetched = [], 0
    for theme, theme_seeds in seeds["themes"].items():
        block = _theme(data, theme)
        block["seeds"] = list(theme_seeds)
        done = {e["prefix"] for e in block["autocomplete"] if e["source"] == source}
        for seed in theme_seeds:
            for prefix in [seed] + [f"{seed} {stem}" for stem in stems]:
                if prefix in done:
                    continue
                try:
                    suggestions = parse_suggestions(_get(suggest_url(prefix, hl, gl)))
                except (OSError, ValueError):
                    failed.append(prefix)
                else:
                    block["autocomplete"].append({"prefix": prefix, "suggestions": suggestions,
                                                  "source": source, "collected": today})
                    done.add(prefix)
                    fetched += 1
                if DELAY:
                    time.sleep(DELAY)
    write_json(Study(root).path("search-demand.json"), data)
    if failed:
        raise Incomplete(f"{_plural(len(failed), 'prefix', 'prefixes')} could not be fetched; the others are "
                         "recorded. Run the same command again to fetch these:\n"
                         + "\n".join(f"  - {p}" for p in failed))
    return f"Wrote search-demand.json: {_plural(fetched, 'prefix', 'prefixes')} fetched."


# --- volumes ------------------------------------------------------------------

def _tokens(text):
    return [w for w in re.findall(r"[a-z0-9]+", folded(text)) if w not in STOPWORDS]


def _volume(value, where):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise Refused(f"{where}: monthly_volume must be a whole number of searches, not {value!r}")
    return value


def _text(value, where):
    if not (isinstance(value, str) and value.strip()):
        raise Refused(f"{where} must be a non-empty text")
    return value.strip()


def merge_volumes(root, volumes_file, seeds_file):
    """Merge a saved keyword-data response into search-demand.json, and refuse the whole file when any
    part of it is not as expected."""
    seeds = _load_seeds(seeds_file)
    try:
        incoming = load_json(volumes_file)
    except (OSError, ValueError) as exc:
        raise Refused(f"{volumes_file} cannot be read as JSON ({exc})") from None
    if not isinstance(incoming, dict) or not isinstance(incoming.get("keywords"), list):
        raise Refused(f"{volumes_file} must hold provider, tool, collected and a list of keywords")
    provider, tool = (_text(incoming.get(k), f"{volumes_file}: {k}") for k in ("provider", "tool"))
    collected = _text(incoming.get("collected"), f"{volumes_file}: collected")
    try:
        dt.date.fromisoformat(collected)
    except ValueError:
        raise Refused(f"{volumes_file}: collected must be a date, YYYY-MM-DD, not {collected!r}") from None
    terms = terms_of(seeds)
    relevance = terms["subject"] + terms["foil"] + terms["component"]
    entries = []
    for n, item in enumerate(incoming["keywords"], 1):
        where = f"{volumes_file}, keyword {n}"
        theme = _text(item.get("theme") if isinstance(item, dict) else None, where + ": theme")
        if theme not in seeds["themes"]:
            raise Refused(f"{where}: theme {theme!r} is not in seeds.json; themes: " + ", ".join(seeds["themes"]))
        keyword = _text(item.get("keyword"), where + ": keyword")
        entry = {"keyword": keyword, "monthly_volume": _volume(item.get("monthly_volume"), where),
                 "class": classify(keyword, terms), "provider": provider, "tool": tool, "collected": collected}
        topic = relevance + _tokens(keyword)
        kept, dropped = [], 0
        for m, rel in enumerate(item.get("related") or [], 1):
            rwhere = f"{where}, related {m}"
            rkeyword = _text(rel.get("keyword") if isinstance(rel, dict) else None, rwhere + ": keyword")
            rvolume = _volume(rel.get("monthly_volume"), rwhere)
            if first_mention(folded(rkeyword), topic) is None:
                dropped += 1
            else:
                kept.append({"keyword": rkeyword, "monthly_volume": rvolume, "class": classify(rkeyword, terms)})
        entries.append((theme, {**entry, "related": kept, "related_dropped": dropped}))
    data = _load_demand(root, seeds)
    for theme, entry in entries:
        block = _theme(data, theme)
        block["volumes"] = [v for v in block["volumes"] if folded(v["keyword"]) != folded(entry["keyword"])]
        block["volumes"].append(entry)
    source = data.get("volume_source") or {"providers": [], "from": collected, "to": collected}
    data["volume_source"] = {"providers": sorted({*source["providers"], provider}),
                             "from": min(source["from"], collected), "to": max(source["to"], collected)}
    write_json(Study(root).path("search-demand.json"), data)
    dropped = sum(e["related_dropped"] for _, e in entries)
    return (f"Merged {_plural(len(entries), 'keyword', 'keywords')} from {provider} into search-demand.json; "
            f"{_plural(dropped, 'related search', 'related searches')} left out as off topic.")


KEYWORD_COLUMNS = ("keyword", "keywords", "query", "search term")
VOLUME_COLUMNS = ("volume", "search volume", "monthly volume", "monthly searches", "avg monthly searches",
                  "monthly search volume", "sv", "monthly_volume")
SEED_COLUMNS = ("related to", "seed", "seed keyword", "parent keyword")
THOUSANDS = re.compile(r"\d{1,3}(,\d{3})+")


def _header(name):
    return " ".join(re.split(r"[\s_-]+", (name or "").strip().lower()))


def _number(text, where):
    text = (text or "").strip()
    if THOUSANDS.fullmatch(text):
        text = text.replace(",", "")
    if not text.isdigit():
        raise Refused(f"{where}: the volume {text!r} is not a whole number")
    return int(text)


def import_export(root, file, seeds_file, provider=None, tool=None, theme=None, date=None):
    """Merge an export file of a keyword tool: a CSV with a keyword and a volume column, or a
    JSON file in the shape `volumes` reads."""
    path = Path(file)
    if path.suffix.lower() == ".json":
        try:
            data = load_json(path)
        except (OSError, ValueError) as exc:
            raise Refused(f"{path} cannot be read as JSON ({exc})") from None
        if not isinstance(data, dict):
            raise Refused(f"{path} must hold provider, tool, collected and a list of keywords")
        data = {**data, **{k: v for k, v in (("provider", provider), ("tool", tool), ("collected", date)) if v}}
    else:
        missing = [f"--{k}" for k, v in (("provider", provider), ("tool", tool), ("theme", theme)) if not v]
        if missing:
            raise Refused(f"a CSV export needs {', '.join(missing)}")
        try:
            text = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            raise Refused(f"{path} cannot be read as UTF-8 text ({exc})") from None
        delimiter = max(",;\t", key=text.split("\n", 1)[0].count)
        reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
        columns = {_header(c): c for c in reader.fieldnames or []}

        def column(names):
            return next((columns[n] for n in names if n in columns), None)
        key_col, vol_col, seed_col = column(KEYWORD_COLUMNS), column(VOLUME_COLUMNS), column(SEED_COLUMNS)
        if not (key_col and vol_col):
            raise Refused(f"{path} needs a keyword column and a volume column; its columns are: "
                          + ", ".join(columns))
        keywords, by_seed = [], {}
        for n, row in enumerate(reader, 2):
            where = f"{path}, line {n}"
            keyword, volume = (row[key_col] or "").strip(), _number(row[vol_col], where)
            seed = (row[seed_col] or "").strip() if seed_col else ""
            if seed:
                parent = by_seed.get(folded(seed))
                if parent is None:
                    raise Refused(f"{where}: the seed {seed!r} is not a keyword row above it")
                parent.setdefault("related", []).append({"keyword": keyword, "monthly_volume": volume})
            else:
                item = {"theme": theme, "keyword": keyword, "monthly_volume": volume}
                keywords.append(item)
                by_seed[folded(keyword)] = item
        data = {"provider": provider, "tool": tool, "collected": date or now_iso()[:10], "keywords": keywords}
    target = Study(root).path("volumes.json")
    write_json(target, data)
    return merge_volumes(root, target, seeds_file)


# --- summary ------------------------------------------------------------------

def summarize(data):
    """Per theme: distinct suggestions, prefixes, volume per class (None without volumes) and the top queries."""
    out = {}
    for theme, block in data["themes"].items():
        suggestions = {}
        for entry in block["autocomplete"]:
            for s in entry["suggestions"]:
                suggestions.setdefault(folded(s), s)
        keywords = {}
        for entry in block["volumes"]:
            for item in [entry, *entry.get("related", [])]:
                keywords.setdefault(folded(item["keyword"]), item)
        volume = None
        if keywords:
            volume = {}
            for item in keywords.values():
                volume[item["class"]] = volume.get(item["class"], 0) + item["monthly_volume"]
            volume = {c: volume[c] for c in CLASSES if c in volume}
        if keywords:
            top = [(i["keyword"], i["monthly_volume"])
                   for i in sorted(keywords.values(), key=lambda i: -i["monthly_volume"])[:TOP]]
        else:
            top = [(s, None) for s in list(suggestions.values())[:TOP]]
        out[theme] = {"suggestions": len(suggestions), "prefixes": len(block["autocomplete"]),
                      "volume": volume, "top": top}
    return out


def summary(root):
    path = Study(root).path("search-demand.json")
    if not path.exists():
        raise Refused(f"{path} not found: run demand autocomplete first")
    data = load_json(path)
    lines = []
    for theme, s in summarize(data).items():
        lines.append(f"{theme}: {_plural(s['suggestions'], 'distinct suggestion', 'distinct suggestions')} from "
                     f"{_plural(s['prefixes'], 'prefix', 'prefixes')}")
        volume = "; ".join(f"{c} {v}" for c, v in s["volume"].items()) if s["volume"] else "none"
        lines.append(f"  volume per month: {volume}")
        lines.append("  top queries: " + "; ".join(q if v is None else f"{q} ({v})" for q, v in s["top"]))
    source = data.get("volume_source")
    lines.append("")
    lines.append(NO_VOLUME if not source else
                 f"volume source: {', '.join(source['providers'])}, {source['from']} to {source['to']}")
    return "\n".join(lines)


# --- the report ---------------------------------------------------------------

def _number_text(n, lang):
    text = f"{n:,}"
    return text.replace(",", ".") if lang == "it" else text


def _month(date, lang):
    day = dt.date.fromisoformat(date)
    return f"{MONTHS[lang][day.month - 1]} {day.year}"


def report_lines(data, themes, lang):
    """The themes section's lines on search demand for `themes` (id, label pairs); empty when
    the search demand holds none of them."""
    t = TEXT[lang]
    lines = []
    for theme_id, label in themes:
        block = (data.get("themes") or {}).get(theme_id)
        if not block:
            continue
        s = summarize({"themes": {theme_id: block}})[theme_id]
        parts = []
        if block["autocomplete"]:
            latest = max(e["collected"] for e in block["autocomplete"])
            parts.append(t["demand_suggestions"][s["suggestions"] != 1].format(n=s["suggestions"])
                         + f" ({_month(latest, lang)}).")
        if s["volume"]:
            dates = sorted({e["collected"] for e in block["volumes"]})
            when = (fmt_date(dates[0], lang) if len(dates) == 1 else
                    phrase(lang, "span", start=fmt_date(dates[0], lang), end=fmt_date(dates[-1], lang)))
            classes = "; ".join(f"{_number_text(v, lang)} {t['volume_classes'][c]}" for c, v in s["volume"].items())
            providers = join(sorted({e["provider"] for e in block["volumes"]}), lang)
            parts.append(t["demand_monthly"].format(classes=classes, provider=providers, when=when))
        lines.append(f"- {label}: " + " ".join(parts))
    if not lines:
        return []
    out = [f"**{t['demand_title']}**", ""] + lines + [""]
    if not data.get("volume_source"):
        out += [t["no_volume"], ""]
    return out
