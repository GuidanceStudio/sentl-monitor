"""Fictional Sentl responses and study helpers shared by the unit tests.

The shapes follow what Sentl's MCP tools return (get-project-tool,
get-run-results-tool, list-ai-models); every name and text is invented.
"""

import contextlib
import copy
import gzip
import importlib.util
import io
import json
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MONITOR = REPO / "sentl-monitor" / "scripts" / "monitor.py"
_spec = importlib.util.spec_from_file_location("monitor", MONITOR)
monitor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(monitor)

GPT = "acme/chat-large"
GEM = "orbit/reason-pro"
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


def run(run_id=9001, started="2026-10-01T06:00:00Z", status="completed", score=3.1,
        overrides=None, rounds=1, extra=None):
    """A get-run-results-tool response. `overrides` maps (key, model) to a
    (answer, score, sentiment, urls) tuple; `extra` appends raw responses."""
    answers = dict(ANSWERS)
    answers.update(overrides or {})
    responses, rid = [], run_id * 100
    for _ in range(rounds):
        for (key, model), (answer, sc, sentiment, urls) in answers.items():
            dim, text = QUESTION_OF[key]
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


def models():
    return {"researcher_models": {
        GPT: {"name": "Acme Chat", "credits": 2},
        GEM: {"name": "Orbit Reason", "credits": 3},
    }}


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

    def cli(self, *args, check=None):
        """Run monitor.py's main() in-process; the result mimics a finished subprocess."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
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

    def adopt(self, run_data=None):
        self.cli("adopt", "--study", self.study, "--project", self.save("project.json", project()),
                 "--run", self.save("run-latest.json", run_data or run()), "--key", "brand", check=0)

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

    def ready(self, run_data=None, date="2026-10-31"):
        """Adopted, answered, ingested and with a period built for `date`."""
        self.adopt()
        self.answer_operator()
        self.ingest(run_data or run())
        self.cli("period", "--study", self.study, "--date", date, check=0)
