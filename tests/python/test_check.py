import re
import unittest

from fixtures import GEM, GPT, StudyCase, models, run

FINDINGS = """### Salute: gli assistenti dicono che Avenello non fa male, con un dubbio sugli zuccheri

> Il latte d'avena Avenello non fa male: contiene fibre di avena ed è più leggero del latte vaccino.

Domanda «Il latte d’avena Avenello fa male?», Acme Chat. Fonti citate: salute.example, avenello.example.

> «tra le bevande all'avena c'è anche Avenello, ma alcuni prodotti contengono zuccheri aggiunti»

Domanda «Il latte d’avena Avenello fa male?», Orbit Reason.

La dimensione ha un punteggio medio di 3,8, su 4 risposte giudicate su 4. Avenello compare nel 75% delle risposte.

Per Avenello conviene una pagina sugli zuccheri, citata dalle fonti sulla salute.

### Prezzo: Avenello viene descritto come più caro del latte vaccino

> Avenello costa circa il doppio […] al litro.

Domanda «Quanto costa il latte d'avena Avenello rispetto al latte vaccino?», Acme Chat. Fonti citate: prezzi.example.

Punteggio medio 2,5; Avenello compare nel 50% delle risposte.

Per Avenello conviene pubblicare il prezzo al litro.
"""


