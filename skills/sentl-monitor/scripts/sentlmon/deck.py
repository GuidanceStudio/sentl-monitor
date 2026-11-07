"""`deck`: one period as one short slide deck for the marketing manager of the company it is about.

The manager knows the market and the competitors, and has never seen the questions, the ratings or the project names.
So the deck says what it shows before any figure, sets each figure beside what it compares with, and writes every label
in the manager's words. The code places each question in a block by its type and draws every tile, chart and table from
the period; the writer fills only the text of `reports/<date>.deck.json`, which `check` reads against the period
(ARCHITECTURE.md §The deck). The page holds no script and no network reference, like the report's.
"""

import html
import json
import re
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from . import pdf as report_pdf
from . import theme as sentl_theme
from .charts import span
from .check import (COUNT, ELLIPSIS, OTHER_UNIT, _allowed, _figures, _pieces, _plain, _quoted_in, _ratio, _shown, _stops_matching, _unquote,
                    leaks)
from .common import REDIRECT_HOSTS, Refused, Study, fmt_date, is_owned, load_json, match_key, write_json, write_text
from .compare import STEPS, called
from .i18n import DECK, join
from .insights import classify, fact_terms, tight
from .insights import page_of as cited_page
from .method import measured
from .period import Reader, _answers_to, _authors, _runs_of

SCHEMA = "sentl-monitor/deck@2"
BLOCKS = ("reach", "description", "facts")
CLASSES = ("not_named", "named_by_name_only", "passed_over", "no_information", "named_with_warning", "wrong_fact",
           "confused", "holds")
TODO = "[[...]]"
MAX_ACTIONS, MAX_SLIDES, MAX_BLOCK_SLIDES, MAX_EXCERPTS, MAX_EXAMPLES, MAX_ROWS, MAX_WORDS = 5, 12, 3, 2, 2, 8, 40
# Figures a sentence holds before it stops being read, and how often the first slides may repeat one.
MAX_TITLE_FIGURES, MAX_READ_FIGURES, MAX_REPEATS = 2, 3, 2
# The list of questions: lines a column holds, and the characters of one line.
COLUMN_LINES, TIGHT_LINES, LINE_CHARS = 27, 31, 80
# The pages a facts row shows behind the old term, per kind of author, and what makes a page one of them: answers with the
# old term cite it this many times as often as those with today's, and at least this many answers do.
SITES_SHOWN = 3
PAGE_NAMES = 4
TELLING_RATIO = 4
TELLING_ANSWERS = 3
CLOSE_SHARE = 0.02
MIN_ANSWERS = 3
MIN_SITE_SHARE = 0.05
MIN_SITE_ANSWERS = 5
THIRD_PAGES = 12
# The characters each text may hold for its slide to stay on one page.
LIMITS = {"title": 125, "answer": 170, "read": 210, "what": 175, "why": 175, "read_next": 70, "limit": 170, "ask": 120,
          "who": 90, "question": 90}
UNSAID = re.compile(r"\b(giudic\w*|judge\w*|letture|readings?|instabil\w*|unstable|deck)\b", re.I)
CAUSED = re.compile(r"\b(grazie a\w*|per effetto|a causa d\w*|in seguito a\w*|thanks to|as a result of|because of|due to|caused by)\b", re.I)
SWEEPING = re.compile(r"\b(nessun[aoe]?|assent[ei]|tutt[ei]|mai|sempre|absent|none|never|always|no (?:answer|assistant)s?"
                      r"|rest\w+ fuori|fuori dalle risposte|left out|missing from"
                      r"|every (?:answer|assistant)|all (?:the |\d+ )?(?:answers|assistants))\b", re.I)
# "None of the 18 answers" and "all 9 answers": the count is said in words, and the figures bear it out or not.
NONE_OF = re.compile(r"\b(?:nessun[ao]? (?:delle|dei|degli) |none of the )(\d+)\b", re.I)
ALL_OF = re.compile(r"\b(?:tutt[ei] (?:le |i |gli )?|all (?:the )?)(\d+)\b", re.I)
# The chart's word is "neutre": a second word for the same answers reads as a second kind of answer.
BAND_WORD = re.compile(r"\bneutral[ie]\b", re.I)
# A topic as the subject of "favourable": the answers are favourable, and they say how many.
FAVOURABLE_IN = re.compile(r"\b(?:is|are|è|sono)\s+(?:favourable|favorevol[ei])\s+in\b", re.I)
# The deck is written about the subject by whoever prepared it: "we" there is the author, never the subject.
FIRST_PERSON = re.compile(r"(?i:\b(?:noi|nostr[aoei]|(?:nominar|citar|trovar|cercar|consigliar)ci|ci (?:nomin|cit|trov|consigli)\w*"
                          r"|we|our|ours)\b)|\bus\b")
# Asking to be listed: a site the answers already cite on questions about the subject probably lists it.
EDITED = re.compile(r"^\s*(?:aggiorn|aggiung|corregg|modific|updat|add\b|correct|edit\b|chang)", re.I)
ASK_TO_CHECK = re.compile(r"\b(?:chiedere a (?:\S+(?:,| e)\s+)*\S+ (?:di (?:verificare|controllare)|se)"
                          r"|ask (?:\S+(?:,| and)\s+)*\S+ (?:to (?:check|verify)|whether|if))\b", re.I)
LISTING = re.compile(r"\b(?:sched[ae]|listings?|listed|list it|elencat[aoie]|inser(?:it[aoie]|ire|irl[aoie]|imento))\b", re.I)
# A page's content the action dictates: after a colon, or after "say that".
ASSERTED = re.compile(r"(?::\s|\b(?:dicendo|dica|dire|spiegando|spieghi|spiegare|scrivendo|scrivere|say|says|saying|state|states|"
                      r"stating|explain|explains|explaining)\s+(?:che|that)\s)[^.;]*\b(?:sono|è|viene|vengono|are|is)\b", re.I)
# What the answers cannot show: they say what assistants reply, not what anyone makes of it.
SITE_RANK = re.compile(r"\b(?:super(?:a|ano)|sorpass\w*|davanti a|overtak\w*|outrank\w*|ahead of)\b", re.I)
MOST_CITED = re.compile(r"\b(?:il sito più citato|the most cited site|the site cited most)\b(?! (?:di terzi|esterno|among third))", re.I)
WHY_NOT = re.compile(r"\b(?:perch[eé]|poich[eé]|because|since|senza azione|nessuna azione|no action)\b", re.I)
DOUBT = re.compile(r"\b(?:non ho trovato|non trovo|non risulta|non (?:è|e') (?:chiaro|verificabile|possibile verificare)|non sono riuscit\w+|"
                   r"non posso (?:valutar|confermar|verificar|dir)\w*|non compare nei risultati|"
                   r"could(?: not|n't) find|did(?: not|n't) find|can(?:not|'t) (?:verify|assess|confirm)|not clear|unclear)\b", re.I)
AMOUNT = re.compile(r"(?<![\w.,])(?:[€£$]\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|£|\$|euro\b|eur\b|sterline\b|pounds?\b|dollari\b|dollars?\b))", re.I)
ACTION_NUMBER = re.compile(r"\b(?:azion[ei]|actions?) \d", re.I)
NAMING_FAVOURABLE = re.compile(r"(?:risposte che (?:l[ao] |\S+ )?nomin\w+|answers (?:that )?nam\w+)[^.;]*\b(?:favorevol|favourabl)", re.I)
CHECK_FIRST = re.compile(r"^\s*(?:verific|controll|check\b|verify\b)", re.I)
ADDS = re.compile(r"\b(?:includ\w*|aggiung\w*|inser\w*|add\b|list\b)", re.I)
ONE_ANSWER = re.compile(r"\b(?:un['’]altra|una(?: sola)? (?:risposta|descrive|dice|riporta|racconta|segnala|cita|avverte)|"
                        r"one (?:answer|describes|says|reports|warns))\b(?! (?:su|in|of|out of) (?:\d|due|tre|quattro|cinque|dieci|two|three|four|five|ten))", re.I)
ASKER_JUDGES = re.compile(r"\b(?:giudizio|opinione|parere) di chi\b|\b(?:verdict|opinion|view) of (?:those|people|anyone|whoever)\b", re.I)
REACTION = re.compile(r"\b(convinc\w*|conquist\w*|persuad\w*|win\w* over|won over)\b", re.I)
# Verbs that name no work: an action says what to write, and where.
VAGUE = re.compile(r"\b(rendere|rafforzare|presidiare|ottimizzare|valorizzare|potenziare|migliorare|strengthen|optimi[sz]e"
                   r"|leverage|improve|enhance)\b", re.I)
OVERSTATED = re.compile(r"\b(corrett[aeio]|correct|accurat[aeio]?|esatt[aeio])\b", re.I)
# Words of the people who build the study, which the reader does not have.
JARGON = re.compile(r"\b(blocc[oh]i?|blocks?|dimension[ei]|dimensions?|punteggi[oa]?|scor(?:e|es|ed|ing)|fasci[ae]|bands?"
                    r"|domande di categoria|category questions?|dat[oi] corrent[ei]|dat[oi] superat[oi]|current facts?"
                    r"|outdated facts?|rubric\w*)\b", re.I)
# A topic made the subject of a sentence: "the platform names it in 0 answers" says nothing a reader can picture.
THEME_VERB = (r"\s+(?:l[aoei]\s+(?:nomin|cit|menzion)\w*|è a\b|sono a\b|sta a\b|stanno a\b|reach\w*|sits? at\b|is at\b|are at\b"
              r"|names? \w+|mentions? \w+)")
# Words that read a figure as low: wrong of a subject among the first of the names monitored.
PLAYED_DOWN = re.compile(r"\b(solo|soltanto|appena|poco|poche|pochi|debole|scars[ao]|only|just|barely|few|weak|low)\b", re.I)
# A count stands beside what it counts when it is said to cite: "X è citato in 9 delle 12", "19 citano X", "X (39)".
CITING = re.compile(r"\b(?:citat[aoie]|cit(?:a|ano)|cited|cites?|citing)\b", re.I)
BARE_COUNT = re.compile(r"(?<![\w.,/-])(\d+)(?=\s+(?:rispost[ae]\b|answers?\b|citazion[ei]\b|citations?\b|cit(?:a|ano)\b|cites?\b))"
                        r"|\b(?:citat[aoie]|cited)\s+(?:da|in|by|on|su)\s+(\d+)\b|\((\d+)\)", re.I)
CUE_REACH = 12
PAGE_WORD = re.compile(r"\b(?:pagin[ae]|sched[ae]|guid[ae]|list[ae]|articol[oi]|pages?|sheets?|guides?|lists?|articles?)\b", re.I)
RIVAL_VERB = r"(?:(?:è|sono|viene|vengono|is|are|appears?|compare|compaiono|nominat\w+|menzionat\w+|named|mentioned)\s+){0,3}"
BARE_RIVAL = re.compile(r"\d{1,3}(?!\d)")
# After a competitor's bare count, a word that keeps it a count: "in 12 e Finom in 11", never "in 3 paesi".
AFTER_BARE = re.compile(r"\s*(?:[,;.)]|$)|\s+(?:rispost[ae]|answers?|e|ed|and|mentre|while|sul\w*|on)\b", re.I)
SITE_SUFFIX = {"co", "com", "org", "net", "ac", "gov"}
MOST = re.compile(r"\b(?:soprattutto|più citat[aoie]|cited most|most[- ]cited|mainly|above all)\b", re.I)
THIRD_WORD = re.compile(r"\b(?:terz[ie]|estern[aoie]|altri siti|third|external|other sites)\b", re.I)
PAGE = re.compile(r"(?<![\w@/.-])(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,}/[\w%~+-][\w%~+./-]*)", re.I)
DOMAIN = re.compile(r"(?<![\w@/.-])(?:https?://)?(?:www\.)?((?:[a-z0-9-]+\.)+[a-z]{2,})(?![\w-])", re.I)
SENTENCE = re.compile(r"(?<=[.!?;])\s+")
SENTENCE_START = re.compile(r"(?:^|[.!?:;]|(?:^|\s)(?:[-•]|\d+[.)]))\s*$")
SENTENCE_END = re.compile(r"[.!?:;…]$")
# The printers a deck takes: the page lays its slides out with flex and grid, which wkhtmltopdf does not read.
ENGINES = tuple(e for e in report_pdf.ENGINES if e[0] not in ("weasyprint", "wkhtmltopdf"))
ENGINES += tuple(e for e in report_pdf.ENGINES if e[0] == "weasyprint")

