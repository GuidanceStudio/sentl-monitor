"""The insights that explain a figure (DEVPLAN M2b): which fact the answers state, the
sources most cited by the answers giving an outdated fact or a low score, how many distinct readings the rounds are,
episodes inside a period, answers that found no evidence, and who wrote the cited pages."""

import functools
import re
from collections import Counter
from urllib.parse import urlparse

from .common import REDIRECT_HOSTS, folded
from .i18n import MISSING_EVIDENCE, THIRD_PERSON

TOP_SOURCES = 5
EPISODE_EARLIER = 5
EPISODE_RUNS = 3
EPS = 1e-9


def fact_terms(question):
    """The current and outdated terms of a question's facts, or None when it has none."""
    terms = {"current": [], "outdated": []}
    for fact in question.get("facts") or []:
        for kind in terms:
            values = fact.get(kind) if isinstance(fact.get(kind), list) else []
            terms[kind] += [t for t in values if isinstance(t, str) and t.strip() and t not in terms[kind]]
    return terms if terms["current"] or terms["outdated"] else None


CURRENCY_SPACE = re.compile(r"(?<=\d)\s+(?=[€£$¥])|(?<=[€£$¥])\s+(?=\d)")


def tight(text):
    """Text with no space between a number and a currency sign, on either side."""
    return CURRENCY_SPACE.sub("", text)


@functools.lru_cache(maxsize=None)
def _as_terms(answer):
    return tight(folded(answer))


@functools.lru_cache(maxsize=None)
def _term(term):
    """A fact term matched on word boundaries and never inside a longer number: "10 €" is not
    stated by "12,10 €", nor "£2" by "£2.50"."""
    return re.compile(r"(?<!\w)(?<!\d[.,])" + re.escape(tight(folded(term))) + r"(?![.,]?\d)(?!\w)")


def classify(answer, terms):
    """`current_only`, `outdated_only` or `both`, by the terms the answer states (folded like
    aliases); None when it states neither."""
    if answer is None:
        return None
    text = _as_terms(answer)
    current = any(_term(t).search(text) for t in terms["current"])
    outdated = any(_term(t).search(text) for t in terms["outdated"])
    return {(True, False): "current_only", (False, True): "outdated_only", (True, True): "both"}.get((current, outdated))


def fact_cell(responses, terms):
    given = [r for r in responses if r["answer"] is not None]
    kinds = Counter(classify(r["answer"], terms) for r in given)
    stating = kinds["current_only"] + kinds["outdated_only"] + kinds["both"]
    return {"given": len(given), "stating": stating, "current_only": kinds["current_only"],
            "outdated_only": kinds["outdated_only"], "both": kinds["both"],
            "current_share": (kinds["current_only"] + kinds["both"]) / stating if stating else None}


def top_sources(group, opposite):
    """The five domains cited by most answers of a group, ties broken by domain name, each with
    its count and share in the group and in the opposite group. A share is out of the group's
    answers that cite a source; a group whose answers cite nothing gets no list. `group` and
    `opposite` are lists of the sets of domains each answer cites."""
    group, opposite = [found for found in group if found], [found for found in opposite if found]
    if not group:
        return []
    here = Counter(d for found in group for d in found)
    there = Counter(d for found in opposite for d in found)
    return [{"domain": d, "citing": n, "answers": len(group), "share": n / len(group),
             "other": {"citing": there[d], "answers": len(opposite),
                       "share": there[d] / len(opposite) if opposite else None}}
            for d, n in sorted(here.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_SOURCES]]


def page_of(source):
    """A cited page as host and path, without query or fragment. A grounding redirect's URL
    differs on every call, so its page is the domain its title names."""
    parts = urlparse(source.get("url") or "")
    host = (parts.hostname or "").lower()
    if host in REDIRECT_HOSTS:
        return source.get("domain") or host
    return host.removeprefix("www.") + parts.path.rstrip("/")


def readings(responses):
    """Answers given, counting as one reading the rounds of a question–model pair in one run
    that cite the same ordered list of pages; an answer citing nothing is a reading of its own."""
    given = [r for r in responses if r["answer"] is not None]
    lists = {(r["run"], r["question"], r["model"], tuple(page_of(s) for s in r["sources"]))
             for r in given if r["sources"]}
    return len(lists) + sum(1 for r in given if not r["sources"])


def episodes(earlier, current):
    """Runs of this period whose value lies outside the range of the runs before them (the
    previous period's `earlier` values and this period's runs so far, at least five), on
    the same side, three or more in a row. The range is the one before the first of them;
    the episode closes at the first value back inside it, or ends as a switch when the value
    jumps to the other side. `current` is [(date, value)]; runs without a value are skipped."""
    before = [v for v in earlier if v is not None]
    runs = [(d, v) for d, v in current if v is not None]
    found, i = [], 0
    while i < len(runs):
        seen = before + [v for _, v in runs[:i]]
        if len(seen) < EPISODE_EARLIER:
            i += 1
            continue
        lo, hi = min(seen), max(seen)

        def side(value):
            return "above" if value > hi + EPS else "below" if value < lo - EPS else None
        first = side(runs[i][1])
        j = i
        while first and j < len(runs) and side(runs[j][1]) == first:
            j += 1
        if j - i >= EPISODE_RUNS:
            after = side(runs[j][1]) if j < len(runs) else first
            found.append({"first": runs[i][0], "last": runs[j - 1][0], "runs": j - i,
                          "values": [v for _, v in runs[i:j]], "range": [lo, hi], "earlier": len(seen),
                          "side": first, "closed": runs[j][0] if after is None else None,
                          "switched": runs[j][0] if after not in (None, first) else None})
            i = j
        else:
            i += 1
    return found


def says_missing(answer, lang):
    """Whether the answer says the assistant found no source of the kind asked for, by the
    phrase list of the market's language (every list when it has none). A phrase in a
    sentence whose subject is a third party (users, customers) does not count."""
    if not answer:
        return False
    langs = [lang] if lang in MISSING_EVIDENCE else list(MISSING_EVIDENCE)
    text = folded(answer)
    for code in langs:
        for pattern in MISSING_EVIDENCE[code]:
            for m in re.finditer(pattern, text):
                sentence = text[text.rfind(".", 0, m.start()) + 1:m.start()]
                if not re.search(THIRD_PERSON[code], sentence):
                    return True
    return False


def reset():
    """Forget the folded answers of the previous period."""
    folded.cache_clear()
    _as_terms.cache_clear()
