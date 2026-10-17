"""Fictional Sentl responses and study helpers shared by the unit tests.

The shapes follow what Sentl's MCP tools return (get-project-tool,
get-run-results-tool, list-ai-models); every name and text is invented.
"""

import contextlib
import copy
import datetime as dt
import gzip
import importlib.util
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "sentl-monitor" / "scripts" / "monitor.py"
_spec = importlib.util.spec_from_file_location("monitor", MONITOR)
monitor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(monitor)

GPT = "acme/chat-large"
GEM = "orbit/reason-pro"
NEW = "zenith/answer-max"
RETIRED = "oldco/legacy-7b"

# Each salute question names the brand in its text; the Italian apostrophe is
# typographic in the project and plain in the run on purpose (transcription).
PROJECT = {
    "project": {
        "id": 501,
        "name": "Avenello · Con il marchio",
        "organization": "example-org",
        "schedule_frequency": "weekly",
        "rounds": 1,
        "is_active": True,
        "researcher_model_ids": [GPT, GEM],
        "latest_run": {"id": 9001, "status": "completed"},
        "dimensions": [
            {"id": 11, "name": "Salute", "color": "#000000", "sort": 1, "archived": False,
             "questions": [
                 {"id": 101, "label": "Avenello fa male",
                  "question": "Il latte d’avena Avenello fa male?",
                  "grading_rubric": {"1": "Dice che fa male senza fonti", "2": "Riporta rischi non verificati",
                                     "3": "Risposta neutra", "4": "Dice che non fa male", "5": "Dice che non fa male con fonti"},
                  "additional_instructions": "Fatto: Avenello contiene 3 g di zuccheri per 100 ml (avenello.example, 2026-10-01)."},
                 {"id": 102, "label": "Avenello fa bene",
                  "question": "Il latte d'avena Avenello fa bene alla salute?",
                  "grading_rubric": {"1": "Lo sconsiglia", "2": "Dubbi prevalenti",
                                     "3": "Neutra", "4": "Positiva", "5": "Positiva con fonti"},
                  "additional_instructions": ""},
             ]},
            {"id": 12, "name": "Prezzo", "color": "#111111", "sort": 2, "archived": False,
             "questions": [
                 {"id": 103, "label": "Prezzo Avenello",
                  "question": "Quanto costa il latte d'avena Avenello rispetto al latte vaccino?",
                  "grading_rubric": {"1": "Prezzo sbagliato", "2": "Prezzo vago",
                                     "3": "Prezzo indicativo", "4": "Prezzo corretto", "5": "Prezzo corretto con fonte"},
                  "additional_instructions": ""},
             ]},
            {"id": 13, "name": "Confezione", "color": "#222222", "sort": 3, "archived": True,
             "questions": [
                 {"id": 104, "label": "Confezione Avenello",
                  "question": "La confezione di Avenello è riciclabile?",
                  "grading_rubric": {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e"},
                  "additional_instructions": ""},
             ]},
        ],
    }
}

ANSWERS = {
    ("salute-1", GPT): ("Il latte d'avena Avenello non fa male: contiene fibre di avena ed è più leggero del latte vaccino.",
                        4, "positive", ["https://www.avenello.example/prodotti", "https://salute.example/avena"]),
    ("salute-1", GEM): ("Il latte vaccino resta la scelta più studiata; tra le bevande all'avena c'è anche Avenello, ma alcuni prodotti contengono zuccheri aggiunti.",
                        2, "negative", ["https://salute.example/zuccheri"]),
    ("salute-2", GPT): ("Sì, Avenello fa bene alla salute se consumato con moderazione.",
                        5, "positive", ["https://shop.avenello.example/offerte"]),
    ("salute-2", GEM): ("Le bevande all'avena possono far parte di una dieta varia.",
                        4, "positive", []),
    ("prezzo-1", GPT): ("Avenello costa circa il doppio del latte vaccino al litro.",
                        3, "neutral", ["https://prezzi.example/avena"]),
    ("prezzo-1", GEM): ("Le bevande vegetali costano in media più del latte di mucca.",
                        2, "negative", ["https://prezzi.example/latte", "https://prezzi.example/avena"]),
}

QUESTION_OF = {
    "salute-1": ("Salute", "Il latte d'avena Avenello fa male?"),
    "salute-2": ("Salute", "Il latte d'avena Avenello fa bene alla salute?"),
    "prezzo-1": ("Prezzo", "Quanto costa il latte d'avena Avenello rispetto al latte vaccino?"),
}


def project():
    return copy.deepcopy(PROJECT)


DEFAULT_ANSWER = ("Avenello è una bevanda all'avena senza lattosio.", 3, "neutral", ["https://guida.example/avena"])


def run(run_id=9001, started="2026-10-01T06:00:00Z", status="completed", score=3.1,
        overrides=None, rounds=1, extra=None, models=None, texts=None):
    """A get-run-results-tool response. `overrides` maps (key, model) to a
    (answer, score, sentiment, urls) tuple; `extra` appends raw responses.
    `models` picks the models that answer (a model ANSWERS lacks gives
    DEFAULT_ANSWER); `texts` maps a key to the wording the run asked."""
    if models is None:
        answers = dict(ANSWERS)
    else:
        answers = {(key, m): ANSWERS.get((key, m), DEFAULT_ANSWER) for key in QUESTION_OF for m in models}
    answers.update({k: v for k, v in (overrides or {}).items() if models is None or k[1] in models})
    responses, rid = [], run_id * 100
    for _ in range(rounds):
        for (key, model), (answer, sc, sentiment, urls) in answers.items():
            dim, text = QUESTION_OF[key]
            text = (texts or {}).get(key, text)
            rid += 1
            responses.append({
                "id": rid, "model_id": model, "question": text, "dimension": dim,
                "answer": answer, "judge_score": sc, "sentiment": sentiment,
                "sources": [{"title": u.rsplit("/", 1)[-1], "url": u} for u in urls],
            })
    responses.extend(extra or [])
    return {"run": {
        "id": run_id, "project_id": 501, "organization": "example-org", "status": status,
        "trigger": "scheduled", "reputation_score": score, "error": None,
        "started_at": started, "finished_at": started.replace("T06", "T07"),
        "responses": responses,
    }}


# A second fictional project for the insights: a price fact, a question naming no brand,
# an employer question, and a competitor (Avoria) with its own domain.
PRICE_Q = "Quanto costa un litro di latte d'avena Avenello?"
CHOICE_Q = "Qual è la migliore bevanda all'avena da comprare?"
WORK_Q = "Com'è lavorare da Avenello?"
MARKET_DIMS = [(31, "Prezzo", [(801, PRICE_Q)]), (32, "Scelta", [(802, CHOICE_Q)]), (33, "Lavoro", [(803, WORK_Q)])]
QUESTION_DIM = {PRICE_Q: "Prezzo", CHOICE_Q: "Scelta", WORK_Q: "Lavoro"}
PRICE_TERMS = {"current": ["2,10 €"], "outdated": ["1,90 €"]}
AVORIA = {"id": "avoria", "label": "Avoria", "aliases": ["Avoria"], "domains": ["avoria.example"]}


def market_project(rounds=1):
    rubric = {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e"}
    return {"project": {
        "id": 601, "name": "Avenello · Mercato", "organization": "example-org", "schedule_frequency": "daily",
        "rounds": rounds, "is_active": True, "researcher_model_ids": [GPT, GEM],
        "dimensions": [{"id": did, "name": name, "archived": False,
                        "questions": [{"id": qid, "label": text[:40], "question": text, "grading_rubric": rubric,
                                       "additional_instructions": ""} for qid, text in questions]}
                       for did, name, questions in MARKET_DIMS]}}


def results(run_id, started, rows, project_id=601, score=None):
    """A get-run-results-tool response from rows of (question, model, answer, score, urls);
    a url may be a (url, title) pair."""
    responses = []
    for n, (question, model, answer, sc, urls) in enumerate(rows, 1):
        sources = []
        for v in urls:
            url, title = v if isinstance(v, tuple) else (v, v.rsplit("/", 1)[-1])
            sources.append({"url": url, "title": title})
        responses.append({"id": run_id * 100 + n, "model_id": model, "question": question,
                          "dimension": QUESTION_DIM[question], "answer": answer, "judge_score": sc,
                          "sentiment": "neutral" if sc is None else "positive", "sources": sources})
    return {"run": {"id": run_id, "project_id": project_id, "organization": "example-org", "status": "completed",
                    "trigger": "scheduled", "reputation_score": score, "error": None, "started_at": started,
                    "finished_at": started, "responses": responses}}


def models():
    return {"researcher_models": {
        GPT: {"name": "Acme Chat", "credits": 2},
        GEM: {"name": "Orbit Reason", "credits": 3},
        NEW: {"name": "Zenith Answer", "credits": 1},
    }}


def weekly(first, count, hour="06"):
    """`count` start times seven days apart from the date `first`."""
    day = dt.date.fromisoformat(first)
    return [f"{day + dt.timedelta(days=7 * n)}T{hour}:00:00Z" for n in range(count)]


@contextlib.contextmanager
def clock(when):
    """Every sentlmon module reads `when` as the current time."""
    with contextlib.ExitStack() as stack:
        for name, module in list(sys.modules.items()):
            if name.startswith("sentlmon") and hasattr(module, "now_iso"):
                stack.enter_context(mock.patch.object(module, "now_iso", lambda: when))
        yield


OPERATOR = {
    "narrative": {
        "research_question": "Cosa viene detto a chi chiede a un assistente AI di Avenello?",
        "purpose": "Sapere cosa dicono gli assistenti AI di Avenello, per decidere quali pagine scrivere.",
        "audience": {"choice": "generic_consumer", "reason": "Le domande sono quelle di un consumatore qualsiasi."},
        "criteria": {"by": "il team marketing di Avenello", "date": "2026-09-15"},
    },
    "subject": {"label": "Avenello", "kind": "brand", "aliases": ["Avenello"],
                "owned_domains": ["avenello.example"]},
    "foils": [{"id": "cow-milk", "label": "latte vaccino", "aliases": ["latte vaccino", "latte di mucca"]}],
    "market": {"country": "IT", "language": "it"},
    "report_language": "it",
    "report_every": "monthly",
}

ORIGINS = {
    "salute": [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"}],
    "prezzo": [{"kind": "client_material", "detail": "Listino 2026"}],
    "gusto": [{"kind": "client_issue", "detail": "Recensioni dei clienti, 2026"}],
}


class StudyCase:
    """Mixin: a temporary study folder and a CLI runner."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.study = Path(self._tmp.name) / "study"
        self.study.mkdir()
        (self.study / "inbox").mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def cli(self, *args, check=None, at=None):
        """Run monitor.py's main() in-process; the result mimics a finished subprocess.
        `at` is the time the commands read as now."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                (clock(at) if at else contextlib.nullcontext()):
            try:
                code = monitor.main([str(a) for a in args])
            except SystemExit as exc:
                code = exc.code
        proc = subprocess.CompletedProcess(args, code, out.getvalue(), err.getvalue())
        if check is not None:
            self.assertEqual(proc.returncode, check, proc.stdout + proc.stderr)
        return proc

    def save(self, name, data):
        path = self.study / "inbox" / name
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def read(self, rel):
        return json.loads((self.study / rel).read_text(encoding="utf-8"))

    def read_run(self, key, run_id):
        with gzip.open(self.study / "history" / "runs" / key / f"{run_id}.json.gz", "rt", encoding="utf-8") as fh:
            return json.load(fh)

    def adopt(self, run_data=None, at=None, project_data=None):
        self.cli("adopt", "--study", self.study, "--project", self.save("project.json", project_data or project()),
                 "--run", self.save("run-latest.json", run_data or run()), "--key", "brand", check=0, at=at)

    def detect(self, project_data, at, *extra, check=0):
        return self.cli("detect", "--study", self.study, "--project", "brand",
                        "--saved", self.save("project-now.json", project_data), *extra, check=check, at=at)

    def answer_operator(self, **changes):
        study = self.read("study.json")
        for field, value in OPERATOR.items():
            if field == "narrative":
                study["narrative"].update(copy.deepcopy(value))
            else:
                study[field] = copy.deepcopy(value)
        for theme in study["themes"]:
            theme["origins"] = copy.deepcopy(ORIGINS.get(theme["id"], []))
        study.update(changes)
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")

    def ingest(self, data, name="run.json", check=0):
        return self.cli("ingest", "--study", self.study, "--project", "brand",
                        "--results", self.save(name, data), check=check)

    def adopt_market(self, rows, at="2026-09-01T00:00:00Z", rounds=1, foils=(AVORIA,), terms=PRICE_TERMS,
                     report_every="monthly"):
        """The market project adopted, the operator's answers given, with price terms and foil domains."""
        self.cli("adopt", "--study", self.study, "--project", self.save("market.json", market_project(rounds)),
                 "--run", self.save("market-run.json", results(9000, "2026-08-31T06:00:00Z", rows)),
                 "--key", "market", check=0, at=at)
        self.answer_operator(report_every=report_every, foils=copy.deepcopy(list(foils)))
        study = self.read("study.json")
        for theme in study["themes"]:
            theme["origins"] = [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"}]
        price = study["projects"][0]["dimensions"][0]["questions"][0]
        if terms:
            price["facts"] = [{"fact": "Il prezzo al litro è 2,10 € dal 2026", "source": "https://avenello.example/prezzi",
                               "date": "2026-09-01", **copy.deepcopy(terms)}]
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False, indent=2), encoding="utf-8")

    def ingest_market(self, run_id, started, rows):
        return self.cli("ingest", "--study", self.study, "--project", "market",
                        "--results", self.save(f"m-{run_id}.json", results(run_id, started, rows)), check=0)

    def ingest_all(self, runs):
        for data in runs:
            self.ingest(data, name=f"run-{data['run']['id']}.json")

    def build(self, date, check=0):
        return self.cli("period", "--study", self.study, "--date", date,
                        "--models", self.save("models.json", models()), check=check)

    def publish(self, date, fill="le risposte descrivono Avenello", changes=None):
        """period, method, the changes in the answers written as `changes` and every other
        [[...]] marker filled with plain text, check: the report is final."""
        self.build(date)
        self.cli("method", "--study", self.study, "--date", date,
                 "--models", self.save("models.json", models()), check=0)
        path = self.study / "reports" / f"{date}.md"
        text = path.read_text(encoding="utf-8")
        if changes:
            from sentlmon.i18n import TEXT
            marker = TEXT[self.read("study.json")["report_language"]]["changes_marker"]
            self.assertIn(marker, text)
            text = text.replace(marker, changes)
        path.write_text(re.sub(r"\[\[[^\]]*\]\]", fill, text), encoding="utf-8")
        return self.cli("check", "--study", self.study, path, check=0)

    def period_file(self, date):
        return self.read(f"history/periods/{date}.json")

    def ready(self, run_data=None, date="2026-10-31"):
        """Adopted, answered, ingested and with a period built for `date`."""
        self.adopt()
        self.answer_operator()
        self.ingest(run_data or run())
        self.cli("period", "--study", self.study, "--date", date, check=0)