STYLE = """
:root { --sl-good: #2F6F8F; --sl-mid: #C4C9D1; --sl-bad: #B8453A; --sl-rival: #8B95A5; }
@page { size: 13.333in 7.5in; margin: 0; }
html, body { margin: 0; padding: 0; background: #fff; }
body { font: 20px/1.4 var(--sl-font); color: var(--sl-text); -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.slide { box-sizing: border-box; width: 100%; min-height: calc(7.5in - 1px); padding: 32px 56px 20px; display: flex;
  flex-direction: column; gap: 14px; break-after: page; }
.slide:last-of-type { break-after: auto; }
h1 { font-size: 30px; line-height: 1.2; color: var(--sl-deep); margin: 0; font-weight: 700; }
.kicker { font-size: 15px; line-height: 1.2; font-weight: 600; color: var(--sl-muted); margin-bottom: -8px; }
.read { margin: 0; font-size: 19px; line-height: 1.35; }
.foot { margin-top: auto; padding-top: 8px; display: flex; justify-content: space-between; align-items: center;
  font-size: 13px; color: var(--sl-muted); border-top: 1px solid var(--sl-line); }
.foot img { height: 16px; vertical-align: -3px; margin-right: 6px; }
.cover { padding: 0; flex-direction: row; gap: 0; }
.band { width: 34px; background: var(--sl-primary); }
.cover-body { flex: 1; padding: 56px 72px; display: flex; flex-direction: column; justify-content: center; gap: 20px; }
.cover-body img { height: 54px; width: auto; align-self: flex-start; margin-bottom: 18px; }
.cover h1 { font-size: 54px; line-height: 1.12; }
.cover-what { font-size: 27px; line-height: 1.32; color: var(--sl-text); max-width: 1020px; }
.cover-kind { font-size: 21px; color: var(--sl-text); font-weight: 600; margin-top: 10px; }
.cover-line { font-size: 19px; color: var(--sl-muted); }
.cards { display: flex; gap: 16px; flex: 1; align-items: stretch; }
.card { flex: 1 1 0; min-width: 0; box-sizing: border-box; background: var(--sl-tint); border-radius: 10px; padding: 15px 18px;
  display: flex; flex-direction: column; gap: 9px; }
.card.reach { flex-grow: 1.3; }
.card-q { font-size: 20px; line-height: 1.24; font-weight: 700; color: var(--sl-deep); }
.found .card-q { font-size: 16px; line-height: 1.25; font-weight: 600; }
.opening .cards { flex: 0 1 auto; }
.opening .reading { margin-top: auto; }
.three .card-q { font-size: 18px; }
.three .card-ex { font-size: 16px; gap: 7px; }
.card-count { font-size: 15px; color: var(--sl-muted); font-weight: 600; }
.card-ex { margin: 0; padding: 0; list-style: none; display: flex; flex-direction: column; gap: 10px; font-size: 18px; line-height: 1.3; }
.card-fig { font-size: 46px; line-height: 1.05; font-weight: 700; }
.card-fig small { font-size: 23px; font-weight: 600; color: var(--sl-muted); }
.card-fig span { font-size: 15px; font-weight: 400; color: var(--sl-muted); }
.card-cap { font-size: 15px; line-height: 1.28; color: var(--sl-muted); }
.card-a { margin: 0; font-size: 19.5px; line-height: 1.28; font-weight: 600; }
.card-visual { margin-top: auto; display: flex; flex-direction: column; gap: 8px; }
.card .bar { height: 22px; }
.card .legend { gap: 12px; font-size: 13px; flex-wrap: wrap; }
.versus { display: grid; grid-template-columns: auto 1fr 30px; gap: 6px 9px; align-items: center; font-size: 16px; line-height: 1.15; }
.versus .meter { height: 17px; background: #fff; }
.versus .fig { text-align: right; font-weight: 600; }
.versus .me { font-weight: 700; }
.pair .card-q { font-size: 18px; }
.pair .card-a { font-size: 25px; line-height: 1.3; }
.pair .card-cap { font-size: 16px; }
.pair .card-fig { font-size: 64px; }
.pair .card-fig small { font-size: 30px; }
.pair .versus { font-size: 19px; gap: 12px 10px; grid-template-columns: auto 1fr 36px; }
.pair .versus .meter { height: 24px; }
.reading { background: #F6F7F9; border-radius: 10px; padding: 11px 18px; }
.reading h2 { margin-bottom: 5px; font-size: 16px; }
.reading ul { margin: 0; padding: 0 0 0 18px; columns: 2; column-gap: 30px; font-size: 16px; line-height: 1.3; }
.reading li { margin-bottom: 4px; break-inside: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 16px; line-height: 1.3; }
th { text-align: left; font-size: 14px; background: var(--sl-tint); color: var(--sl-deep); padding: 8px 10px; }
td { padding: 9px 10px; border-bottom: 1px solid var(--sl-line); vertical-align: top; }
td.num { font-weight: 700; text-align: center; }
td.class { font-weight: 700; }
.actions table { table-layout: fixed; flex: 1; }
.earlier table { table-layout: fixed; }
.actions th:nth-child(1), .actions th:nth-child(4) { width: 52px; }
.actions th:nth-child(2) { width: 43%; }
.actions td { font-size: 17px; padding: 9px 10px; }
.few-actions td { font-size: 19px; padding: 14px 10px; }
.many-actions td { font-size: 15.5px; padding: 5px 10px; line-height: 1.25; }
.note { margin: 0; font-size: 15.5px; color: var(--sl-muted); }
.site-why { font-size: .9em; color: var(--sl-muted); }
.sources table { font-size: 17px; }
.sources th { font-size: 14.5px; }
.sources td { padding: 18px 10px; }
.method table { font-size: 16px; }
.sources .small-meter { height: 12px; }
.chart { display: flex; flex-direction: column; gap: 8px; margin-top: 6px; }
.legend { display: flex; gap: 22px; font-size: 14px; color: var(--sl-muted); }
.legend i { display: inline-block; width: 13px; height: 13px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.rows { display: grid; column-gap: 18px; row-gap: 9px; align-items: center; font-size: 17px; line-height: 1.25; }
.reach-rows { grid-template-columns: 290px 1fr 84px 340px; }
.description-rows { grid-template-columns: 370px 1fr 92px 70px 92px; }
.facts-rows { grid-template-columns: 340px 1fr 92px 84px 84px 92px; }
.rows small { display: block; font-size: 13px; line-height: 1.25; color: var(--sl-muted); }
.long { font-size: 15px; }
.head { font-size: 14px; line-height: 1.2; font-weight: 600; color: var(--sl-muted); }
.head i { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 5px; }
.group { grid-column: 1 / -1; font-size: 15px; font-weight: 700; color: var(--sl-deep); margin-top: 4px; }
.fig { font-weight: 700; white-space: nowrap; }
.foils { font-size: 15px; color: var(--sl-muted); }
.bar { display: flex; gap: 2px; height: 28px; }
.few .bar, .few .meter { height: 40px; }
.dense { row-gap: 5px; font-size: 16px; }
.dense .bar, .dense .meter { height: 22px; }
.seg { display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; overflow: hidden; min-width: 0; }
.seg:first-child { border-radius: 4px 0 0 4px; }
.seg:last-child { border-radius: 0 4px 4px 0; }
.seg:only-child { border-radius: 4px; }
.good { background: var(--sl-good); color: #fff; }
.mid { background: var(--sl-mid); color: var(--sl-text); }
.low { background: var(--sl-bad); color: #fff; }
.meter { height: 28px; background: var(--sl-line); border-radius: 4px; overflow: hidden; }
.meter span { display: block; height: 100%; background: var(--sl-primary); border-radius: 0 4px 4px 0; }
.meter span.rival { background: var(--sl-rival); }
.small-meter { height: 10px; margin-top: 5px; }
.quotes { display: flex; gap: 20px; }
.quote { flex: 1; margin: 0; padding: 2px 0 2px 14px; border-left: 3px solid var(--sl-primary); }
.quote blockquote { margin: 0 0 5px; font-size: 16px; line-height: 1.3; }
.quote figcaption { font-size: 13px; line-height: 1.3; color: var(--sl-muted); }
.strip { background: var(--sl-tint); border-radius: 8px; padding: 9px 14px; font-size: 16.5px; line-height: 1.3; }
.strip b { color: var(--sl-deep); }
.method-cols { display: flex; gap: 28px; flex: 1; }
.method-cols > div { flex: 1; }
h2 { font-size: 18px; color: var(--sl-deep); margin: 0 0 4px; }
.method-cols p, .method-cols ul { font-size: 16px; line-height: 1.32; margin: 0 0 12px; }
.method-cols ul { padding-left: 18px; }
.question-cols { display: flex; gap: 30px; flex: 1; }
.question-cols > div { flex: 1 1 0; min-width: 0; font-size: 14.5px; line-height: 1.28; }
.tight > div { font-size: 13px; line-height: 1.22; }
.q-group { font-size: 16px; font-weight: 700; color: var(--sl-deep); margin: 7px 0 2px; }
.q-theme { font-weight: 700; margin: 5px 0 1px; }
.q-line { margin: 0 0 2px; }
"""


def esc(value):
    return html.escape(str(value), quote=False)


# --- the blocks -------------------------------------------------------------

def _short(name, subject):
    """A project's name with the subject it opens on taken off: the deck is about the subject already."""
    return re.sub(rf"^{re.escape(subject)}\s*[·:–-]\s*", "", name)


def _block(study, reader, text):
    """The block a question belongs to. A question naming no subject measures whether the subject is found; a category
    or a method has no presence to measure. A question with recorded facts stays in its block and shows in `facts` as
    well: its answers still say something of the subject, and a topic's figure that left them out would flatter it."""
    kind = (study.get("subject") or {}).get("kind")
    return "reach" if not reader.position(text) and kind not in ("category", "method") else "description"


def _later_record(study, question):
    """The fact another project records later for this question, with other current terms: the earlier
    record no longer says what is current, whatever the period's answers were read against."""
    mine = fact_terms(question)
    if not mine:
        return None
    dated = max(f.get("date") or "" for f in question["facts"])
    text = match_key(question["text"])
    for project in study["projects"]:
        for d in project["dimensions"]:
            for q in d["questions"]:
                terms = fact_terms(q)
                if terms and match_key(q["text"]) == text and set(terms["current"]) != set(mine["current"]):
                    later = [f for f in q["facts"] if (f.get("date") or "") > dated]
                    if later:
                        return later[-1]
    return None


def _rivals(items, reader):
    """The answers naming each competitor, left out where the question itself names it: an assistant repeating a name
    it was given says nothing of who it finds."""
    counts, left_out = Counter(), False
    for question, scope in items:
        named = set(reader.foils_named(question["text"]))
        left_out = left_out or any(k in named for k in scope["total"]["foils"])
        counts.update({k: n for k, n in scope["total"]["foils"].items() if k not in named})
    return counts, left_out


def _row(project, dimension, label, items, reader):
    cells = [scope["total"] for _, scope in items]
    rivals, left_out = _rivals(items, reader)
    return {"project": project, "dimension": dimension, "label": label, "judged": sum(c["judged"] for c in cells),
            "named": sum(c["presence"]["named"] for c in cells), "given": sum(c["presence"]["given"] for c in cells),
            "bands": {k: sum(c["bands"][k] for c in cells) for k in ("1-2", "3", "4-5")},
            "foils": sorted(rivals.items(), key=lambda kv: (-kv[1], kv[0]))[:3], "rivals": rivals, "left_out": left_out}


def _fact_name(question):
    """What a fact says to the reader: the fact, with the current terms its words do not hold, each once."""
    parts = []
    for fact in question.get("facts") or []:
        text, seen, terms = fact.get("fact", "").rstrip(". "), set(), []
        for term in fact.get("current") or []:
            same = re.sub(r"\D", "", term) or match_key(term)
            if same not in seen and tight(match_key(term)) not in tight(match_key(text)):
                terms.append(term)
            seen.add(same)
        parts.append(text + (": " + ", ".join(terms) if terms else ""))
    return "; ".join(parts)


def _sites_by_term(question, responses):
    """The pages cited by the answers carrying the old term, and by those carrying today's. A page, because a site usually
    feeds both kinds of answer: only a page says where the old term comes from."""
    terms, sites = fact_terms(question), {"old": Counter(), "new": Counter()}
    for r in responses:
        kind = classify(r["answer"], terms)
        if kind:
            sites["old" if kind == "outdated_only" else "new"].update(filter(None, map(cited_page, r["sources"])))
    return sites


def _telling(row, author):
    """The pages the answers with the old term cite and those with today's hardly ever do, by who wrote them."""
    old, new = row["sites"]["old"], row["sites"]["new"]
    found = {"owned": [], "third": [], "foil": []}
    for page, n in sorted(old.items(), key=lambda kv: (-kv[1], kv[0])):
        share, against = n / max(row["outdated"], 1), new.get(page, 0) / max(row["current"], 1)
        if n >= TELLING_ANSWERS and share >= TELLING_RATIO * against:
            kind = author(page.split("/")[0])
            found[kind if kind in found else "foil"].append((page, n))
    return found


def _pages_shown(row):
    return [p for pages in (row.get("telling") or {}).values() for p in pages[:SITES_SHOWN]]


def _fact_row(project, dimension, question, scope, responses=()):
    c = scope["facts"]["total"]
    total = scope["total"]
    last = (question.get("facts") or [{}])[-1]
    return {"project": project, "dimension": dimension, "key": question["key"], "label": question["text"],
            "fact": _fact_name(question), "source": last.get("source"), "date": last.get("date"), "given": c["given"],
            "current": c["current_only"] + c["both"], "both": c["both"], "outdated": c["outdated_only"], "silent": c["given"] - c["stating"],
            "judged": total["judged"], "bands": dict(total["bands"]), "sites": _sites_by_term(question, responses)}


def _by_fact(questions, same_audience):
    """One row per fact: the reader asks whether a fact is carried, whichever question brought it out."""
    rows = {}
    for q in questions:
        key = (None if same_audience else q["project"], q["fact"])
        row = rows.setdefault(key, {"project": q["project"], "dimension": q["dimension"], "dimensions": [], "label": q["fact"],
                                    "source": q["source"], "date": q["date"], "given": 0, "current": 0, "both": 0, "outdated": 0,
                                    "silent": 0, "judged": 0, "bands": {"1-2": 0, "3": 0, "4-5": 0}, "asked": 0,
                                    "sites": {"old": Counter(), "new": Counter()}})
        row["asked"] += 1
        for kind in row["sites"]:
            row["sites"][kind].update(q["sites"][kind])
        row["dimensions"] += [] if q["dimension"] in row["dimensions"] else [q["dimension"]]
        for k in ("given", "current", "both", "outdated", "silent", "judged"):
            row[k] += q[k]
        for k in row["bands"]:
            row["bands"][k] += q["bands"][k]
    return list(rows.values())


def _dimensions(row):
    return row.get("dimensions") or [row["dimension"]]


def _measure(key, row):
    return {"reach": (row.get("named"), row.get("given")), "facts": (row.get("current"), row.get("given")),
            "description": ((row.get("bands") or {}).get("4-5"), row.get("judged"))}[key]


def _parts(key, rows):
    """The parts of a block's figure as its bar draws them."""
    if key == "facts":
        return [(sum(r["current"] for r in rows), "good"), (sum(r["outdated"] for r in rows), "low"),
                (sum(r["silent"] for r in rows), "mid")]
    return [(sum(r["bands"][band] for r in rows), kind) for band, kind in (("4-5", "good"), ("3", "mid"), ("1-2", "low"))]


def _block_figures(key, rows, same_audience, names=0):
    """The figure of a block, one per project: a count across audiences says nothing, so the projects are added up only
    when the deck says they address the same audience and market. Presence carries what it compares with: the answers
    naming each competitor, and the subject's place among the `names` monitored."""
    groups = {}
    for row in rows:
        groups.setdefault(None if same_audience else row["project"], []).append(row)
    out = []
    for project, members in groups.items():
        a, b = (sum(_measure(key, r)[i] for r in members) for i in (0, 1))
        rivals = Counter()
        for r in members:
            rivals.update(r.get("rivals") or {})
        ranked = sorted(rivals.items(), key=lambda kv: (-kv[1], kv[0]))
        out.append({"project": project, "a": a, "b": b, "rivals": ranked, "rank": 1 + sum(n > a for _, n in ranked),
                    "names": names, "left_out": any(r.get("left_out") for r in members),
                    "parts": [] if key == "reach" else _parts(key, members)})
    return out


def _sources(responses, reader):
    out = _authors(responses, reader)
    domains = Counter(d for r in responses for d in {s["domain"] for s in r["sources"] if s["domain"]})
    naming = Counter(d for r in responses if reader.position(r["answer"]) is not None
                     for d in {s["domain"] for s in r["sources"] if s["domain"]})
    ranked = [{"domain": d, "answers": n, "author": reader.author(d), "naming": naming[d]}
              for d, n in sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))]
    pages = Counter(p for r in responses for p in {cited_page(s) for s in r["sources"] if reader.author(s["domain"]) == "owned"})
    others = Counter(p for r in responses for p in {cited_page(s) for s in r["sources"] if reader.author(s["domain"]) == "third"}
                     if "/" in p)
    return {**out, "answers": sum(r["answer"] is not None for r in responses), "domains": ranked[:5],
            "third_pages": sorted(others.items(), key=lambda kv: (-kv[1], kv[0]))[:THIRD_PAGES],
            "third_domains": [d for d in ranked if d["author"] == "third"][:5],
            "third_all": {d["domain"]: d["answers"] for d in ranked if d["author"] == "third"},
            "third_naming": {d["domain"]: d["naming"] for d in ranked if d["author"] == "third"},
            "owned_pages": sorted(pages.items(), key=lambda kv: (-kv[1], kv[0]))[:4],
            "foil_domains": [d for d in ranked if d["author"] not in ("owned", "third")][:5]}


def _assistant(model, names):
    return (names.get(model) or model).split(": ", 1)[-1]


def _makers(models, names):
    """The assistants by who makes them, as the reader knows them: Anthropic (Claude Haiku 5.5), Perplexity (Sonar)."""
    makers = {}
    for model in models:
        maker, _, name = (names.get(model) or model).rpartition(": ")
        if name not in makers.setdefault(maker, []):
            makers[maker].append(name)
    return ", ".join(f"{maker} ({', '.join(shown)})" if maker else ", ".join(shown) for maker, shown in sorted(makers.items()))


def _earlier(folder, date):
    """(date, text) of the latest deck before `date` that passed check and still has its period."""
    days = {e["date"] for e in folder.reports() if e.get("status") == "final" and e["date"] < date}
    for day in sorted(days, reverse=True):
        path = folder.path("reports", f"{day}.deck.json")
        if path.is_file() and folder.path("history", "periods", f"{day}.json").is_file():
            text = path.read_text(encoding="utf-8")
            if TODO not in text:
                return day, json.loads(text)
    return None


def _counted(study, period, doc):
    """{(block, question): (project, assistants, figure, base)}, from the period alone: a pack without --full leaves out
    the runs of the periods before the latest report."""
    moved, reader, out = doc.get("moved") or {}, Reader(study), {}
    for proj, dims in measured(study, period):
        part = period["projects"][proj["key"]]
        asked = sorted(((period.get("settings") or {}).get(proj["key"]) or {}).get("models") or part["by_model"])
        name = _short(proj["name"], study["subject"]["label"])
        for d in dims:
            for q in d["questions"]:
                scope = part["dimensions"][d["key"]]["questions"][q["key"]]
                block = moved.get(q["key"]) or _block(study, reader, q["text"])
                out[block, q["key"]] = (name, asked, *_measure(block, {**scope["total"], **scope["total"]["presence"]}))
                facts = None if _later_record(study, q) else scope.get("facts")
                if facts and (block == "description" or facts["total"]["stating"]):
                    c = facts["total"]
                    out["facts", q["key"]] = (name, asked, c["current_only"] + c["both"], c["given"])
    return out


def _change(then, now):
    """"up", "down" or None, by the step of a rate with a single previous period."""
    rate, before = now[0] / now[1], then[0] / then[1]
    return ("up" if rate > before else "down") if called(rate, [before], "presence") else None


def _second(folder, study, period, doc):
    """The deck before this one: its date, each block's figure on both dates, its actions. None for a first edition."""
    found = _earlier(folder, period["date"])
    if not found:
        return None
    day, earlier = found
    then, now, sums = _counted(study, load_json(folder.path("history", "periods", f"{day}.json")), earlier), _counted(study, period, doc), {}
    for key in now.keys() & then.keys():
        if now[key][1] == then[key][1]:
            group = sums.setdefault((key[0], None if doc.get("same_audience") else now[key][0]), [0, 0, 0, 0])
            for i, n in enumerate((*then[key][2:], *now[key][2:])):
                group[i] += n
    rows = [{"block": block, "project": project, "before": (a, b), "now": (c, d), "change": _change((a, b), (c, d))}
            for (block, project), (a, b, c, d) in sorted(sums.items(), key=lambda kv: (BLOCKS.index(kv[0][0]), kv[0][1] or ""))
            if b and d]
    return {"date": day, "rows": rows, "actions": [{"what": a["what"], "then": a["read_next"]} for a in earlier["actions"]]}