class CheckTest(StudyCase, unittest.TestCase):

    def write_report(self, findings=FINDINGS, data=None):
        self.ready(data)
        self.cli("method", "--study", self.study, "--date", "2026-10-31",
                 "--models", self.save("models.json", models()), check=0)
        path = self.study / "reports" / "2026-10-31.md"
        text = path.read_text(encoding="utf-8")
        head, rest = text.split("## 6. ", 1)
        title, tail = rest.split("\n", 1)
        changes = tail[tail.index("## 7. "):]
        path.write_text(f"{head}## 6. {title}\n\n{findings}\n{changes}", encoding="utf-8")
        return path

    def check(self, path, code):
        return self.cli("check", "--study", self.study, path, check=code)

    def edit(self, path, old, new):
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def test_a_faithful_report_passes(self):
        proc = self.check(self.write_report(), 0)
        self.assertIn("pass", proc.stdout.lower())

    def test_the_skeleton_with_entries_left_to_write_fails(self):
        self.ready()
        self.cli("method", "--study", self.study, "--date", "2026-10-31",
                 "--models", self.save("models.json", models()), check=0)
        self.check(self.study / "reports" / "2026-10-31.md", 1)

    def test_a_paraphrased_quote_fails(self):
        path = self.write_report()
        self.edit(path, "> Il latte d'avena Avenello non fa male: contiene",
                  "> Il latte d'avena Avenello non è dannoso: contiene")
        self.assertIn("excerpt", self.check(path, 1).stdout.lower())

    def test_a_quote_joining_two_answers_fails(self):
        path = self.write_report()
        self.edit(path, "> Avenello costa circa il doppio […] al litro.",
                  "> Avenello costa circa il doppio […] se consumato con moderazione.")
        self.check(path, 1)

    def test_an_unknown_score_fails(self):
        path = self.write_report()
        self.edit(path, "punteggio medio di 3,8", "punteggio medio di 3,9")
        self.assertIn("3,9", self.check(path, 1).stdout)

    def test_an_unknown_percentage_fails(self):
        path = self.write_report()
        self.edit(path, "nel 75% delle", "nel 80% delle")
        self.assertIn("80%", self.check(path, 1).stdout)

    def test_a_figure_of_a_dimension_without_one_fails(self):
        data = run(rounds=2)
        next(r for r in data["run"]["responses"] if r["dimension"] == "Prezzo")["judge_score"] = None
        path = self.write_report(FINDINGS.replace("Punteggio medio 2,5", "Punteggio medio 2,3"), data=data)
        self.assertIn("2,3", self.check(path, 1).stdout)

    def test_a_run_id_fails(self):
        path = self.write_report()
        self.edit(path, "Per Avenello conviene pubblicare", "Nel run 9001, per Avenello conviene pubblicare")
        self.check(path, 1)

    def test_a_question_key_fails(self):
        path = self.write_report()
        self.edit(path, "Acme Chat. Fonti citate: prezzi", "Acme Chat (prezzo-1). Fonti citate: prezzi")
        self.assertIn("prezzo-1", self.check(path, 1).stdout)

    def test_a_model_id_fails(self):
        path = self.write_report()
        self.edit(path, "», Orbit Reason.", f"», {GEM}.")
        self.check(path, 1)

    def test_a_credit_figure_fails(self):
        path = self.write_report()
        self.edit(path, "Per Avenello conviene pubblicare", "Con 12 crediti, per Avenello conviene pubblicare")
        self.check(path, 1)

    def test_a_file_name_fails(self):
        path = self.write_report()
        self.edit(path, "Per Avenello conviene pubblicare", "Come in study.json, per Avenello conviene pubblicare")
        self.check(path, 1)

    def test_a_dimension_without_findings_fails(self):
        path = self.write_report(FINDINGS.split("### Prezzo")[0])
        self.assertIn("Prezzo", self.check(path, 1).stdout)

    def test_sections_out_of_order_fail(self):
        path = self.write_report()
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"(?=^## \d+\. )", text, flags=re.M)
        parts[2], parts[3] = parts[3], parts[2]
        path.write_text("".join(parts), encoding="utf-8")
        self.check(path, 1)

    def test_a_missing_section_fails(self):
        path = self.write_report()
        text = path.read_text(encoding="utf-8")
        parts = re.split(r"(?=^## \d+\. )", text, flags=re.M)
        del parts[2]
        path.write_text("".join(parts), encoding="utf-8")
        self.check(path, 1)

    def test_a_figure_of_another_dimension_fails(self):
        path = self.write_report()
        self.edit(path, "punteggio medio di 3,8", "punteggio medio di 2,5")
        self.assertIn("2,5", self.check(path, 1).stdout)

    def test_a_figure_in_a_findings_heading_fails(self):
        path = self.write_report()
        self.edit(path, "### Salute: gli assistenti", "### Salute: 3,8, gli assistenti")
        self.assertIn("heading", self.check(path, 1).stdout)

    def test_a_decimal_with_the_wrong_separator_fails(self):
        path = self.write_report()
        self.edit(path, "punteggio medio di 3,8", "punteggio medio di 3.8")
        self.assertIn("3.8", self.check(path, 1).stdout)

    def test_a_count_of_answers_not_in_the_period_fails(self):
        path = self.write_report()
        self.edit(path, "su 4 risposte giudicate su 4", "su 4 risposte giudicate su 9")
        self.assertIn("4 su 9", self.check(path, 1).stdout)

    def test_a_figure_in_guillemets_that_quote_nothing_fails(self):
        path = self.write_report()
        self.edit(path, "punteggio medio di 3,8", "punteggio medio di «3,9»")
        self.assertIn("3,9", self.check(path, 1).stdout)

    def test_a_failed_quote_says_where_it_stops_matching(self):
        path = self.write_report()
        self.edit(path, "> Il latte d'avena Avenello non fa male: contiene",
                  "> Il latte d'avena Avenello non è dannoso: contiene")
        self.assertIn("stops matching", self.check(path, 1).stdout)

    def test_quotes_match_across_non_breaking_hyphens_and_citation_markers(self):
        answer = "Avenello è senza\u2011glutine.[1] Costa poco al litro.[2][3]"
        data = run(overrides={("salute-2", GPT): (answer, 5, "positive", [])})
        path = self.write_report(FINDINGS + "\n", data=data)
        self.edit(path, "> Avenello costa circa il doppio […] al litro.",
                  "> Avenello costa circa il doppio […] al litro.\n\nDomanda «x», Acme Chat.\n\n"
                  "> Avenello è senza-glutine. Costa poco al litro.")
        self.check(path, 0)

    def test_an_assistant_name_with_a_version_number_is_not_a_figure(self):
        named = models()
        named["researcher_models"][GEM]["name"] = "Orbit Reason 4.7"
        named_file = self.save("models.json", named)
        self.adopt()
        self.answer_operator()
        self.ingest(run())
        self.cli("period", "--study", self.study, "--date", "2026-10-31", "--models", named_file, check=0)
        self.cli("method", "--study", self.study, "--date", "2026-10-31", "--models", named_file, check=0)
        path = self.study / "reports" / "2026-10-31.md"
        text = path.read_text(encoding="utf-8")
        head, rest = text.split("## 6. ", 1)
        title, tail = rest.split("\n", 1)
        findings = FINDINGS.replace("», Orbit Reason.", "», Orbit Reason 4.7.")
        path.write_text(f"{head}## 6. {title}\n\n{findings}\n{tail[tail.index('## 7. '):]}", encoding="utf-8")
        self.check(path, 0)

    def test_counts_and_dates_written_as_integers_pass(self):
        path = self.write_report()
        self.edit(path, "Per Avenello conviene pubblicare",
                  "Al 31 ottobre 2026, con 2 assistenti e 3 domande, per Avenello conviene pubblicare")
        self.check(path, 0)

    def test_the_project_figure_and_a_position_pass(self):
        path = self.write_report()
        self.edit(path, "Per Avenello conviene pubblicare",
                  "Il punteggio complessivo è 3,1 e Avenello compare in media in posizione 1,3; per Avenello conviene pubblicare")
        self.check(path, 0)


if __name__ == "__main__":
    unittest.main()