def build_model(folder, study, period, doc=None):
    """What the deck draws, from the period: each block's rows, figures and sources, the method table."""
    doc = doc or {}
    moved = doc.get("moved") or {}
    reader, subject = Reader(study), study["subject"]["label"]
    names = period.get("names") or {}
    narrative = study.get("narrative") or {}
    blocks = {b: {"rows": [], "questions": [], "placed": [], "responses": []} for b in BLOCKS}
    answers_of = {}
    method, cache, replaced, models, counted = [], {}, [], [], {}

    def run_of(key, run_id):
        if (key, run_id) not in cache:
            cache[(key, run_id)] = folder.run(key, run_id)
        return cache[(key, run_id)]

    for proj, dims in measured(study, period):
        key, part = proj["key"], period["projects"][proj["key"]]
        runs, name = _runs_of(period, key, run_of), _short(proj["name"], subject)
        for d in dims:
            entry = part["dimensions"][d["key"]]
            here = {b: [] for b in BLOCKS}
            for q in d["questions"]:
                scope = entry["questions"][q["key"]]
                if "foils" not in scope["total"]:
                    raise Refused(f"the period of {period['date']} was built before the deck's figures: "
                                  f"run period --date {period['date']} again")
                later = _later_record(study, q)
                facts = None if later else scope.get("facts")
                if later:
                    replaced.append({"question": q["text"], "fact": q["facts"][-1]["fact"], "date": q["facts"][-1].get("date"),
                                     "later": later["fact"], "later_date": later.get("date"),
                                     "terms": fact_terms(q)["current"]})
                block = moved.get(q["key"]) or _block(study, reader, q["text"])
                here[block].append((q, scope))
                blocks[block]["placed"].append({"key": q["key"], "text": q["text"], "dimension": d["name"],
                                                "names_subject": bool(reader.position(q["text"]))})
                # One base everywhere the reader can add up: an answer counts in a block as its block's figure counts it.
                reach = block == "reach"
                counted[q["key"]] = scope["total"]["presence"]["given"] if reach else scope["total"]["judged"]
                answers_of[q["key"]] = _answers_to(runs, q["key"])
                blocks[block]["responses"] += [r for r in answers_of[q["key"]] if reach or r["score"] is not None]
                if facts and (block == "description" or facts["total"]["stating"]):
                    blocks["facts"]["questions"].append(_fact_row(name, d["name"], q, scope, _answers_to(runs, q["key"])))
            for b in ("reach", "description"):
                if here[b]:
                    blocks[b]["rows"].append(_row(name, d["name"], d["name"], here[b], reader))
                    blocks[b]["questions"] += [{**_row(name, d["name"], q["text"], [(q, s)], reader), "key": q["key"]}
                                               for q, s in here[b]]
        settings = (period.get("settings") or {}).get(key) or {}
        asked = settings.get("models") or list(part["by_model"])
        models += asked
        method.append({"name": name, "questions": sum(len(d["questions"]) for d in dims),
                       "assistants": [_assistant(m, names) for m in asked],
                       "answers": sum(counted[q["key"]] for d in dims for q in d["questions"]),
                       "schedule": settings.get("schedule")})
    blocks["facts"]["rows"] = _by_fact(blocks["facts"]["questions"], doc.get("same_audience"))
    for row in blocks["facts"]["rows"]:
        row["telling"] = _telling(row, reader.author)
    for key, block in blocks.items():
        block["figures"] = _block_figures(key, block["rows"], doc.get("same_audience"), len(study.get("foils") or []) + 1)
        block["sources"] = _sources(block["responses"], reader)
    assistants = {a for row in method for a in row["assistants"]}
    given = Counter(counted.values())
    asked = {d["key"] for _, dims in measured(study, period) for d in dims}
    origins = {o["kind"] for t in study.get("themes") or [] if t.get("dimension") in asked for o in t.get("origins") or []}
    return {"blocks": blocks, "method": method, "subject": subject, "replaced": replaced, "names": names,
            "answers_of": answers_of, "author": reader.author,
            "makers": _makers(models, names), "spread": sorted(given.items(), key=lambda kv: (-kv[1], -kv[0])),
            "purpose": narrative.get("purpose"), "origins": origins,
            "monitored": [f["label"] for f in study.get("foils") or []],
            "repeated": any(r["answers"] > r["questions"] * len(r["assistants"]) for r in method),
            "by": (narrative.get("criteria") or {}).get("by"), "first": not (period.get("comparison") or {}).get("previous"),
            "fidelity": narrative.get("score_axis") == "fidelity", "second": _second(folder, study, period, doc),
            "totals": {"questions": sum(r["questions"] for r in method), "assistants": len(assistants),
                       "answers": sum(r["answers"] for r in method)}}


def present(m):
    return [b for b in BLOCKS if m["blocks"][b]["rows"]]


# --- what the writer fills --------------------------------------------------

def _latest(folder):
    days = sorted(p.stem for p in folder.path("history", "periods").glob("*.json")
                  if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem) and not load_json(p).get("rebuilt"))
    if not days:
        raise Refused("no period yet: run period first")
    return days[-1]


def load(root, date=None):
    """(folder, date, study, period, the deck's text or None)."""
    folder = Study(root)
    study = folder.study
    date = date or _latest(folder)
    path = folder.path("history", "periods", f"{date}.json")
    if not path.exists():
        raise Refused(f"no period for {date}: run period --date {date} first")
    period = load_json(path)
    folder.require_runs([period], date)
    doc_path = folder.path("reports", f"{date}.deck.json")
    if not doc_path.exists():
        return folder, date, study, period, None
    try:
        return folder, date, study, period, json.loads(doc_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise Refused(f"{doc_path} is not valid JSON ({exc})") from None


def _earlier_fields(second):
    fields = {"date": second["date"], "actions_title": TODO, "now": [TODO for _ in second["actions"]]}
    return {**fields, "title": TODO, "read": TODO} if second["rows"] else fields


def _skeleton(date, m):
    slide = {"title": TODO, "read": TODO, "rows": "dimensions", "dimensions": [], "questions": [], "excerpts": [], "action": None}
    shown = present(m)
    second = {"earlier": _earlier_fields(m["second"])} if m.get("second") else {}
    return {"schema": SCHEMA, "date": date, "same_audience": False, "moved": {}, **second,
            "opening": {"who": TODO, "questions": {b: TODO for b in shown}, "examples": {b: [] for b in shown}},
            "found": {"title": TODO, "answers": {b: TODO for b in shown}},
            "actions_title": TODO,
            "actions": [{"class": TODO, "what": TODO, "why": TODO, "read_next": TODO, "block": TODO, "pages": []}],
            "blocks": {b: [dict(slide)] for b in shown},
            "sources": {"title": TODO, "read": TODO},
            "method": {"limits": [], "ask": [TODO]}}


def _listed_pages(pages):
    return ", ".join(f"{p} ({n})" for p, n in pages[:SITES_SHOWN])


def _plan(m, study, date, lang):
    """The figures the deck will draw, block by block, as the writer may cite them."""
    t = DECK[lang]

    def of(a, b):
        return f"{a} {t['of']} {b}"

    def rated(row):
        return (f"favourable {of(row['bands']['4-5'], row['judged'])}, neutral {of(row['bands']['3'], row['judged'])}, "
                f"unfavourable {of(row['bands']['1-2'], row['judged'])}")
    out = [f"# Figures of the deck of {date}", "",
           "What the deck draws. The text may cite these figures as they stand here, and the figures of the sections "
           "that follow. Each question shows its block and its key. Favourable is a score of 4 or 5, neutral 3, unfavourable "
           "1 or 2: the deck says favourable, neutral and unfavourable, never the score.", "", "## Blocks", ""]
    for key in present(m):
        block = m["blocks"][key]
        shown = "; ".join((f"{f['project']}: " if f["project"] else "") + of(f["a"], f["b"]) for f in block["figures"])
        out += [f"### {key}: {shown}", ""]
        if key == "reach":
            for f in block["figures"]:
                if f["rivals"]:
                    where = f" ({f['project']})" if f["project"] else ""
                    out.append(f"Compared on the same answers{where}: {m['subject']} {of(f['a'], f['b'])}, "
                               + ", ".join(f"{label} {of(n, f['b'])}" for label, n in f["rivals"])
                               + f". Position: {of(f['rank'], f['names'])} names monitored.")
            out.append("")
        for row in block["rows"]:
            a, b = _measure(key, row)
            line = f"- {row['project']} / {row['label']}: {of(a, b)}"
            if key == "reach" and row["foils"]:
                line += "; competitors named: " + ", ".join(f"{label} {of(n, row['given'])}" for label, n in row["foils"])
            if key == "description":
                line += "; " + rated(row)
            if key == "facts":
                line += (f"; of which beside an old figure {of(row['both'], row['current'])}; old figure only {of(row['outdated'], row['given'])}, "
                         f"not stated {of(row['silent'], row['given'])}; {rated(row)}")
                if row["outdated"]:
                    pages = "; ".join(f"{kind}: {_listed_pages(found)}" for kind, found in row["telling"].items() if found)
                    line += f"; pages cited by the answers with the old figure and hardly ever by today's: {pages or 'none'}"
            out.append(line)
        rows = {r["key"]: r for r in block["questions"]}
        out += ["", "Questions (key, topic, text, figure):"]
        placed = block["placed"] if key != "facts" else [{"key": r["key"], "text": r["label"], "dimension": r["dimension"]}
                                                         for r in block["questions"]]
        for q in placed:
            row = rows.get(q["key"])
            shown = (": " + of(*_measure(key, row))) if row else ""
            if row and key != "reach":
                shown += f"; {rated(row)}"
            out.append(f"- {q['key']} ({q['dimension']}): «{q['text']}»{shown}")
        s = block["sources"]

        def listed(domains):
            return ", ".join(f"{d['domain']} ({d['answers']})" for d in domains) or "none"

        def counted(domains):
            return ", ".join(f"{d['domain']} ({d['answers']}, of which {d['naming']} name the subject)" for d in domains) or "none"
        out += ["", f"Sources: of {s['answers']} answers, {s['owned']} cite the subject's pages, {s['foil']} competitors' "
                    f"pages, {s['third']} other sites.",
                f"other sites cited most: {(counted if key == 'reach' else listed)(s['third_domains'])}",
                "other pages cited most: " + ", ".join(f"{p} ({n})" for p, n in s["third_pages"]),
                f"competitors' domains cited most: {listed(s['foil_domains'])}", ""]
    if m["replaced"]:
        out += ["## Facts a later record replaces", "",
                "These questions count by rating, in their block. Their terms no longer say what is current: never write one "
                "as current, and take no action on it.", ""]
        out += [f"- «{r['question']}»: {r['fact']} ({r['date']}), replaced by: {r['later']} ({r['later_date']})"
                for r in m["replaced"]]
        out.append("")
    second = m.get("second")
    if second:
        out += [f"## Compared with the deck of {second['date']}", ""]
        if second["rows"]:
            out += ["Each block's figure on both dates, on the questions asked of the same assistants. Fill `earlier`: `title` and "
                    "`read` say what moved.", ""]
            out += [f"- {r['block']}{' (' + r['project'] + ')' if r['project'] else ''}: {of(*r['before'])} then, {of(*r['now'])} now"
                    + (f", {r['change']}" if r["change"] else "") for r in second["rows"]]
        else:
            out.append("No question was asked of the same assistants on both dates: only the slide of the actions is drawn.")
        out += ["", "The actions of that deck and the figure each said to read next. Fill `earlier.now`, one per action, with the same "
                    "figure on this period. Never say an action moved a figure: the deck does not know whether the reader acted.", ""]
        out += [f"{n}. {a['what']}. Figure then: {a['then']}" for n, a in enumerate(second["actions"], 1)]
        out.append("")
    return out


def _without_answers(material):
    """The material with each answer and its heading taken out."""
    out, inside = [], False
    for line in material.splitlines():
        if line == "~~~~":
            inside = not inside
        elif not inside and not (line.startswith("**") and ", sources: " in line) and not line.startswith("Each answer is between"):
            if line or (out and out[-1]):
                out.append(line)
    return out


def write(root, date=None):
    """The figures file and, the first time, the deck's text to fill. A second run keeps what is written, reads its
    `moved` and `same_audience`, and adds `earlier` when a deck before this one has become final."""
    folder, date, study, period, doc = load(root, date)
    lang = study["report_language"]
    m = build_model(folder, study, period, doc)
    path = folder.path("reports", f"{date}.deck.json")
    if doc is None:
        path.parent.mkdir(exist_ok=True)
        write_json(path, _skeleton(date, m))
    elif m.get("second") and "earlier" not in doc:
        write_json(path, {**doc, "earlier": _earlier_fields(m["second"])})
    material = folder.path("history", "material", f"{date}.md")
    if not material.exists():
        raise Refused(f"no material for {date}: run period --date {date} first")
    figures = folder.path("history", "deck", f"{date}.figures.md")
    figures.parent.mkdir(exist_ok=True)
    write_text(figures, "\n".join(_plan(m, study, date, lang) + _without_answers(material.read_text(encoding="utf-8"))) + "\n")
    blocks = ", ".join(f"{b} ({len(m['blocks'][b]['placed'])} questions)" for b in present(m))
    notes = folder.path("history", "deck", f"{date}.notes.md")
    earlier = f" Notes of an earlier session: {notes}. Read them first." if notes.exists() else ""
    return f"Blocks: {blocks}. Figures: {figures}. To fill: {path}, {path.read_text(encoding='utf-8').count(TODO)} texts left.{earlier}"


# --- the check --------------------------------------------------------------

def _texts(doc):
    """(field, limit name, text) of every text of the deck the reader gets, excerpts apart."""
    opening = doc.get("opening") or {}
    yield "opening who", "who", opening.get("who") or ""
    for key, question in (opening.get("questions") or {}).items():
        yield f"opening question {key}", "question", question
    found = doc.get("found") or {}
    yield "found title", "title", found.get("title") or ""
    for key, answer in (found.get("answers") or {}).items():
        yield f"found answer {key}", "answer", answer
    yield "actions title", "title", doc.get("actions_title") or ""
    for n, a in enumerate(doc.get("actions") or [], 1):
        for field in ("what", "why", "read_next"):
            yield f"action {n} {field}", field, a.get(field) or ""
    earlier = doc.get("earlier") or {}
    for field, limit in (("title", "title"), ("read", "read"), ("actions_title", "title")):
        if field in earlier:
            yield f"earlier {field}", limit, earlier[field] or ""
    for n, text in enumerate(earlier.get("now") or [], 1):
        yield f"earlier action {n} now", "read_next", text
    for key, slides in (doc.get("blocks") or {}).items():
        for slide in slides:
            yield f"{key} title", "title", slide.get("title") or ""
            yield f"{key} read", "read", slide.get("read") or ""
    sources = doc.get("sources") or {}
    yield "sources title", "title", sources.get("title") or ""
    yield "sources read", "read", sources.get("read") or ""
    method = doc.get("method") or {}
    for text in method.get("limits") or []:
        yield "method limit", "limit", text
    for text in method.get("ask") or []:
        yield "method question", "ask", text


def _competitor_sites(doc, study):
    """A competitor's own site is no place to act on: the reader can ask third parties, not rivals."""
    domains = [d for f in study.get("foils") or [] for d in f.get("domains") or []]
    return [f"action {n} sends the reader to {d}, a competitor's site: name the third parties' pages the answers cite"
            for n, a in enumerate(doc.get("actions") or [], 1) for d in domains
            if re.search(r"(?<![\w-])" + re.escape(d) + r"(?![\w-])", a.get("what") or "")]


def _opening(doc, m):
    """What the first slides need: who asks, the question each block answers, a real question for each, the answer."""
    problems = []
    opening, found = doc.get("opening") or {}, doc.get("found") or {}
    questions, answers, examples = (opening.get("questions") or {}), (found.get("answers") or {}), (opening.get("examples") or {})
    for key in present(m):
        if not (questions.get(key) or "").strip().endswith("?"):
            problems.append(f"opening question {key} is the question this block answers, in the reader's words: end it with ?")
        if re.search(r"\d", questions.get(key) or ""):
            problems.append(f"opening question {key} holds a count: the card draws it")
        if not (answers.get(key) or "").strip():
            problems.append(f"found answer {key} is missing: answer the opening's question in one sentence")
        chosen = examples.get(key) or []
        if not 1 <= len(chosen) <= MAX_EXAMPLES:
            problems.append(f"opening example of {key}: give one or two question keys, {len(chosen)} given")
        known = {r.get("key") for r in m["blocks"][key]["questions"]}
        problems += [f"opening example {k} is not a question of block {key}" for k in chosen if k not in known]
    problems += [f"{key} has no question in this period: remove it from opening and found"
                 for key in set(questions) | set(answers) if key not in present(m)]
    return problems


def _second_edition(doc, m):
    """The part on the deck before this one: there when one exists, a figure for each of its actions, and no cause."""
    second, earlier = m.get("second"), doc.get("earlier")
    if not second:
        return ["`earlier` is filled and no deck comes before this one: remove it"] if earlier else []
    if not earlier:
        return [f"the deck of {second['date']} comes before this one: run deck again and fill `earlier`"]
    problems = []
    if earlier.get("date") != second["date"]:
        problems.append(f"earlier date is {earlier.get('date')} and the deck before this one is of {second['date']}")
    if second["rows"] and not (earlier.get("title") and earlier.get("read")):
        problems.append("earlier title and read are missing: they say what moved")
    now = earlier.get("now") or []
    if len(now) != len(second["actions"]):
        problems.append(f"{len(second['actions'])} earlier action(s) and {len(now)} figures in earlier now: give one for each")
    problems += [f"earlier action {n} now carries no figure" for n, text in enumerate(now, 1) if not re.search(r"\d", text)]
    told = [(f, text) for f, text in ((k, earlier.get(k) or "") for k in ("title", "read", "actions_title"))] + [("now", t) for t in now]
    return problems + [f"earlier {field} gives a cause ({found.group(0)}): the deck shows the figures on two dates, and does not "
                       "know whether the reader acted" for field, text in told for found in CAUSED.finditer(text)]


def _structure(doc, m):
    """The actions and what supports them, the slides of each block, and the deck's length."""
    problems = _opening(doc, m)
    blocks, actions = doc.get("blocks") or {}, doc.get("actions") or []
    if not actions:
        problems.append("the deck has no action")
    if len(actions) > MAX_ACTIONS:
        problems.append(f"{len(actions)} actions: a deck holds at most {MAX_ACTIONS}")
    for key, value in (doc.get("moved") or {}).items():
        if value != "description":
            problems.append(f"question {key} moved to {value}: a question can move only to description")
        if not any(q["key"] == key and not q["names_subject"] for q in m["blocks"]["description"]["placed"]):
            problems.append(f"question {key} is moved, and only a question naming no subject can be")
    for key in present(m):
        block = m["blocks"][key]
        slides = blocks.get(key) or []
        if not slides:
            problems.append(f"block {key} has no slide")
        if len(slides) > MAX_BLOCK_SLIDES:
            problems.append(f"block {key} has {len(slides)} slides: a block holds at most {MAX_BLOCK_SLIDES}")
        shown = set()
        known = {d for r in block["rows"] for d in _dimensions(r)}
        keys = {r.get("key") for r in block["questions"]}
        for slide in slides:
            for name in slide.get("dimensions") or []:
                if name not in known:
                    problems.append(f"block {key}: {name} is not one of its dimensions ({', '.join(sorted(known))})")
            problems += [f"block {key}: question {k} is not one of its questions" for k in slide.get("questions") or []
                         if k not in keys]
            rows = rows_of(key, block, slide)
            shown |= {d for r in rows for d in _dimensions(r)}
            if len(rows) > MAX_ROWS:
                problems.append(f"a slide of block {key} draws {len(rows)} rows, at most {MAX_ROWS}: "
                                "split them over its slides with `dimensions`")
            if len(slide.get("excerpts") or []) > MAX_EXCERPTS:
                problems.append(f"a slide of block {key} holds more than {MAX_EXCERPTS} excerpts")
            if slide.get("action") is not None and not slide.get("excerpts"):
                problems.append(f"the slide of block {key} supporting action {slide['action']} shows no answer: "
                                "give an excerpt of what the action rests on")
            if key == "description" and not slide.get("excerpts"):
                problems.append("a slide of block description shows no answer: a reader asks what a favourable answer says, "
                                "so give an excerpt of the kind its title speaks of")
            if slide.get("action") is not None and not 1 <= slide["action"] <= len(actions):
                problems.append(f"a slide of block {key} supports action {slide['action']}, which the deck does not have")
        missing = known - shown
        if slides and missing:
            problems.append(f"block {key}: no slide draws {', '.join(sorted(missing))}")
    problems += [f"block {key} has no question in this period: remove it" for key in blocks if key not in present(m)]
    for n, a in enumerate(actions, 1):
        if a.get("class") not in CLASSES:
            problems.append(f"action {n}: class {a.get('class')!r} is not one of {', '.join(CLASSES)}")
        if a.get("block") not in present(m):
            problems.append(f"action {n}: block {a.get('block')!r} is not one of {', '.join(present(m))}")
        elif not any(s.get("action") == n for s in blocks.get(a["block"]) or []):
            problems.append(f"action {n} has no evidence slide: set `action` on a slide of block {a['block']}")
        for field in ("why", "read_next"):
            if not re.search(r"\d", a.get(field) or ""):
                problems.append(f"action {n}: {field} carries no figure")
    count = 4 + sum(len(s) for s in blocks.values()) + bool(_any_sources(m)) + 1
    if count > MAX_SLIDES:
        problems.append(f"the deck has {count} slides before the list of questions, at most {MAX_SLIDES}")
    return problems


def _drawn(key, block, slide):
    """The x of y a slide shows: its chart and the dimensions of the questions it draws. The block's figure counts only
    on a slide drawing the whole block: over part of it, the reader looks for that figure and cannot find it."""
    rows = rows_of(key, block, slide)
    dimensions = set() if slide.get("questions") else {d for r in rows for d in _dimensions(r)}
    seen = set()
    if dimensions >= {d for r in block["rows"] for d in _dimensions(r)}:
        seen = {(f["a"], f["b"]) for f in block["figures"]}
        seen.add(tuple(sum(f[k] for f in block["figures"]) for k in ("a", "b")))
        seen |= {(n, f["b"]) for f in block["figures"] for _, n in f.get("rivals") or []}
    for row in rows + [r for r in block["rows"] if set(_dimensions(r)) & dimensions]:
        seen.add(_measure(key, row))
        seen |= {(n, row["judged"]) for n in row["bands"].values()}
        seen |= {(n, row["given"]) for _, n in row.get("foils") or []}
        seen |= {(row.get(part), row["given"]) for part in ("outdated", "silent")}
        seen |= {(n, row.get("outdated")) for _, n in _pages_shown(row)}
    return seen


def _undrawn(doc, m):
    """A figure over a chart is what the reader looks for in that chart."""
    problems = []
    for key, slides in (doc.get("blocks") or {}).items():
        if key not in m["blocks"]:
            continue
        for slide in slides:
            seen = _drawn(key, m["blocks"][key], slide)
            problems += [f"{key} {field} cites {c.group(0)}, which its chart does not draw: draw the question with "
                         "`questions`, draw fewer dimensions, or leave the figure out"
                         for field in ("title", "read") for c in COUNT.finditer(slide.get(field) or "")
                         if (pair := (int(c.group(1)), int(c.group(4)))) not in seen
                         and pair not in _tied_to_sites(slide.get(field) or "", m)]
    return problems


def _why_drawn(doc, m):
    """An action's reason is what the reader goes to its slide to see."""
    problems = []
    for n, action in enumerate(doc.get("actions") or [], 1):
        key = action.get("block")
        slide = next((s for s in (doc.get("blocks") or {}).get(key) or [] if s.get("action") == n), None)
        if slide is None or key not in m["blocks"]:
            continue
        why = action.get("why") or ""
        seen = _drawn(key, m["blocks"][key], slide) | _tied_to_sites(why, m)
        cited = [(int(c.group(1)), int(c.group(4))) for c in COUNT.finditer(why)] + [(0, int(c.group(1))) for c in NONE_OF.finditer(why)]
        problems += [f"action {n} gives {a} of {b} as its reason, and its slide does not draw it: draw that question, "
                     "or give the reason its slide shows" for a, b in cited if (a, b) not in seen]
    return problems


def _any_sources(m):
    return any(m["blocks"][b]["sources"]["with_sources"] for b in present(m))


def _thin(key, row):
    """A question with too few answers for a finding of its own."""
    return bool(row.get("key")) and (_measure(key, row)[1] or 0) < MIN_ANSWERS


def rows_of(key, block, slide):
    """The rows a slide draws: the questions it names; else its dimensions, one row each or, with `rows: questions`, one
    per question. A slide on one or two dimensions draws their questions: it is about them. A fact has one row however
    many questions bring it out."""
    keys = slide.get("questions") or []
    if keys:
        return [r for r in block["questions"] if r.get("key") in keys]
    chosen = set(slide.get("dimensions") or [])

    def picked(pool):
        return [r for r in pool if not chosen or set(_dimensions(r)) & chosen]
    if key == "facts":
        return picked(block["questions"]) if slide.get("rows") == "questions" else picked(block["rows"])
    questions = picked(block["questions"])
    few = any(_thin(key, q) for q in questions)
    if slide.get("rows") == "questions" or (len(picked(block["rows"])) <= 2 and len(questions) <= 6 and not few):
        return questions
    return picked(block["rows"])


def _answered(folder, period):
    """(question text as `check` compares it, response) of every answer of the period."""
    for key, ids in period["runs"].items():
        keys = {q["key"]: match_key(q["text"]) for d in period["asked"].get(key, []) for q in d["questions"]}
        for run_id in ids:
            for r in folder.run(key, run_id)["responses"]:
                if r["match"] != "unmatched" and r["answer"] and r["question"] in keys:
                    yield keys[r["question"]], r


def _responses(folder, period):
    """{(question text, model): the answers given}, compared in `check`'s plain form."""
    out = {}
    for text, r in _answered(folder, period):
        out.setdefault((text, r["model"]), []).append(_plain(r["answer"]))
    return out


def _address(page):
    return re.sub(r"^(?:https?://)?(?:www\.)?", "", page.lower()).rstrip("/.")


def _unseen_pages(doc, study, folder, period):
    """An address the writer composed reads as a page that exists: only those the answers cite, or the study
    records as the source of a fact, may be named."""
    answered = [r for _, r in _answered(folder, period)]
    known = [_address(s["url"]) for r in answered for s in r["sources"] if s.get("url")]
    known += [_address(f.get("source") or "") for p in study["projects"] for d in p["dimensions"] for q in d["questions"]
              for f in q.get("facts") or []]
    cited = "\n".join(known + [r["answer"].lower() for r in answered])
    return [f"{field} names {page}, an address no answer cites: give the domain, or an address the answers cite"
            for field, _, text in _texts(doc) for page in PAGE.findall(text) if _address(page) not in cited]


def _named_sites(doc, study, folder, period):
    """An action says where to act, on a site the answers cite: the reader's first question is why that one."""
    reader = Reader(study)
    cited = {s["domain"] for _, r in _answered(folder, period) for s in r["sources"] if s.get("domain")}
    cited |= {_address(f.get("source") or "").split("/")[0] for p in study["projects"] for d in p["dimensions"]
              for q in d["questions"] for f in q.get("facts") or []}
    problems = []
    for n, action in enumerate(doc.get("actions") or [], 1):
        sites = [d.lower() for d in DOMAIN.findall(action.get("what") or "")]
        if not sites:
            problems.append(f"action {n} names no site: give the domain it acts on")
        problems += [f"action {n} names {d}, which no answer cites: choose a site the answers read" for d in sites
                     if reader.author(d) != "owned" and not any(c == d or c.endswith("." + d) for c in cited)]
        if ASK_TO_CHECK.search(action.get("what") or ""):
            problems.append(f"action {n} asks a third party to check: the reader does the checking, and asks it to add or "
                            "correct what is missing")
        if action.get("class") not in ("confused", "wrong_fact") and ASSERTED.search(action.get("what") or ""):
            problems.append(f"action {n} dictates a fact the study does not record: say what the page must answer, "
                            "and leave the content to the subject")
        if sites and EDITED.match(action.get("what") or "") and reader.author(sites[0]) != "owned":
            problems.append(f"action {n} tells the reader to edit {sites[0]}, a page the reader does not own: "
                            "write that they ask its owners")
    return problems


def _own_action(doc, study, folder, period):
    """The reader controls the subject's pages and can only ask everywhere else."""
    reader = Reader(study)
    if not any(reader.author(s["domain"]) == "owned" for _, r in _answered(folder, period) for s in r["sources"] if s.get("domain")):
        return []
    named = [d.lower() for a in doc.get("actions") or [] for d in DOMAIN.findall(a.get("what") or "")]
    if named and not any(reader.author(d) == "owned" for d in named):
        return ["every action asks a third party: give at least one on the subject's own pages, from what the answers "
                "about the subject lack"]
    return []


def _same_rows(doc, m):
    """A slide of rows another slide of the block already draws tells the reader nothing new."""
    problems = []
    for key, slides in (doc.get("blocks") or {}).items():
        if key not in m["blocks"]:
            continue
        drawn = [{r["label"] for r in rows_of(key, m["blocks"][key], s)} for s in slides]
        problems += [f"two slides of block {key} draw the same rows: give each its own, or draw the questions of one"
                     for i, a in enumerate(drawn) for b in drawn[i + 1:] if a and b and (a <= b or b <= a)]
    return problems


def _same_examples(doc, m):
    """Two cards showing the same questions read as one card: a block with others to show shows those."""
    examples, problems = (doc.get("opening") or {}).get("examples") or {}, []
    for key in present(m):
        chosen = examples.get(key) or []
        others = {k for other, keys in examples.items() if other != key for k in keys}
        spare = [q for q in m["blocks"][key]["questions"] if q.get("key") not in others | set(chosen) and not _thin(key, q)]
        problems += [f"opening example {k} stands on two cards: block {key} has other questions to show"
                     for k in chosen if k in others and spare]
    return problems


def _doubts(doc, m):
    """A doubt printed beside "favourable answer" reads as a contradiction."""
    return [f"an excerpt of block {key} quotes a doubt from a favourable answer: quote it from a neutral or unfavourable one: "
            f"{e.get('text')[:60]!r}" for key, slides in (doc.get("blocks") or {}).items() for slide in slides
            for e in slide.get("excerpts") or [] if DOUBT.search(e.get("text") or "") and _rating(e, m, key) == "4-5"]


def _amounts(doc, study):
    """An amount no slide shows has no proof: a sentence states a recorded fact or what an excerpt beside it quotes."""
    def digits(text):
        return {re.sub(r"\D", "", a) for a in AMOUNT.findall(text)}

    recorded = {re.sub(r"\D", "", n) for term in _quotable(study) for n in re.findall(r"\d[\d.,]*", term)}
    problems, slides = [], [s for block in (doc.get("blocks") or {}).values() for s in block]

    def judge(field, text, excerpts):
        shown = recorded | digits(" ".join(e.get("text") or "" for e in excerpts))
        problems.extend(f"{field} states an amount no excerpt of its slide shows and no fact records: {a}"
                        for a in sorted(digits(text) - shown))

    for slide in slides:
        judge("a slide's title or read", f'{slide.get("title") or ""} {slide.get("read") or ""}', slide.get("excerpts") or [])
    for n, a in enumerate(doc.get("actions") or [], 1):
        judge(f"action {n}", a.get("why") or "", [e for s in slides if s.get("action") == n for e in s.get("excerpts") or []])
    return problems


def _one_answer(doc):
    """One answer is what an assistant happened to say: it can stand in a read, not carry work for the reader."""
    return [f"action {n} rests on one answer: an action needs at least three, so count them or take another"
            for n, a in enumerate(doc.get("actions") or [], 1) if ONE_ANSWER.search(a.get("why") or "")]


def _sites_compared(doc):
    """Two sites level at 44 were written as one overtaking the other, and the subject's own site is usually cited most."""
    sources, problems = doc.get("sources") or {}, []
    for field in ("title", "read"):
        text = sources.get(field) or ""
        if SITE_RANK.search(text):
            problems.append(f"sources {field} compares sites in words: state each site's answers, which the table draws")
        if MOST_CITED.search(text):
            problems.append(f"sources {field} says the site cited most: say among which sites, the subject's own is on the table too")
    return problems


def _top_site(doc, m):
    """The reader sees the site cited most, with no action on it, and asks why: the sources slide says."""
    named = " ".join(a.get("what") or "" for a in doc.get("actions") or []).lower()
    read = ((doc.get("sources") or {}).get("read") or "").lower()
    problems = []
    for key in ("reach", "description"):
        third = ((m["blocks"].get(key) or {}).get("sources") or {}).get("third_domains") or []
        if third:
            label = max(third[0]["domain"].split(".")[:-1], key=len)
            if label not in named and not (label in read and WHY_NOT.search(read)):
                problems.append(f"{third[0]['domain']} is the third party cited most on block {key} and has no action: "
                                "name it in sources.read and say why")
    return problems


def _is_third(action, author):
    sites = [d.lower() for d in DOMAIN.findall(action.get("what") or "")]
    return bool(sites) and not any(author(d) == "owned" for d in sites)


def _third_pages(doc, study, folder, period, m):
    """A writer reading only the answers asks a shop to list a rival, or to correct a figure its page does not hold: a site an
    action asks has been opened, and so has any page it corrects, and what the page shows is on the record for the reader."""
    reader = Reader(study)
    known = {_address(s["url"]) for _, r in _answered(folder, period) for s in r["sources"] if s.get("url")}
    problems = []
    for n, action in enumerate(doc.get("actions") or [], 1):
        what, corrects = action.get("what") or "", action.get("class") == "wrong_fact"
        sites = list(dict.fromkeys(map(str.lower, DOMAIN.findall(what))))
        if corrects and sites and not any(p.get("shows") for p in action.get("pages") or []):
            problems.append(f"action {n} corrects a figure no page was read to show: open the pages the answers with the old "
                            "figure cite, and rest it on one that shows it, or leave the action out")
        for site in sites:
            if reader.author(site) == "owned" and not corrects:
                continue
            page = next((p for p in action.get("pages") or [] if site in _address(p.get("url") or "")), None)
            if page is None:
                problems.append(f"action {n} names {site} and says nothing of its page: open the page the answers cite and "
                                "record it in `pages`, with what it shows")
                continue
            if _address(page.get("url") or "") not in known:
                problems.append(f"action {n}: {page.get('url')} is not a page the answers cite")
            shows = page.get("shows") or []
            label = max(site.split(".")[:-1], key=len)
            others = [s for s in shows if label not in s.lower() and m["subject"].lower() not in s.lower()]
            if not shows:
                if not CHECK_FIRST.search(what):
                    problems.append(f"action {n} asks {site} for something and its page was not read: open it, or start the "
                                    "action with what the reader checks there")
            elif not corrects and len(others) < 2:
                problems.append(f"action {n}: the page of {site} lists fewer than two others, so nobody gets listed there: "
                                "choose a page that compares providers, or an action on the subject's own pages")
            elif not corrects and ADDS.search(what) and any(m["subject"].lower() in s.lower() for s in shows):
                problems.append(f"action {n} asks {site} to add the subject, and its page lists it: say what is missing there")
    return problems


def _weak_sites(doc, m):
    """A site few answers read earns "why that one?", and the slide prints how few."""
    return [f"action {n} names {site}, cited by {citing} of the {total} answers on its slide: choose a site the assistants "
            "read more" for n, action in enumerate(doc.get("actions") or [], 1)
            for site, citing, total, _ in _site_counts(action, n, doc, m) if citing and citing < max(MIN_SITE_ANSWERS, MIN_SITE_SHARE * total)]


def _worst_shown(doc, m):
    """A reader told of unfavourable answers looks for one."""
    if "description" not in m["blocks"] or m.get("fidelity"):
        return []
    worst = sum(r["bands"]["1-2"] for r in m["blocks"]["description"]["rows"])
    shown = [_rating(e, m, key) for key, slides in (doc.get("blocks") or {}).items() if key != "reach"
             for slide in slides for e in slide.get("excerpts") or []]
    if worst and "1-2" not in shown:
        return [f"{worst} answers are unfavourable and no excerpt shows one: the reader looks for it"]
    return []


def _too_few(doc, m):
    """One answer of two is no finding: such a question counts in its topic and in the list of questions, nowhere else."""
    problems = []
    for key, chosen in ((doc.get("opening") or {}).get("examples") or {}).items():
        problems += [f"opening example {q['key']} has too few answers for a finding: pick a question the deck can show"
                     for q in (m["blocks"].get(key) or {}).get("questions") or [] if q.get("key") in chosen and _thin(key, q)]
    for key, slides in (doc.get("blocks") or {}).items():
        if key not in m["blocks"]:
            continue
        block = m["blocks"][key]
        thin = {match_key(q["label"]) for q in block["questions"] if _thin(key, q)}
        for slide in slides:
            problems += [f"{key} draws question {r['key']}, with too few answers for a row of its own: draw its topic"
                         for r in rows_of(key, block, slide) if _thin(key, r)]
            problems += [f"an excerpt comes from a question with too few answers for a finding: {e.get('question')!r}"
                         for e in slide.get("excerpts") or [] if match_key(e.get("question") or "") in thin]
    return problems


def _read_on_its_slide(doc, study, folder, period, m):
    """The reader goes to an action's slide to see why that site: it is read on the questions there."""
    reader, cited, problems = Reader(study), {}, []
    for text, r in _answered(folder, period):
        cited.setdefault(text, set()).update(s["domain"] for s in r["sources"] if s.get("domain"))
    for n, action in enumerate(doc.get("actions") or [], 1):
        key = action.get("block")
        slide = next((s for s in (doc.get("blocks") or {}).get(key) or [] if s.get("action") == n), None)
        if slide is None or key not in m["blocks"]:
            continue
        block = m["blocks"][key]
        rows = rows_of(key, block, slide)
        keys = {r.get("key") for r in rows} - {None}
        topics = {d for r in rows if not r.get("key") for d in _dimensions(r)}
        domains = set().union(*[cited.get(match_key(q["label"]), set()) for q in block["questions"]
                                if q.get("key") in keys or set(_dimensions(q)) & topics] or [set()])
        problems += [f"action {n} names {d}, which no answer cites on the questions of its slide: "
                     "choose a site read on those questions" for d in map(str.lower, DOMAIN.findall(action.get("what") or ""))
                     if reader.author(d) != "owned" and not any(c == d or c.endswith("." + d) for c in domains)]
    return problems


def _voices(doc, m):
    """Excerpts all from one assistant read as a study of that assistant, on questions several answer."""
    voices = [e.get("assistant") for key, slides in (doc.get("blocks") or {}).items()
              if key in m["blocks"] and len(_block_assistants(key, m)) > 1
              for slide in slides for e in slide.get("excerpts") or []]
    if len(voices) > 1 and len(set(voices)) == 1:
        return [f"all {len(voices)} excerpts of the questions several assistants answer come from {voices[0]}: "
                "show at least one answer of another assistant"]
    return []


def _cut(text, pieces, answers):
    """Whether an excerpt starts or ends inside a sentence with no mark of the cut: read without the words
    around it, a part of a sentence can say what the sentence does not."""
    bare = text.strip().strip("«»“”\"'").strip()
    opened = bool(re.match(r"(?:\[…\]|\[\.\.\.\]|\(…\)|\(\.\.\.\)|…|\.\.\.)", bare))
    closed = bool(re.search(r"(?:\[…\]|\[\.\.\.\]|\(…\)|\(\.\.\.\)|…|\.\.\.)$", bare))
    found = []
    for answer in answers:
        if not _quoted_in(pieces, [answer]):
            continue
        at = answer.find(pieces[0])
        end = answer.rfind(pieces[-1]) + len(pieces[-1])
        if not opened and not SENTENCE_START.search(answer[:at].rstrip() if answer[:at].strip() else ""):
            found.append("starts inside a sentence")
        if not closed and end < len(answer) and not SENTENCE_END.search(pieces[-1]):
            found.append("ends inside a sentence")
        return found
    return found


def _excerpts(doc, study, period, by_answer, names):
    problems = []
    questions = {match_key(q["text"]) for d in (d for ds in period["asked"].values() for d in ds) for q in d["questions"]}
    models = {}
    for model, name in names.items():
        models[match_key(name)] = model
        models[match_key(name.split(": ", 1)[-1])] = model
    for key, slides in (doc.get("blocks") or {}).items():
        for slide in slides:
            for e in slide.get("excerpts") or []:
                text, question, assistant = e.get("text") or "", e.get("question") or "", e.get("assistant") or ""
                pieces = _pieces(text)
                if len(ELLIPSIS.sub(" ", text).split()) > MAX_WORDS:
                    problems.append(f"an excerpt holds over {MAX_WORDS} words: {text[:60]!r}")
                if match_key(question) not in questions:
                    problems.append(f"{question!r} is not a question of the period: copy it as `figures` gives it")
                    continue
                if match_key(assistant) not in models:
                    problems.append(f"{assistant!r} is not an assistant of the period ({', '.join(names.values())})")
                    continue
                pool = by_answer.get((match_key(question), models[match_key(assistant)]), [])
                if not _quoted_in(pieces, pool):
                    problems.append(f"excerpt not found verbatim in the answers of {assistant} to this question: {text[:80]!r}; "
                                    + _stops_matching(pieces[0] if pieces else "", pool))
                    continue
                problems += [f"an excerpt {why}: mark the cut with […], and keep whole any condition or comparison its "
                             f"meaning rests on: {text[:80]!r}" for why in _cut(text, pieces, pool)]
    return problems


def _quotable(study):
    """The texts a «» may hold without being read as figures: questions and fact terms."""
    found = {tight(match_key(q["text"])) for p in study["projects"] for d in p["dimensions"] for q in d["questions"]}
    terms = (fact_terms(q) or {} for p in study["projects"] for d in p["dimensions"] for q in d["questions"])
    return found | {tight(match_key(t)) for term in terms for ts in term.values() for t in ts}


def _allowed_figures(m, period):
    """What the text may cite: the figures of the period, and those the deck draws from it."""
    scopes = [s for b in period["projects"].values() for s in [b, *b["dimensions"].values()]]
    scopes += [q for b in period["projects"].values() for d in b["dimensions"].values() for q in d["questions"].values()]
    decimals, percents, pairs = _allowed(scopes)
    for row in (m.get("second") or {}).get("rows") or []:
        _ratio(*row["before"], percents, pairs)
        _ratio(*row["now"], percents, pairs)
    for key in present(m):
        block = m["blocks"][key]
        for f in block["figures"]:
            _ratio(f["a"], f["b"], percents, pairs)
            for _, n in f["rivals"]:
                _ratio(n, f["b"], percents, pairs)
            if f["rivals"]:
                pairs.add((f["rank"], f["names"]))
        pooled = [sum(f[k] for f in block["figures"]) for k in ("a", "b")]
        _ratio(*pooled, percents, pairs)
        for row in block["rows"] + block["questions"]:
            _ratio(*_measure(key, row), percents, pairs)
            for n in row["bands"].values():
                _ratio(n, row["judged"], percents, pairs)
            if key == "facts":
                _ratio(row["outdated"], row["given"], percents, pairs)
                _ratio(row["both"], row["current"], percents, pairs)
                _ratio(row["silent"], row["given"], percents, pairs)
                for _, n in _pages_shown(row):
                    _ratio(n, row["outdated"], percents, pairs)
            else:
                for _, n in row["foils"]:
                    _ratio(n, row["given"], percents, pairs)
        s = block["sources"]
        for n in (s["owned"], s["foil"], s["third"],
                  *(d["answers"] for ds in (s["domains"], s["third_domains"], s["foil_domains"]) for d in ds)):
            _ratio(n, s["answers"], percents, pairs)
        for d in s["third_domains"] if key == "reach" else []:
            _ratio(d["naming"], d["answers"], percents, pairs)
    return decimals, percents, pairs


def _earned(word, sentence, pairs):
    """Whether a word saying all or nothing is what the figures say: "none" beside 0 of 18, "all 9 answers" of 9."""
    none = word.lower().startswith(("nessun", "none", "no ", "mai", "never", "assent", "absent", "rest", "fuori", "left", "missing"))
    for c in COUNT.finditer(sentence):
        a, b = int(c.group(1)), int(c.group(4))
        if (a == 0 if none else a == b) and (a, b) in pairs:
            return True
    for found in (NONE_OF if none else ALL_OF).finditer(sentence):
        total = int(found.group(1))
        if (0 if none else total, total) in pairs:
            return True
    return False


def _sweeping(doc, pairs):
    problems = []
    for field, limit, claim in _texts(doc):
        if limit not in ("title", "answer", "read", "why"):
            continue
        for sentence in SENTENCE.split(claim):
            problems += [f"{field} says all or nothing with {w.group(0)!r}: keep it only beside the count that says so, "
                         "\"none of the 18 answers\" or \"0 of 18\", or write the count" for w in SWEEPING.finditer(sentence)
                         if not _earned(w.group(0), sentence, pairs)]
    return problems


def _crowded(doc):
    """A sentence that strings figures together is read as a table: the chart holds them."""
    most = {"title": MAX_TITLE_FIGURES, "read": MAX_READ_FIGURES, "answer": MAX_READ_FIGURES}
    return [f"{field} holds {len(COUNT.findall(text))} figures, at most {most[limit]}: keep the one that makes the point"
            for field, limit, text in _texts(doc) if limit in most and len(COUNT.findall(text)) > most[limit]]


def _repeated(doc):
    """The same figure, again and again, on the slides that decide whether the reader goes on."""
    found = doc.get("found") or {}
    first = [found.get("title") or "", *(found.get("answers") or {}).values(), doc.get("actions_title") or ""]
    first += [a.get(k) or "" for a in doc.get("actions") or [] for k in ("what", "why")]
    seen = Counter((c.group(1), c.group(4)) for text in first for c in COUNT.finditer(text))
    return [f"{a} of {b} appears {n} times on the first slides, at most {MAX_REPEATS}: say it once and say something else"
            for (a, b), n in seen.items() if n > MAX_REPEATS]


def _reader_words(doc, m, study):
    """Words the reader does not have: the study's, its project names, and a topic standing as the subject of a sentence."""
    found = []
    for field, limit, text in _texts(doc):
        found += [f"{field} says {w.group(0)!r}, a word of the study: write what the reader would say (DECK.md, Words)"
                  for w in JARGON.finditer(text)]
        found += [f"{field} says {w.group(0)!r}: the chart says neutre" for w in BAND_WORD.finditer(text)]
        if limit != "ask":
            found += [f"{field} says {w.group(0)!r}: name the subject, the deck is written about it" for w in FIRST_PERSON.finditer(text)]
        if limit == "what":
            found += [f"{field} says {w.group(0)!r}: say what to write and on which page" for w in VAGUE.finditer(text)]
        if limit in ("title", "answer", "read"):
            found += [f"{field} says {w.group(0)!r}: the answers show what assistants reply, not what people think"
                      for w in REACTION.finditer(text)]
        found += [f"{field} says {w.group(0)!r}: write \"35 of the 75 answers on the app are favourable\""
                  for w in FAVOURABLE_IN.finditer(text)]
        if limit in ("title", "answer", "read", "why"):
            for proj in study["projects"]:
                name = _short(proj["name"], m["subject"])
                if name != m["subject"] and re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text):
                    found.append(f"{field} names the project {name}: say which questions, in the reader's words")
            themes = {d for b in present(m) for r in m["blocks"][b]["rows"] for d in _dimensions(r)}
            found += [f"{field} makes the topic {name} the subject of a sentence: say who asks and what they find"
                      for name in themes if re.search(re.escape(name) + THEME_VERB, text, re.I)]
    return found


def _listed_already(doc, m):
    """Asking for a listing where the answers on the subject already read that site earns "we are there already". A page
    opened and recorded says better than a count whether the subject is there."""
    cited = m["blocks"].get("description", {}).get("sources", {}).get("third_all") or {}
    return [f"action {n} asks for a listing on {domain}, which the answers about the subject already cite: "
            "say what is missing there, or choose another site"
            for n, action in enumerate(doc.get("actions") or [], 1) for domain in cited
            if domain in (action.get("what") or "") and LISTING.search(action.get("what") or "")
            and not any(domain in (p.get("url") or "") and p.get("shows") for p in action.get("pages") or [])]


def _compared(doc, m):
    """Presence read alone misleads: 72 of 120 reads as weak, and may be second of ten."""
    block = m["blocks"]["reach"]
    found = doc.get("found") or {}
    title, answer = found.get("title") or "", (found.get("answers") or {}).get("reach") or ""
    problems = []
    for f in block["figures"]:
        rivals = [name for name, _ in f["rivals"]]
        if not rivals:
            continue
        if answer and not any(name in answer for name in rivals):
            problems.append("found answer reach gives no comparison: name the competitors the same answers name")
        cited = [c for c in COUNT.finditer(title) if (int(c.group(1)), int(c.group(4))) == (f["a"], f["b"])]
        if cited and not any(name in title for name in rivals):
            problems.append("found title cites presence with no comparison: name a competitor, or leave the figure out")
        if f["rank"] <= 2:
            problems += [f"found answer reach says {w.group(0)!r} of a subject at position {f['rank']} of {f['names']}: "
                         "say where it stands" for w in PLAYED_DOWN.finditer(answer)]
            problems += ["found title sets presence against what holds with a 'but': at position "
                         f"{f['rank']} of {f['names']} it is no weakness" for c in cited
                         if re.search(r"\b(?:ma|però|but|yet)\b", title[:c.start()], re.I)]
    return problems


def _site_name(domain):
    """The name a sentence gives a site: Trustpilot for it.trustpilot.com, Money for money.co.uk."""
    parts = domain.split(".")[:-1]
    if len(parts) > 1 and parts[-1] in SITE_SUFFIX:
        parts.pop()
    return parts[-1].capitalize() if parts else domain


def _cited_domains(m):
    return {s["domain"] for answers in m["answers_of"].values() for r in answers for s in r["sources"] if s.get("domain")}


def _site_labels(m):
    """{a third party's name as a sentence writes it: its domains}. A competitor counts by its name, and a word of three
    letters reads as a word."""
    taken = {m["subject"].lower(), *(n.lower() for n in m.get("monitored") or [])}
    labels = {}
    for domain in _cited_domains(m):
        name = _site_name(domain)
        if m["author"](domain) == "third" and len(name) > 3 and name.lower() not in taken:
            labels.setdefault(name, []).append(domain)
    return labels


def _names_in(part, labels):
    """(start, end, shown, domains, page, by its bare name) of every site and page a part of a sentence names."""
    found = [(p.start(), p.end(), p.group(1), [_address(p.group(1)).split("/")[0]], _address(p.group(1)), False)
             for p in PAGE.finditer(part)]
    taken = [(a, b) for a, b, *_ in found]
    found += [(d.start(), d.end(), d.group(1).lower(), [d.group(1).lower()], None, False) for d in DOMAIN.finditer(part)
              if not any(a <= d.start() < b for a, b in taken)]
    if labels:
        words = "|".join(re.escape(name) for name in sorted(labels, key=len, reverse=True))
        found += [(w.start(), w.end(), w.group(0), labels[w.group(0)], None, True)
                  for w in re.finditer(rf"(?<![\w.-])(?:{words})(?![\w-]|\.[a-z])", part)]
    return sorted(found)


def _spans(part):
    """(start, end, count, base) of every count in a part of a sentence; a count with no base has None."""
    found = [(c.start(), c.end(), int(c.group(1)), int(c.group(4))) for c in COUNT.finditer(part)
             if not OTHER_UNIT.search(f"{c.group(2)} {' '.join(part[c.end():].split()[:1])}")]
    found += [(c.start(), c.end(), 0, int(c.group(1))) for c in NONE_OF.finditer(part)]
    found += [(c.start(), c.end(), int(c.group(1)), int(c.group(1))) for c in ALL_OF.finditer(part)]
    for bare in BARE_COUNT.finditer(part):
        group = next(g for g in (1, 2, 3) if bare.group(g))
        if not any(a <= bare.start(group) < b for a, b, *_ in found):
            found.append((bare.start(group), bare.end(group), int(bare.group(group)), None))
    return sorted(found)


def _beside(part, start, end, names):
    """The site a count stands beside, and whether it speaks of one of its pages: the name before its brackets, or the address
    the verb of citing joins it to. "Citare" also means naming in the text, so "9 citano Swan" is no count of a site's: a bare
    name ties only through brackets or a page. None when the count is of something else."""
    opened = part[:start].rstrip()
    if opened.endswith("("):
        before = opened[:-1].rstrip()
        name = next((n for n in names if n[1] == len(before)), None)
        return (name, False) if name else None
    addresses = [n for n in names if not n[5]]
    cue = next((c for c in reversed(list(CITING.finditer(part, 0, start))) if start - c.end() <= CUE_REACH), None)
    if cue:
        name = next((n for n in reversed(addresses) if n[1] <= cue.start()), None)
        if name:
            return name, bool(PAGE_WORD.search(part[max(0, name[0] - 25):name[0]] + " " + part[name[1]:start]))
    cue = CITING.search(part, end, end + 40)
    if not cue:
        return None
    name = next((n for n in addresses if n[0] >= cue.end()), None)
    if name:
        return name, False
    name = next((n for n in reversed(names) if n[1] <= start), None)
    return (name, True) if name and PAGE_WORD.search(part, cue.end(), cue.end() + 15) else None


def _tied_to_sites(text, m):
    """The x of y of a text that stand beside a site: no chart draws those."""
    labels = _site_labels(m)
    return {(a, b) for part in SENTENCE.split(text) for start, end, a, b in _spans(part)
            if b is not None and _beside(part, start, end, _names_in(part, labels))}


def _scopes(doc, m):
    """(block or part of one, name, answers) of the sets of answers a sentence may count, the widest first. Past the questions without the
    name a block counts the answers it scored, and a sentence may count those or all it was given."""
    everyone = {id(r): r for answers in m["answers_of"].values() for r in answers}
    yield "block", "the period", [r for r in everyone.values() if r["answer"] is not None]
    for key, block in m["blocks"].items():
        yield "block", f"block {key}", block["responses"]
        for slide in (doc.get("blocks") or {}).get(key) or []:
            yield "part", "its slide", _slide_answers(key, slide, m)
        for project in {r.get("project") for r in block["rows"]}:
            keys = [q.get("key") for q in block["questions"] if q.get("project") == project]
            yield "part", f"block {key} of {project}", [r for k in keys for r in m["answers_of"].get(k, []) if r["answer"] is not None]
    for key, block in m["blocks"].items():
        narrow = [(q["label"][:50], [q.get("key")]) for q in block["questions"]]
        narrow += [(row["label"], [q.get("key") for q in block["questions"] if q.get("project") == row.get("project")
                                   and set(_dimensions(q)) & set(_dimensions(row))]) for row in block["rows"]]
        for label, keys in narrow:
            given = [r for k in keys for r in m["answers_of"].get(k, []) if r["answer"] is not None]
            scored = [r for r in given if r["score"] is not None]
            yield "part", label, given
            if len(scored) != len(given):
                yield "part", label, scored


def _pages_cited(r, domains):
    """The pages of a site an answer cites by address, and whether it cites the site with its page hidden: a grounding redirect
    gives the site alone."""
    sources = [s for s in r["sources"] if s.get("domain") and is_owned(s["domain"], domains)]
    hidden = [urlparse(s.get("url") or "").hostname in REDIRECT_HOSTS for s in sources]
    return {cited_page(s) for s, away in zip(sources, hidden) if not away}, any(hidden)


def _tally(answers, domains, page, in_words):
    """(lowest, highest) answers that may count for a site or a page among `answers`: an answer hiding the page may have read it."""
    cited = [_pages_cited(r, domains) for r in answers]
    if page or in_words:
        pages = {page} if page else {p for shown, _ in cited for p in shown if "/" in p}
        hidden = sum(hides and not shown & pages for shown, hides in cited)
        known = [sum(p in shown for shown, _ in cited) for p in pages]
        return [(n, n + hidden) for n in known] or [(1, hidden)]
    alone = [sum(any(s.get("domain") == d for s in r["sources"]) for r in answers) for d in domains]
    together = sum(bool(shown) or hides for shown, hides in cited)
    return [(n, n) for n in {*alone, together}]


def _held(rows):
    """The counts of a name for the writer, those on the base it cited first."""
    shown = [(f"{lo} to {hi}" if lo != hi else str(lo), base, where) for lo, hi, base, where in rows if hi]
    seen, out = set(), []
    for count, base, where in shown:
        if (count, base) not in seen:
            seen.add((count, base))
            out.append(f"{count} of {base} on {where}")
    return "; ".join(out[:3]) or "no answer cites it"


def _tied_sites(field, part, labels, assistants, scopes):
    """The counts of a part of a sentence that stand beside a site: what is wrong with them, and those it judged."""
    names, problems, read = _names_in(part, labels), [], set()
    for start, end, a, b in _spans(part):
        tied = _beside(part, start, end, names)
        if not tied:
            continue
        (first, last, shown, domains, page, _), in_words = tied
        said = part[max(0, min(start, first) - 20):max(end, last)]
        models = [model for model, names_of in assistants.items() if any(n in said for n in names_of)]
        rows = []
        only = f", answers of {', '.join(sorted(assistants[model][-1] for model in models))} only" if models else ""
        for _, where, answers in scopes:
            pool = [r for r in answers if r["model"] in models] if models else answers
            rows += [(lo, hi, len(pool), where + only) for lo, hi in _tally(pool, domains, page, in_words)]
        what = f"a page of {shown}" if in_words else shown
        if b is None:
            problems.append(f"{field} says {a} beside {what} with no base: write it as a count of the answers it comes from: "
                            + _held(sorted(rows, key=lambda r: (r[0] != a, not r[0] <= a <= r[1], r[1] - r[0]))))
            continue
        read.add((a, b))
        if not any(lo <= a <= hi and base == b for lo, hi, base, _ in rows):
            problems.append(f"{field} says {a} of {b} beside {what}: it has " + _held(sorted(rows, key=lambda r: r[2] != b)))
    return problems, read


def _rival_counts(m):
    """{competitor: {(answers naming it, answers)}} on every figure, row and question."""
    held = {name: [] for name in m.get("monitored") or []}
    for key, block in m["blocks"].items():
        for f in block["figures"]:
            for name in held:
                held[name].append((dict(f.get("rivals") or []).get(name, 0), f["b"], f"block {key}"))
        for row in block["rows"] + block["questions"]:
            if "rivals" in row:
                for name in held:
                    held[name].append((row["rivals"].get(name, 0), row["given"], row["label"][:50]))
    return held


def _tied_rivals(field, part, held):
    """The counts of a part of a sentence said of a competitor: "X è nominata in 48 su 90", "X in 12", "X (37)"."""
    problems, read = [], set()
    for name, rows in held.items():
        for said in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)\s*(?:\(|{RIVAL_VERB}(?:in|at)\s+)(?=\d)", part):
            pair = COUNT.match(part, said.end())
            bare = BARE_RIVAL.match(part, said.end())
            if pair and not OTHER_UNIT.search(pair.group(2)):
                a, b = int(pair.group(1)), int(pair.group(4))
                read.add((a, b))
                if not any((a, b) == (n, base) for n, base, _ in rows):
                    problems.append(f"{field} says {a} of {b} beside {name}: it has "
                                    + _held([(n, n, base, where) for n, base, where in sorted(rows, key=lambda r: r[1] != b)]))
            elif not pair and bare and AFTER_BARE.match(part, bare.end()):
                a = int(bare.group(0))
                if not any(a == n for n, _, _ in rows):
                    problems.append(f"{field} says {a} beside {name}: it has " + _held([(n, n, base, where) for n, base, where in rows]))
    return problems, read


def _tied_counts(doc, m, clean=str):
    """A count must be the count of the name beside it, not merely some count of the period: what is wrong, and the counts
    judged here, which the period's figures need not hold."""
    labels, held = _site_labels(m), _rival_counts(m)
    assistants = {model: name.split(": ") for model, name in m["names"].items()}
    scopes = [s for s in _scopes(doc, m) if s[2]]
    problems, read = [], set()
    for field, limit, text in _texts(doc):
        if limit in ("who", "question", "ask"):
            continue
        for part in SENTENCE.split(clean(text)):
            for found, judged in (_tied_sites(field, part, labels, assistants, scopes), _tied_rivals(field, part, held)):
                problems += found
                read |= judged
    return problems, read


def _most_cited(doc, m):
    """A site said to be cited most comes first, alone, among the sites the sentence speaks of, on some set of answers: a whole
    block on the sources slide, whose title says so of whatever site it says the answers cite."""
    labels, problems = _site_labels(m), []
    scopes = [s for s in _scopes(doc, m) if s[2]]
    for field, _, text in _texts(doc):
        for part in SENTENCE.split(text):
            cited = CITING.search(part)
            word = MOST.search(part) or (cited if field == "sources title" else None)
            names = _names_in(part, labels) if word and cited else []
            if not names:
                continue
            claimed = min(names, key=lambda n: abs(n[0] - word.start()))
            site = _site_name(claimed[3][0])
            third = bool(THIRD_WORD.search(part))
            level, first = None, None
            for kind, where, answers in scopes:
                if kind != "block" and field.startswith("sources"):
                    continue
                counts = Counter(k for r in answers for k in {_site_name(s["domain"]) for s in r["sources"] if s.get("domain")
                                                              and (not third or m["author"](s["domain"]) == "third")})
                if not counts:
                    continue
                top = max(counts.values())
                leaders = sorted(k for k, n in counts.items() if n == top)
                first = first or (where, leaders[0], top)
                if leaders == [site]:
                    break
                if site in leaders:
                    level = level or (where, next(k for k in leaders if k != site), top)
            else:
                if level:
                    problems.append(f"{field} says {claimed[2]} is cited most, and it is level with {level[1]} on {level[0]}, "
                                    f"at {level[2]} answers: a tie is no most")
                elif first:
                    leader = min((d for d in _cited_domains(m) if _site_name(d) == first[1]), key=len, default=first[1])
                    problems.append(f"{field} says {claimed[2]} is cited most, and it comes first nowhere: on {first[0]} "
                                    f"{leader} has {first[2]} answers")
    return problems


def problems_of(folder, study, period, doc):
    if doc.get("schema") != SCHEMA:
        return [f"schema is not {SCHEMA}"]
    if "[[" in json.dumps(doc, ensure_ascii=False):
        return ["a text is left to write: replace every [[...]] marker"]
    lang = study["report_language"]
    m = build_model(folder, study, period, doc)
    allowed = _allowed_figures(m, period)
    problems = _structure(doc, m) + _second_edition(doc, m) + _competitor_sites(doc, study) + _undrawn(doc, m) + _compared(doc, m) + _listed_already(doc, m)
    problems += _why_drawn(doc, m) + _named_sites(doc, study, folder, period) + _voices(doc, m) + _too_few(doc, m)
    problems += _read_on_its_slide(doc, study, folder, period, m) + _own_action(doc, study, folder, period) + _same_rows(doc, m)
    problems += _weak_sites(doc, m) + _worst_shown(doc, m) + _same_examples(doc, m) + _doubts(doc, m) + _amounts(doc, study)
    problems += _sites_compared(doc) + _top_site(doc, m) + _third_pages(doc, study, folder, period, m) + _one_answer(doc)
    problems += [f"{field} gives the judgement to who asks: people ask and the answers judge"
                 for field, _, claim in _texts(doc) if ASKER_JUDGES.search(claim)]
    names = period.get("names") or {}
    by_answer = _responses(folder, period)
    problems += _excerpts(doc, study, period, by_answer, names)
    for field, limit, text in _texts(doc):
        if len(text) > LIMITS[limit]:
            problems.append(f"{field} holds {len(text)} characters, at most {LIMITS[limit]}: {text[:60]!r}")
        if not text.strip():
            problems.append(f"{field} is empty")
    text = "\n".join(t for _, _, t in _texts(doc))
    problems += [f"a word about how the deck was built appears: {w.group(0)}" for w in UNSAID.finditer(text)]
    problems += _reader_words(doc, m, study) + _crowded(doc) + _repeated(doc) + _sweeping(doc, allowed[2])
    problems += [f"{field} names an action by its number, and the deck sets the numbers: say what it does"
                 for field, _, claim in _texts(doc) if ACTION_NUMBER.search(claim)]
    problems += [f"{field} says favourable answers name the subject: the figure counts answers to the questions on it, and "
                 "others name it too" for field, _, claim in _texts(doc) if NAMING_FAVOURABLE.search(claim)]
    problems += [f"{field} says {w.group(0)!r}: a figure counts the answers carrying today's term, and those can be wrong "
                 "elsewhere; write that they state it, as the chart does"
                 for field, limit, claim in _texts(doc) if limit in ("title", "answer", "read") for w in OVERSTATED.finditer(claim)]
    problems += _unseen_pages(doc, study, folder, period)
    problems += [f"{field} names {term}, the current term of a fact a later record replaces: {r['later']}"
                 for r in m["replaced"] for term in r["terms"] for field, _, claim in _texts(doc)
                 if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", claim)]
    problems += leaks(folder, study, period, text, folder.binding)
    shown = [*names.values(), *(n.split(": ", 1)[-1] for n in names.values())]
    answers = [a for pool in by_answer.values() for a in pool]
    quotable = _quotable(study)
    tied, read = _tied_counts(doc, m, lambda t: _unquote(t, quotable, answers))
    problems += tied + _most_cited(doc, m)
    problems += _figures(_unquote(text, quotable, answers, shown), lang, (*allowed[:2], allowed[2] | read), every_count=True)
    return problems


def check(root, path, date=None):
    path = Path(path)
    day = date or path.name.split(".")[0]
    folder, day, study, period, _ = load(root, day)
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refused(f"{path} cannot be read ({exc})") from None
    problems = problems_of(folder, study, period, doc)
    if not problems:
        folder.record_report({"date": day, "status": "final", "period": {"from": period["from"], "to": period["to"]},
                              "runs": period["runs"], "previous": (period.get("comparison") or {}).get("previous"),
                              "file": _shown(folder, path)})
        folder.record_outcome("written", f"deck of {day} passed check")
    return problems


# --- the page ---------------------------------------------------------------

def _of(a, b, t):
    return f"{a} {t['of']} {b}"


def _head(cells, subject):
    return "".join(f'<div class="head">{esc(c.format(subject=subject))}</div>' for c in cells)


def _swatch_heads(entries):
    return "".join(f'<div class="head">{f"""<i class="{kind}"></i>""" if kind else ""}{esc(label)}</div>' for kind, label in entries)


def _bar(parts):
    """A stacked bar. Its counts stand beside it, where a thin part cannot lose them."""
    segments = "".join(f'<span class="seg {kind}" style="flex: {n} 0 0"></span>' for n, kind in parts if n)
    return f'<div class="bar">{segments}</div>'


def _meter(a, b, small=False, rival=False):
    width = 100 * a / b if b else 0
    kind = ' class="rival"' if rival else ""
    return f'<div class="meter{" small-meter" if small else ""}"><span{kind} style="width: {width:.1f}%"></span></div>'


def _legend(entries):
    return '<div class="legend">' + "".join(f'<span><i class="{kind}"></i>{esc(label)}</span>' for kind, label in entries) + "</div>"


def _bands(m, t):
    return t["bands_fidelity" if m["fidelity"] else "bands"]


def _chart_legend(key, m, t):
    if key == "facts":
        parts = t["fact_parts"]
        return [("good", parts["current"]), ("low", parts["outdated"]), ("mid", parts["silent"])]
    bands = _bands(m, t)
    return [("good", bands["4-5"]), ("mid", bands["3"]), ("low", bands["1-2"])]


def _fact_label(row, t, lang):
    source = (row.get("source") or "").replace("https://", "").replace("www.", "").rstrip("/")
    small = ""
    if source and row.get("date") and row.get("key") is None:
        where = t["fact_source"].format(source=source, date=fmt_date(row["date"], lang))
        asked = f' · {t["fact_from"].format(n=row["asked"])}' if row.get("asked", 0) > 1 else ""
        small = f'<small>{esc(where + asked)}</small>'
    return f'<div>{esc(row["label"])}{small}</div>'


def _rows(key, rows, t, lang, m, grouped, excerpts):
    subject = m["subject"]
    long = " long" if any(len(r["label"]) > 60 for r in rows) else ""
    height = len(rows) + 2 * excerpts + (len({r["project"] for r in rows}) if grouped else 0)
    few = " few" if len(rows) <= 3 else " dense" if height > 8 else ""
    head = list(t["description_head_fidelity" if key == "description" and m["fidelity"] else f"{key}_head"])
    if rows and rows[0].get("key"):
        head[0] = t["question_head"]
    bands = _bands(m, t)
    if key == "description":
        head_html = _head(head, subject) + _swatch_heads(_chart_legend(key, m, t))
    elif key == "facts":
        parts = t["facts_heads"]
        head_html = _head(head, subject) + _swatch_heads([("good", parts["current"]), ("low", parts["outdated"]),
                                                         ("mid", parts["silent"]), ("", parts["favourable"])])
    else:
        head_html = _head(head, subject)
    out, group = [head_html], None
    for row in rows:
        if grouped and row["project"] != group:
            group = row["project"]
            out.append(f'<div class="group">{esc(group)}</div>')
        label = f'<div>{esc(row["label"])}</div>'
        if key == "reach":
            foils = ", ".join(f"{name} {n}" for name, n in row["foils"]) or t["none"]
            out.append(f'{label}{_meter(row["named"], row["given"])}'
                       f'<div class="fig">{_of(row["named"], row["given"], t)}</div><div class="foils">{esc(foils)}</div>')
        elif key == "description":
            b = row["bands"]
            out.append(f'{label}{_bar([(b["4-5"], "good"), (b["3"], "mid"), (b["1-2"], "low")])}'
                       f'<div class="fig">{_of(b["4-5"], row["judged"], t)}</div>'
                       f'<div class="fig">{b["3"]}</div><div class="fig">{b["1-2"]}</div>')
        else:
            out.append(f'{_fact_label(row, t, lang)}{_bar([(row["current"], "good"), (row["outdated"], "low"), (row["silent"], "mid")])}'
                       f'<div class="fig">{_of(row["current"], row["given"], t)}</div>'
                       f'<div class="fig">{row["outdated"]}</div><div class="fig">{row["silent"]}</div>'
                       f'<div class="fig">{_of(row["bands"]["4-5"], row["judged"], t)}</div>')
    grid = f'<div class="rows {key}-rows{long}{few}">' + "".join(out) + "</div>"
    behind = "".join(_old_pages(r, subject, t) for r in rows if key == "facts")
    return f'<div class="chart">{grid}{behind}</div>'


def _old_pages(row, subject, t):
    """Where the old term comes from, by who wrote the page: the reader can act on some of them and not on others."""
    found = [(kind, pages) for kind, pages in (row.get("telling") or {}).items() if pages]
    if not found:
        return ""
    lists = " ".join(f'{t["fact_authors"][kind].format(subject=subject)}: {_listed_pages(pages)}.' for kind, pages in found)
    return f'<p class="note">{esc(t["fact_sites"].format(n=row["outdated"]))} {esc(lists)}</p>'


def _public(name, names):
    """An assistant as the reader knows it: its maker, then its name."""
    for full in names.values():
        if name in (full, full.split(": ", 1)[-1]):
            return full.replace(": ", " ", 1)
    return name


def _rating(excerpt, m, key):
    """How the answer an excerpt comes from was rated: a reader of a favourable figure asks what such an answer says."""
    if key == "reach" or m.get("fidelity"):
        return None
    pieces = _pieces(excerpt.get("text") or "")
    scores = Counter(r["score"] for r in m["blocks"]["description"]["responses"] if _quoted_in(pieces, [_plain(r["answer"])]))
    if not scores:
        return None
    score = scores.most_common(1)[0][0]
    return "4-5" if score >= 4 else "3" if score >= 3 else "1-2"


def _quotes(excerpts, t, names, ratings=()):
    if not excerpts:
        return ""
    rated = [f' · {esc(t["rated"][r])}' if r else "" for r in ratings] or [""] * len(excerpts)
    cards = "".join(f'<figure class="quote"><blockquote>«{esc(e["text"])}»</blockquote><figcaption>'
                    f'<b>{esc(t["question"])}:</b> {esc(e["question"])}<br><b>{esc(t["assistant"])}:</b> {esc(_public(e["assistant"], names))}{mark}'
                    "</figcaption></figure>" for e, mark in zip(excerpts, rated))
    return f'<div class="quotes">{cards}</div>'


def _kicker(text):
    return f'<div class="kicker">{esc(text)}</div>' if text else ""


def _asked(doc, key):
    return ((doc.get("opening") or {}).get("questions") or {}).get(key) or ""


def _block_assistants(key, m):
    projects = {r["project"] for r in m["blocks"][key]["questions"]}
    return sorted({a for r in m["method"] if r["name"] in projects for a in r["assistants"]})


def _count_line(key, block, t):
    n = len(block["questions"])
    answers = sum(_measure(key, r)[1] for r in block["rows"])
    if key == "facts":
        return t["overlap"].format(n=n, answers=answers)
    return f'{n} {t["question_one" if n == 1 else "question_many"]}, {answers} {t["answer_many"]}'


def _spread(spread, t):
    """How many answers a question gives: few cases are counted, many are given as a range."""
    if len(spread) == 1:
        return t["spread_one"].format(n=spread[0][0])
    if len(spread) > 3:
        given = [n for n, _ in spread]
        return t["spread_range"].format(low=min(given), high=max(given))
    (n, q), rest = spread[0], spread[1:]
    return ", ".join([t["spread_first"].format(q=q, n=n)] +
                     [t["spread_rest_one" if q == 1 else "spread_rest"].format(q=q, n=n) for n, q in rest])


def _origins_line(m, t, lang):
    """Where the questions come from, in the order of the study's origin kinds."""
    known = t["origins"]
    found = [known[k].format(subject=m["subject"]) for k in known if k in m["origins"]]
    return t["origins_line"].format(origins=join(found, lang)) if found else ""


def _reading_key(m):
    """"Some several times" is false of questions that all have more answers than assistants."""
    if m["totals"]["assistants"] == 1:
        return "reading_answers_one"
    always = min(n for n, _ in m["spread"]) > max(len(r["assistants"]) for r in m["method"])
    return "reading_answers_always" if always else "reading_answers"


def _opening_slide(doc, m, t, lang, list_slides):
    """What the report shows, before any finding: why it exists, what it answers, what was asked, how to read a figure."""
    subject, examples = m["subject"], (doc.get("opening") or {}).get("examples") or {}
    cards = ""
    for key in present(m):
        block = m["blocks"][key]
        texts = {r.get("key"): r["label"] for r in block["questions"]}
        shown = "".join(f"<li>«{esc(texts[k])}»</li>" for k in examples.get(key) or [] if k in texts)
        cards += (f'<div class="card"><div class="card-q">{esc(_asked(doc, key))}</div>'
                  f'<div class="card-count">{esc(_count_line(key, block, t))}<br>'
                  f'{esc(t["card_assistants"].format(assistants=", ".join(_block_assistants(key, m))))}</div>'
                  f'<ul class="card-ex">{shown}</ul></div>')
    each = sorted({len(r["assistants"]) for r in m["method"]})
    few = ", ".join(str(n) for n in each[:-1]) + f' {t["or"]} {each[-1]}' if len(each) > 1 else str(each[0])
    lines = [t[_reading_key(m)].format(spread=_spread(m["spread"], t), few=few),
             t["reading_assistants"].format(assistants=m["makers"]),
             t["reading_scores"].format(bands=t["bands_line_fidelity" if m["fidelity"] else "bands_line"].format(subject=subject))]
    if m["first"]:
        lines.append(t["reading_first"])
    first, last = list_slides
    lines.append(t["reading_list"].format(n=first) if first == last else t["reading_list_many"].format(n=first, last=last))
    origins = _origins_line(m, t, lang)
    lines = ([origins] if origins else []) + lines
    purpose = f'<p class="read"><b>{esc(t["purpose"])}:</b> {esc(m["purpose"])}</p>' if m["purpose"] else ""
    size = " three" if len(present(m)) > 2 else ""
    return (f'<h1>{esc(t["opening_title"])}</h1>{purpose}<div class="cards{size}">{cards}</div><div class="reading">'
            f'<h2>{esc(t["reading_title"])}</h2><ul>' + "".join(f"<li>{esc(x)}</li>" for x in lines) + "</ul></div>")


def _only_assistant(key, m):
    """The assistant of a block whose answers all come from one, as the reader knows it."""
    asked = _block_assistants(key, m)
    return _public(asked[0], m["names"]) if len(asked) == 1 else None


def _close(f, subject, t):
    """Names a few answers from the subject: a position they could swap with it says less than its number."""
    margin = max(2, round(f["b"] * CLOSE_SHARE))
    near = [(n, c) for n, c in f["rivals"] if abs(c - f["a"]) <= margin]
    if not near or not f["a"]:
        return ""
    names = f' {t["and"]} '.join(filter(None, [", ".join(n for n, _ in near[:-1]), near[-1][0]]))
    return t["close" if len(near) > 1 else "close_one"].format(names=names, subject=subject,
                                                             gap=max(abs(c - f["a"]) for _, c in near))


def _versus(f, subject, t, only=None):
    """The subject beside the names the same answers carry: the five named most, the subject among them."""
    names = sorted([(subject, f["a"], True)] + [(n, c, False) for n, c in f["rivals"]], key=lambda x: (-x[1], not x[2]))
    top = names[:5]
    if not any(me for _, _, me in top):
        top = names[:4] + [next(x for x in names if x[2])]
    rows = "".join(f'<div class="{"me" if me else ""}">{esc(name)}</div>{_meter(n, f["b"], rival=not me)}'
                   f'<div class="fig{" me" if me else ""}">{n}</div>' for name, n, me in top)
    caption = [_close(f, subject, t), t["versus"].format(b=f["b"]), t["left_out"] if f["left_out"] else "",
               t["one_assistant"].format(assistant=only) if only else ""]
    shown = len(top) if any(me for _, _, me in names[:5]) else 4
    rank = t["rank" if any(me for _, _, me in names[:5]) else "rank_below"].format(subject=subject, rank=f["rank"],
                                                                                 field=f["names"], shown=shown)
    label = f'<div class="card-cap"><b>{esc(f["project"])}</b></div>' if f["project"] else ""
    return f'{label}<div class="versus">{rows}</div><div class="card-cap"><b>{esc(rank)}</b> {esc(" ".join(caption).strip())}</div>'


def _visual(key, m, t):
    block, subject = m["blocks"][key], m["subject"]
    if key == "reach":
        return "".join(_versus(f, subject, t, _only_assistant(key, m)) if f["rivals"] else
                       f'<div class="card-fig">{f["a"]} <small>{t["of"]} {f["b"]}</small></div>' for f in block["figures"])
    caption = t["card"]["description_fidelity" if key == "description" and m["fidelity"] else key].format(subject=subject)
    labels = dict(_chart_legend(key, m, t))
    shown = "".join(f'<div class="card-fig">{f["a"]} <small>{t["of"]} {f["b"]}</small>'
                    + (f' <span>{esc(f["project"])}</span>' if f["project"] else "") + f'</div>{_bar(f["parts"])}'
                    + _legend([(kind, f"{labels[kind]}: {n}") for n, kind in f["parts"]]) for f in block["figures"])
    return f'<div class="card-cap">{esc(caption)}</div>{shown}'


def _found_slide(doc, m, t):
    found = doc.get("found") or {}
    answers = found.get("answers") or {}
    cards = "".join(f'<div class="card {key}"><div class="card-q">{esc(_asked(doc, key))}</div>'
                    f'<p class="card-a">{esc(answers.get(key) or "")}</p><div class="card-visual">{_visual(key, m, t)}</div></div>'
                    for key in present(m))
    pair = " pair" if len(present(m)) == 2 else ""  # two cards leave room: larger type, not a hole in the card
    return f'{_kicker(t["found_kicker"])}<h1>{esc(found.get("title"))}</h1><div class="cards{pair}">{cards}</div>'


def _question_pages(m, t):
    """The questions, two columns a slide. A last page holding a few stray lines is drawn tighter, so it goes."""
    pages = _flow_questions(m, t, COLUMN_LINES)
    if len(pages) > 1 and len(pages[-1]) == 1 and len(pages[-1][0]) <= 6:
        tight = _flow_questions(m, t, TIGHT_LINES)
        if len(tight) < len(pages):
            return [[["tight"] + column for column in page] for page in tight]
    return pages


def _flow_questions(m, t, capacity):
    """Columns of at most `capacity` lines; a heading stays with what follows it."""
    items = []
    for key in present(m):
        placed = m["blocks"][key]["placed"]
        if placed:
            items.append(("q-group", t["groups"][key].format(subject=m["subject"]), 1.6))
        theme = None
        for q in placed:
            if q["dimension"] != theme:
                theme = q["dimension"]
                items.append(("q-theme", theme, 1.3))
            items.append(("q-line", q["text"], 1 + len(q["text"]) // LINE_CHARS))
    columns, column, used = [], [], 0
    for n, (kind, text, lines) in enumerate(items):
        need, ahead = lines, n
        while items[ahead][0] != "q-line" and ahead + 1 < len(items):
            ahead += 1
            need += items[ahead][2]
        if column and used + need > capacity:
            columns.append(column)
            column, used = [], 0
        column.append((kind, text))
        used += lines
    if column:
        columns.append(column)
    return [columns[i:i + 2] for i in range(0, len(columns), 2)]


def _questions_slide(page, n, pages, m, t):
    total = sum(len(m["blocks"][b]["placed"]) for b in present(m))
    title = t["questions_title"].format(n=total) if pages == 1 else t["questions_more"].format(n=total, page=n, pages=pages)
    tight = any(column[0] == "tight" for column in page)
    cols = "".join("<div>" + "".join(f'<div class="{entry[0]}">{esc(entry[1])}</div>' for entry in column if entry != "tight") + "</div>"
                   for column in page)
    return f'<h1>{esc(title)}</h1><div class="question-cols{" tight" if tight else ""}">{cols}</div>'


def _order(doc, m, t):
    """The slides in reading order: (kind, block, slide)."""
    second = m.get("second")
    order = [("cover", None, None), ("opening", None, None), ("found", None, None)]
    order += [("changed", None, None)] * bool(second and second["rows"]) + [("earlier", None, None)] * bool(second)
    order.append(("actions", None, None))
    for key in present(m):
        order += [(key, key, s) for s in (doc.get("blocks") or {}).get(key) or []]
    if _any_sources(m):
        order.append(("sources", None, None))
    order.append(("method", None, None))
    return order + [("questions", None, page) for page in _question_pages(m, t)]


def _evidence(order, action, n):
    return next((i for i, (_, key, s) in enumerate(order, 1) if key == action.get("block") and s.get("action") == n),
                next((i for i, (_, key, _s) in enumerate(order, 1) if key == action.get("block")), ""))


def _slide_answers(key, slide, m):
    """The answers to the questions a slide draws."""
    block = m["blocks"][key]
    rows = rows_of(key, block, slide)
    keys = {r.get("key") for r in rows} - {None}
    topics = {d for r in rows if not r.get("key") for d in _dimensions(r)}
    return [r for q in block["questions"] if q.get("key") in keys or set(_dimensions(q)) & topics
            for r in m["answers_of"].get(q.get("key"), []) if r["answer"] is not None]


def _site_counts(action, n, doc, m):
    """Each third party an action names, with the answers to the questions of its slide that cite it and those answers'
    total. On the facts slide the pages say it."""
    key = action.get("block")
    slide = next((s for s in (doc.get("blocks") or {}).get(key) or [] if s.get("action") == n), None)
    if slide is None or key not in m["blocks"] or key == "facts":
        return []
    answers = _slide_answers(key, slide, m)
    def on_site(source, site):
        return bool(source.get("domain")) and is_owned(source["domain"], [site])

    found = []
    for site in dict.fromkeys(map(str.lower, DOMAIN.findall(action.get("what") or ""))):
        if m["author"](site) != "owned":
            pages = Counter(p for r in answers for p in {cited_page(s) for s in r["sources"] if on_site(s, site)} if "/" in p)
            found.append((site, sum(any(on_site(s, site) for s in r["sources"]) for r in answers), len(answers),
                          min(pages.items(), key=lambda kv: (-kv[1], kv[0])) if pages else None))
    return found


def _page_seen(record, action, m, t):
    """What the page an action asks shows, so that the reader needs not open it to know why."""
    url, shows = _address(record["url"]), record["shows"]
    if action.get("class") == "wrong_fact":
        return t["action_shows"].format(url=url, term="», «".join(shows))
    listed = any(m["subject"].lower() in s.lower() for s in shows)
    return t["action_lists_with" if listed else "action_lists"].format(url=url, names=", ".join(shows[:PAGE_NAMES]), subject=m["subject"])


def _why_site(action, n, doc, m, t, slide=None, page=False):
    """Why that site: how many answers on the action's slide cite it and, on that slide, what its page shows or, for a page
    the reader checks, the page they cite most."""
    where = t["action_there"].format(slide=slide) if slide else t["action_here"]
    seen = [p for p in action.get("pages") or [] if p.get("shows")]
    lines = []
    for site, citing, total, top in _site_counts(action, n, doc, m):
        lines.append(t["action_site"].format(site=site, n=citing, y=total, where=where))
        if page and top and not any(site in _address(p.get("url") or "") for p in seen):
            lines.append(t["action_page"].format(page=top[0], n=top[1]))
    if page:
        lines += [_page_seen(p, action, m, t) for p in seen]
    return " ".join(lines)


def _numbers(doc, m):
    """{place in the file: number on the page}. The subject's own pages come first: they depend on the reader alone, and a
    ranking by a weight nobody sees earns "why this one first?"."""
    actions = doc.get("actions") or []
    ranked = sorted(range(1, len(actions) + 1), key=lambda n: _is_third(actions[n - 1], m["author"]))
    return {n: shown for shown, n in enumerate(ranked, 1)}


def _actions_note(doc, m, t):
    kinds = {_is_third(a, m["author"]) for a in doc.get("actions") or []}
    order = t["actions_order"].format(subject=m["subject"]) + " " if kinds == {True, False} else ""
    return order + t["actions_note"]


def _actions_table(doc, order, m, t):
    head = "".join(f"<th>{esc(c)}</th>" for c in t["actions_head"])
    rows = ""
    numbers = _numbers(doc, m)
    for n in sorted(numbers, key=numbers.get):
        a = doc["actions"][n - 1]
        slide = _evidence(order, a, n)
        site = _why_site(a, n, doc, m, t, slide=slide)
        site = f'<br><span class="site-why">{esc(site)}</span>' if site else ""
        rows += (f'<tr><td class="num">{numbers[n]}</td><td>{esc(a.get("what"))}</td><td>{esc(a.get("why"))}{site}</td>'
                 f'<td class="num">{slide}</td></tr>')
    return f"<table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>"


def _sources_table(doc, m, t, subject):
    head = "".join(f"<th>{esc(c.format(subject=subject))}</th>" for c in t["sources_head"])
    named = " ".join(a.get("what") or "" for a in doc.get("actions") or [])
    rows, told = [], False
    for key in present(m):
        s = m["blocks"][key]["sources"]
        if not s["with_sources"]:
            continue
        n = s["answers"]
        cells = "".join(f'<td><span class="fig">{_of(s[k], n, t)}</span>{_meter(s[k], n, True)}</td>' for k in ("owned", "foil", "third"))
        # A site an action names is on the slide, whatever its rank: the reader asks why that one.
        shown = {d["domain"]: d["answers"] for d in s["third_domains"]}
        shown.update({d: n for d, n in s["third_all"].items() if d in named})
        naming = (s.get("third_naming") or {}) if key == "reach" else {}
        told = told or bool(naming)
        domains = ", ".join(t["site_naming"].format(domain=d, n=n, k=naming[d], subject=subject) if d in naming else f"{d} ({n})"
                            for d, n in shown.items()) or t["none"]
        rows.append(f'<tr><td class="class">{esc(t["groups"][key].format(subject=subject))}</td>{cells}<td>{esc(domains)}</td></tr>')
    table = f'<table><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'
    pages = Counter()
    for key in present(m):
        pages.update(dict(m["blocks"][key]["sources"]["owned_pages"]))
    cited = ", ".join(f"{p} ({n})" for p, n in sorted(pages.items(), key=lambda kv: (-kv[1], kv[0]))[:4])
    note = t["site_naming_note"].format(subject=subject) + " " if told else ""
    note += t["owned_pages"].format(subject=subject, pages=cited) if cited else ""
    return table + (f'<p class="note">{esc(note.strip())}</p>' if note else "")


def _method(doc, m, t):
    head = "".join(f"<th>{esc(c)}</th>" for c in t["method_head"])
    rows = "".join(f'<tr><td class="class">{esc(r["name"])}</td><td class="num">{r["questions"]}</td>'
                   f'<td>{esc(", ".join(r["assistants"]))}</td><td class="num">{r["answers"]}</td>'
                   f'<td>{esc(t["frequency"].get(r["schedule"], ""))}</td></tr>' for r in m["method"])
    method = doc.get("method") or {}
    limits = [t["limit_versions"]] + (method.get("limits") or [])
    scores = t["scores"].format(line=t["bands_line_fidelity" if m["fidelity"] else "bands_line"].format(subject=m["subject"]))
    if len({tuple(r["assistants"]) for r in m["method"]}) > 1:
        scores += " " + t["scope_note"]
    left = f'<h2>{esc(t["scores_title"])}</h2><p>{esc(scores)}</p>'
    left += f'<h2>{esc(t["limits_title"])}</h2><ul>' + "".join(f"<li>{esc(x)}</li>" for x in limits) + "</ul>"
    monitored = f'<h2>{esc(t["monitored_title"])}</h2><p>{esc(", ".join(m["monitored"]))}</p>' if m["monitored"] else ""
    right = (f'{monitored}<h2>{esc(t["where_title"])}</h2><p>{esc(t["where"])}</p><h2>{esc(t["ask_title"])}</h2><ul>'
             + "".join(f"<li>{esc(x)}</li>" for x in method.get("ask") or []) + "</ul>")
    return (f'<h1>{esc(t["method_title"])}</h1><table><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
            f'<div class="method-cols"><div>{left}</div><div>{right}</div></div>')


def _dates(doc, m, lang):
    return {"then": fmt_date(m["second"]["date"], lang), "now": fmt_date(doc["date"], lang)}


def _moved(row, t):
    if row["change"]:
        return t["changed_values"][row["change"]]
    if row["before"][0] * row["now"][1] == row["now"][0] * row["before"][1]:
        return t["changed_values"]["same"]
    return t["changed_values"]["small"].format(step=round(100 * STEPS["presence"][1]))


def _table(heads, rows, dates):
    head = "".join(f"<th>{esc(c.format(**dates))}</th>" for c in heads)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def _changed_slide(doc, m, t, lang):
    earlier, dates = doc.get("earlier") or {}, _dates(doc, m, lang)
    rows = [(esc(_asked(doc, r["block"])) + (f'<br><span class="site-why">{esc(r["project"])}</span>' if r["project"] else ""),
             _of(*r["before"], t), _of(*r["now"], t), esc(_moved(r, t))) for r in m["second"]["rows"]]
    return (f'{_kicker(t["changed_kicker"].format(**dates))}<h1>{esc(earlier.get("title"))}</h1><p class="read">{esc(earlier.get("read"))}</p>'
            f'{_table(t["changed_head"], rows, dates)}<p class="note">{esc(t["changed_note"])}</p>')


def _earlier_slide(doc, m, t, lang):
    earlier, dates = doc.get("earlier") or {}, _dates(doc, m, lang)
    rows = [(esc(a["what"]), esc(a["then"]), esc(now)) for a, now in zip(m["second"]["actions"], earlier.get("now") or [])]
    return (f'{_kicker(t["earlier_kicker"].format(**dates))}<h1>{esc(earlier.get("actions_title"))}</h1>'
            f'{_table(t["earlier_head"], rows, dates)}<p class="note">{esc(t["earlier_note"])}</p>')


def _slide_html(kind, key, slide, doc, m, order, t, lang):
    subject = m["subject"]
    if kind == "opening":
        lists = [i for i, entry in enumerate(order, 1) if entry[0] == "questions"]
        return _opening_slide(doc, m, t, lang, (lists[0], lists[-1]))
    if kind == "found":
        return _found_slide(doc, m, t)
    if kind == "changed":
        return _changed_slide(doc, m, t, lang)
    if kind == "earlier":
        return _earlier_slide(doc, m, t, lang)
    if kind == "actions":
        return (f'{_kicker(t["actions_kicker"])}<h1>{esc(doc.get("actions_title") or "")}</h1>{_actions_table(doc, order, m, t)}'
                f'<p class="note">{esc(_actions_note(doc, m, t))}</p>')
    if kind == "sources":
        sources = doc.get("sources") or {}
        return (f'{_kicker(t["sources_kicker"])}<h1>{esc(sources.get("title"))}</h1><p class="read">{esc(sources.get("read"))}</p>'
                + _sources_table(doc, m, t, subject))
    if kind == "method":
        return _method(doc, m, t)
    if kind == "questions":
        pages = [entry[2] for entry in order if entry[0] == "questions"]
        return _questions_slide(slide, pages.index(slide) + 1, len(pages), m, t)
    block = m["blocks"][key]
    rows = rows_of(key, block, slide)
    grouped = len({r["project"] for r in rows}) > 1 and not doc.get("same_audience")
    out = (f'{_kicker(_asked(doc, key))}<h1>{esc(slide.get("title"))}</h1><p class="read">{esc(slide.get("read"))}</p>'
           + _rows(key, rows, t, lang, m, grouped, len(slide.get("excerpts") or []))
           + _quotes(slide.get("excerpts"), t, m["names"], [_rating(e, m, key) for e in slide.get("excerpts") or []]))
    n = slide.get("action")
    if n is not None and 1 <= n <= len(doc.get("actions") or []):
        label = t["action"].format(n=_numbers(doc, m)[n])
        site = _why_site(doc["actions"][n - 1], n, doc, m, t, page=True)
        out += f'<div class="strip"><b>{esc(label)}:</b> {esc(doc["actions"][n - 1].get("what"))}{" " + esc(site) if site else ""}</div>'
    return out


def _cover_line(m, who, t):
    totals = m["totals"]
    assistants = t["assistant_one"] if totals["assistants"] == 1 else t["assistant_many"]
    return t["cover_what_repeated" if m["repeated"] else "cover_what"].format(questions=totals["questions"], assistants=assistants,
                                                                              who=who, answers=totals["answers"])


def _tight_units(text):
    """A figure and its unit stay on one line."""
    return re.sub(r"(?<=\d) (?=[€£$%])", "\u00a0", text)


def page_of(root, date=None, option=None):
    """(the deck as one HTML page, its slides)."""
    folder, date, study, period, doc = load(root, date)
    if doc is None:
        raise Refused(f"no deck for {date}: run deck --date {date} and write its text first")
    chosen, _ = sentl_theme.resolve(folder, option)
    lang = study["report_language"]
    t = DECK[lang]
    m = build_model(folder, study, period, doc)
    order = _order(doc, m, t)
    subject = m["subject"]
    days = span(period["from"], period["to"], lang)
    logo = f'<img src="{html.escape(chosen["logo"], quote=True)}" alt="">' if chosen.get("logo") else ""
    who = (doc.get("opening") or {}).get("who") or ""
    by = f'<div class="cover-line">{esc(t["cover_by"].format(by=m["by"]))}</div>' if m["by"] else ""
    cover = (f'<section class="slide cover"><div class="band"></div><div class="cover-body">{logo}'
             f'<h1>{esc(t["cover_title"].format(subject=subject))}</h1>'
             f'<div class="cover-what">{esc(_cover_line(m, who, t))}</div>'
             f'<div class="cover-kind">{esc(t["cover_first" if m["first"] else "cover_next"])} · {esc(days)}</div>{by}</div></section>')
    slides = [cover]
    for n, (kind, key, slide) in enumerate(order[1:], 2):
        foot = (f'<footer class="foot"><span>{logo}{esc(subject)} · {esc(days)}</span><span>{n} / {len(order)}</span></footer>')
        actions = len(doc.get("actions") or [])
        extra = (" few-actions" if actions <= 3 else " many-actions" if actions == MAX_ACTIONS else "") if kind == "actions" else ""
        slides.append(f'<section class="slide {kind}{extra}">{_slide_html(kind, key, slide, doc, m, order, t, lang)}{foot}</section>')
    font = f'<link rel="stylesheet" href="{html.escape(chosen["font_url"], quote=True)}">' if chosen.get("font_url") else ""
    style = sentl_theme.variables(chosen) + STYLE + (chosen.get("css") or "")
    text = (f'<!doctype html>\n<html lang="{html.escape(lang)}"><head><meta charset="utf-8"><title>{esc(subject)} · {esc(days)}</title>'
            f"{font}<style>{style}</style></head><body>\n" + "\n".join(slides) + "\n</body></html>\n")
    return _tight_units(text), len(order)


def pages(path):
    """The pages of a PDF: from pdfinfo where installed, otherwise from its page objects."""
    exe = shutil.which("pdfinfo")
    if exe:
        done = subprocess.run([exe, str(path)], capture_output=True, text=True)
        found = re.search(r"^Pages:\s+(\d+)", done.stdout, re.M)
        if found:
            return int(found.group(1))
    return len(re.findall(rb"/Type\s*/Page\b", Path(path).read_bytes()))


def _spilling(path, count, total):
    """The slides that run over their page, read from the numbers in the pages' feet, where pdftotext is installed."""
    exe = shutil.which("pdftotext")
    if not exe:
        return []
    out, last = [], 1
    for page in range(1, count + 1):
        text = subprocess.run([exe, "-f", str(page), "-l", str(page), str(path), "-"], capture_output=True, text=True).stdout
        found = re.search(rf"(\d+)\s*/\s*{total}\s*$", text.replace("\f", "").strip())
        if found:
            last = int(found.group(1))
        elif page > 1:
            out.append(last + 1)
    return sorted(set(out))


def render(root, date=None, option=None, printer=None, skip_check=False):
    """reports/<date>.deck.html and .pdf; the copy to send goes to reports/share/."""
    folder, date, study, period, doc = load(root, date)
    if doc is None:
        raise Refused(f"no deck for {date}: run deck --date {date} and write its text first")
    if not skip_check:
        found = problems_of(folder, study, period, doc)
        if found:
            raise Refused(f"the deck fails check on {len(found)} point(s): run check on it, then pdf --deck again")
    text, slides = page_of(root, date, option)
    target = folder.path("reports", f"{date}.deck.html")
    pdf = folder.path("reports", f"{date}.deck.pdf")
    write_text(target, text)
    engine, failures = (printer or report_pdf.print_pdf)(target, pdf, ENGINES)
    if not engine:
        why = "; ".join(failures) or "no PDF engine (chromium, google-chrome, weasyprint) is on this machine"
        return f"Wrote {target}. The PDF was not written ({why}): open the page in a browser and print it to PDF."
    count = pages(pdf)
    if count != slides:
        over = _spilling(pdf, count, slides)
        where = f" (slide {', '.join(map(str, over))} runs over)" if over else ""
        raise Refused(f"{count} pages for {slides} slides{where}: shorten the text of that slide, then pdf --deck again")
    name = report_pdf.share_name(folder, study, date, "monitoring deck")
    shared = folder.path("reports", "share")
    shared.mkdir(exist_ok=True)
    copy = shared / f"{name}.pdf"
    shutil.copyfile(pdf, copy)
    return f"Wrote {target} and {pdf} ({slides} slides, engine: {engine}). To send: {copy}"
