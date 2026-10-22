"""The setup route's script: `payload` builds the arguments of the Sentl tools that write, keeping every
id of sentl.json, and `bind` records the ids and a `setup` version from a saved get-project-tool response."""

import copy
import json
import unittest

from design_study import clean_study
from fixtures import GEM, GPT, StudyCase, listing, models

from sentlmon.design import compose_instructions

KEY = "brand"
PROJECT_ID = 900
TOOLS = ("create-project-tool", "update-project-settings-tool", "save-project-questions-tool")


def sentl_project(study, key=KEY, project_id=PROJECT_ID, edit=None, first_id=1000):
    """The get-project-tool response of a project saved from study.json's project `key`, with ids
    allocated in sequence, as Sentl does. `edit` may change the response before it is returned."""
    project = next(p for p in study["projects"] if p["key"] == key)
    next_id = first_id
    dimensions = []
    for d in project["dimensions"]:
        did, next_id = next_id, next_id + 1
        questions = []
        for q in d["questions"]:
            qid, next_id = next_id, next_id + 1
            questions.append({"id": qid, "label": q["label"], "question": q["text"], "grading_rubric": dict(q["rubric"]),
                              "additional_instructions": compose_instructions(q.get("instructions"), q.get("facts"))})
        dimensions.append({"id": did, "name": d["name"], "archived": False, "questions": questions})
    data = {"project": {"id": project_id, "name": project["name"], "organization": "example-org",
                        "schedule_frequency": project["schedule"], "rounds": project["rounds"], "is_active": False,
                        "researcher_model_ids": list(project["models"]), "dimensions": dimensions}}
    if edit:
        edit(data["project"])
    return data


def empty_project(study, key=KEY, project_id=PROJECT_ID):
    return sentl_project(study, key, project_id, edit=lambda p: p.update(dimensions=[]))


class SetupCase(StudyCase, unittest.TestCase):

    def setUp(self):
        super().setUp()
        self.design = clean_study()
        self.write_study(self.design)
        self.models = self.save("models.json", models())

    def write_study(self, study):
        self.design = study
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")

    def payload(self, saved=None, runs=None, check=0, key=KEY):
        args = ["payload", "--study", self.study, "--project", key, "--models", self.models]
        if saved is not None:
            args += ["--saved", self.save("project-now.json", saved)]
        if runs is not None:
            args += ["--runs", self.save("runs-now.json", runs)]
        proc = self.cli(*args, check=check)
        return json.loads(proc.stdout) if proc.returncode == 0 else proc

    def bind(self, saved, *extra, check=0, at="2026-11-01T09:00:00Z"):
        return self.cli("bind", "--study", self.study, "--project", KEY, "--saved", self.save("project-now.json", saved),
                        *extra, check=check, at=at)

    def create_and_save(self):
        """The brand project created, bound while empty, its questions saved and bound again; returns what Sentl holds."""
        self.bind(empty_project(self.design))
        saved = sentl_project(self.design)
        self.bind(saved)
        return saved

    def no_runs(self, project_id=PROJECT_ID):
        return listing([], project_id)

    def question_args(self, saved, runs=None):
        return self.payload(saved, runs or self.no_runs())["save-project-questions-tool"]

    def study_question(self, key):
        return next(q for p in self.design["projects"] for d in p["dimensions"] for q in d["questions"] if q["key"] == key)


class PayloadForANewProject(SetupCase):

    def test_an_unbound_project_gets_only_create_arguments_that_leave_it_paused(self):
        out = self.payload()
        self.assertEqual(sorted(k for k in out if k in TOOLS), ["create-project-tool"])
        create = out["create-project-tool"]
        self.assertEqual(create, {"organization": "example-org", "name": "Avenello · With the brand",
                                  "researcher_model_ids": [GPT, GEM], "rounds": 1, "schedule_frequency": "weekly"})
        self.assertNotIn("is_active", create)

    def test_the_questions_wait_for_the_id_the_create_call_returns(self):
        self.assertTrue(any("bind" in n for n in self.payload()["notes"]))

    def test_payload_only_prints_and_writes_no_file(self):
        before = sorted(p.name for p in self.study.rglob("*") if p.is_file())
        self.payload()
        self.assertEqual(sorted(p.name for p in self.study.rglob("*") if p.is_file()), before)

    def test_a_study_that_fails_validate_is_refused(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["models"] = ["gone/model"]
        self.write_study(study)
        proc = self.payload(check=2)
        self.assertIn("gone/model", proc.stderr)

    def test_an_unknown_project_key_is_refused(self):
        self.assertIn("nope", self.payload(check=2, key="nope").stderr)


class PayloadForABoundProject(SetupCase):

    def setUp(self):
        super().setUp()
        self.saved = self.create_and_save()
        self.binding = self.read("sentl.json")["projects"][KEY]

    def test_every_dimension_and_question_keeps_its_id(self):
        args = self.question_args(self.saved)
        self.assertEqual(args["project_id"], PROJECT_ID)
        ids = {d["name"]: (d["id"], [q["id"] for q in d["questions"]]) for d in args["dimensions"]}
        for dkey, did in self.binding["dimensions"].items():
            dim = next(d for d in self.design["projects"][0]["dimensions"] if d["key"] == dkey)
            self.assertEqual(ids[dim["name"]][0], did)
            self.assertEqual(ids[dim["name"]][1], [self.binding["questions"][q["key"]] for q in dim["questions"]])

    def test_a_new_question_and_a_new_dimension_are_sent_without_an_id(self):
        study = copy.deepcopy(self.design)
        dims = study["projects"][0]["dimensions"]
        dims[0]["questions"].append({**copy.deepcopy(dims[0]["questions"][0]), "key": "health-3",
                                     "text": "Is Avenello oat milk safe for toddlers?", "pair": None})
        dims.append({"key": "packaging", "name": "Packaging", "search_lean": "none", "axis": "stance",
                     "questions": [{**copy.deepcopy(dims[0]["questions"][0]), "key": "packaging-1", "pair": None,
                                    "text": "Is the Avenello carton recyclable?", "framing": "neutral"}]})
        study["themes"].append({"id": "packaging", "label": "Packaging", "dimension": "packaging",
                                "origins": [{"kind": "client_issue", "detail": "Customer-service questions, 2026"}]})
        self.write_study(study)
        args = self.question_args(self.saved)
        health = next(d for d in args["dimensions"] if d["name"] == "Health")
        self.assertEqual([q.get("id") for q in health["questions"]][-1], None)
        self.assertNotIn("id", health["questions"][-1])
        self.assertTrue(all("id" in q for q in health["questions"][:-1]))
        packaging = args["dimensions"][-1]
        self.assertEqual(packaging["name"], "Packaging")
        self.assertNotIn("id", packaging)
        self.assertNotIn("id", packaging["questions"][0])

    def test_a_dropped_dimension_is_sent_archived_with_its_id_and_nothing_else(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"] = [d for d in study["projects"][0]["dimensions"] if d["key"] != "taste"]
        study["themes"] = [t for t in study["themes"] if t["id"] != "taste"]
        self.write_study(study)
        args = self.question_args(self.saved)
        self.assertIn({"id": self.binding["dimensions"]["taste"], "archived": True}, args["dimensions"])
        self.assertNotIn("Taste", [d.get("name") for d in args["dimensions"]])
        self.assertNotIn("delete_missing", args)

    def test_a_dimension_already_archived_in_sentl_is_still_sent_back_archived(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"] = [d for d in study["projects"][0]["dimensions"] if d["key"] != "taste"]
        study["themes"] = [t for t in study["themes"] if t["id"] != "taste"]
        self.write_study(study)
        taste_id = self.binding["dimensions"]["taste"]
        saved = copy.deepcopy(self.saved)
        next(d for d in saved["project"]["dimensions"] if d["id"] == taste_id)["archived"] = True
        self.bind(saved)
        args = self.question_args(saved)
        self.assertIn({"id": taste_id, "archived": True}, args["dimensions"])

    def test_delete_missing_is_never_set_and_a_question_left_out_is_listed_in_the_notes(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"][1]["questions"].pop()
        self.write_study(study)
        out = self.payload(self.saved, self.no_runs())
        self.assertNotIn("delete_missing", out["save-project-questions-tool"])
        self.assertNotIn("delete_missing", json.dumps(out["save-project-questions-tool"]))
        self.assertTrue(any("delete_missing" in n and "price-2" in n for n in out["notes"]), out["notes"])

    def test_dry_run_is_left_to_the_playbook(self):
        self.assertNotIn("dry_run", self.question_args(self.saved))

    def test_a_reworded_question_is_sent_with_its_id_and_its_new_text(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"][1]["questions"][0]["text"] = "What is the price of Avenello oat milk?"
        self.write_study(study)
        args = self.question_args(self.saved)
        price = next(q for d in args["dimensions"] if d.get("name") == "Price" for q in d["questions"])
        self.assertEqual(price["id"], self.binding["questions"]["price-1"])
        self.assertEqual(price["question"], "What is the price of Avenello oat milk?")

    def test_a_text_that_differs_from_sentls_only_by_quotes_or_spacing_is_sent_as_sentl_has_it(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"][0]["questions"][0]["text"] = "Is Avenello oat milk  bad for you?"
        self.write_study(study)
        saved = copy.deepcopy(self.saved)
        saved["project"]["dimensions"][0]["questions"][0]["question"] = "Is Avenello oat milk\u00a0bad for you?"
        saved["project"]["dimensions"][1]["questions"][1]["question"] = "Is Avenello\toat milk worth the price?"
        args = self.question_args(saved)
        self.assertEqual(args["dimensions"][0]["questions"][0]["question"], "Is Avenello oat milk\u00a0bad for you?")
        self.assertEqual(args["dimensions"][1]["questions"][1]["question"], "Is Avenello\toat milk worth the price?")

    def test_a_typographic_apostrophe_in_sentl_is_not_replaced_by_a_plain_one(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"][0]["questions"][0]["text"] = "Is Avenello's oat milk bad for you?"
        self.write_study(study)
        saved = copy.deepcopy(self.saved)
        saved["project"]["dimensions"][0]["questions"][0]["question"] = "Is Avenello’s oat milk bad for you?"
        self.bind(saved)
        args = self.question_args(saved)
        self.assertEqual(args["dimensions"][0]["questions"][0]["question"], "Is Avenello’s oat milk bad for you?")

    def test_the_judge_instructions_are_the_instructions_with_their_facts(self):
        args = self.question_args(self.saved)
        price = next(q for d in args["dimensions"] if d.get("name") == "Price" for q in d["questions"])
        q = self.study_question("price-1")
        self.assertEqual(price["additional_instructions"], compose_instructions(q["instructions"], q["facts"]))
        self.assertIn("Facts:", price["additional_instructions"])

    def test_settings_are_sent_only_when_they_differ_and_never_activate(self):
        self.assertNotIn("update-project-settings-tool", self.payload(self.saved, self.no_runs()))
        study = copy.deepcopy(self.design)
        study["projects"][0]["rounds"] = 3
        study["projects"][0]["models"] = [GPT]
        self.write_study(study)
        update = self.payload(self.saved, self.no_runs())["update-project-settings-tool"]
        self.assertEqual(update, {"project_id": PROJECT_ID, "name": "Avenello · With the brand", "researcher_model_ids": [GPT],
                                  "rounds": 3, "schedule_frequency": "weekly"})

    def test_an_edit_made_in_the_sentl_panel_since_the_last_version_is_refused(self):
        saved = copy.deepcopy(self.saved)
        saved["project"]["dimensions"][0]["questions"][0]["question"] = "Does Avenello oat milk harm you?"
        proc = self.payload(saved, self.no_runs(), check=2)
        self.assertIn("detect", proc.stderr)

    def test_a_saved_project_that_is_not_the_bound_one_is_refused(self):
        saved = copy.deepcopy(self.saved)
        saved["project"]["id"] = 12345
        self.payload(saved, listing([], 12345), check=2)

    def test_a_bound_project_needs_the_saved_project_and_the_run_listing(self):
        self.payload(None, self.no_runs(), check=2)
        self.payload(self.saved, None, check=2)


class PendingRunGuard(SetupCase):

    def setUp(self):
        super().setUp()
        self.saved = self.create_and_save()

    def test_a_completed_run_not_ingested_blocks_the_payload(self):
        proc = self.payload(self.saved, listing([(7001, "completed", "2026-11-02T06:00:00Z")], PROJECT_ID), check=2)
        self.assertIn("7001", proc.stderr)
        self.assertIn("ingest", proc.stderr)

    def test_a_run_recorded_as_unavailable_does_not_block(self):
        self.cli("ingest", "--study", self.study, "--project", KEY, "--unavailable", 7001, check=0)
        out = self.payload(self.saved, listing([(7001, "completed", "2026-11-02T06:00:00Z")], PROJECT_ID))
        self.assertIn("save-project-questions-tool", out)

    def test_an_ingested_run_does_not_block(self):
        history = self.study / "history" / "runs" / KEY
        history.mkdir(parents=True)
        (history / "7001.json.gz").write_bytes(b"")
        out = self.payload(self.saved, listing([(7001, "completed", "2026-11-02T06:00:00Z")], PROJECT_ID))
        self.assertIn("save-project-questions-tool", out)

    def test_a_run_still_open_is_named_in_the_notes_and_does_not_block(self):
        out = self.payload(self.saved, listing([(7002, "running", "2026-11-02T06:00:00Z")], PROJECT_ID))
        self.assertTrue(any("7002" in n for n in out["notes"]), out["notes"])

    def test_a_listing_of_another_project_is_refused(self):
        self.payload(self.saved, listing([], 777), check=2)


class Bind(SetupCase):

    def test_a_created_project_is_bound_with_a_setup_version(self):
        proc = self.bind(empty_project(self.design))
        binding = self.read("sentl.json")
        self.assertEqual(binding["schema"], "sentl-monitor/binding@1")
        self.assertEqual(binding["projects"][KEY], {"project_id": PROJECT_ID, "version": 1, "dimensions": {}, "questions": {}})
        version = self.read(f"history/versions/{KEY}-001.json")
        self.assertEqual(version["source"], "setup")
        self.assertEqual(version["settings"], {"models": [GPT, GEM], "rounds": 1, "schedule": "weekly", "active": False})
        self.assertIn(str(PROJECT_ID), proc.stdout)

    def test_bind_writes_every_id_by_key_and_a_second_setup_version(self):
        self.bind(empty_project(self.design))
        saved = sentl_project(self.design)
        self.bind(saved)
        binding = self.read("sentl.json")["projects"][KEY]
        self.assertEqual(binding["version"], 2)
        sentl_dims = {d["name"]: d for d in saved["project"]["dimensions"]}
        for d in self.design["projects"][0]["dimensions"]:
            self.assertEqual(binding["dimensions"][d["key"]], sentl_dims[d["name"]]["id"])
            for q, sq in zip(d["questions"], sentl_dims[d["name"]]["questions"]):
                self.assertEqual(binding["questions"][q["key"]], sq["id"])
        version = self.read(f"history/versions/{KEY}-002.json")
        self.assertEqual(version["source"], "setup")
        self.assertEqual(len(version["dimensions"]), 5)
        self.assertTrue(all(q["criteria_hash"] and q["id"] for d in version["dimensions"] for q in d["questions"]))
        self.assertIn({"question": "health-1", "change": "created"}, version["changes"])

    def test_a_reworded_question_keeps_its_id_and_its_key_and_is_recorded_as_reworded(self):
        saved = self.create_and_save()
        before = self.read("sentl.json")["projects"][KEY]["questions"]["price-1"]
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"][1]["questions"][0]["text"] = "What is the price of Avenello oat milk?"
        self.write_study(study)
        after = sentl_project(study)
        # Sentl edits in place: the project keeps its ids.
        self.assertEqual(after["project"]["dimensions"][1]["questions"][0]["id"], before)
        self.bind(after)
        binding = self.read("sentl.json")["projects"][KEY]
        self.assertEqual(binding["questions"]["price-1"], before)
        self.assertEqual(binding["version"], 3)
        self.assertEqual(self.read(f"history/versions/{KEY}-003.json")["changes"], [{"question": "price-1", "change": "reworded"}])

    def test_a_dropped_dimension_is_recorded_as_archived(self):
        saved = self.create_and_save()
        taste_id = self.read("sentl.json")["projects"][KEY]["dimensions"]["taste"]
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"] = [d for d in study["projects"][0]["dimensions"] if d["key"] != "taste"]
        study["themes"] = [t for t in study["themes"] if t["id"] != "taste"]
        self.write_study(study)
        after = copy.deepcopy(saved)
        next(d for d in after["project"]["dimensions"] if d["id"] == taste_id)["archived"] = True
        self.bind(after)
        binding = self.read("sentl.json")["projects"][KEY]
        self.assertEqual(binding["dimensions"]["taste"], taste_id)
        self.assertIn({"dimension": "taste", "change": "dimension_archived"},
                      self.read(f"history/versions/{KEY}-003.json")["changes"])

    def test_a_new_intent_question_is_recorded_with_the_one_it_replaces(self):
        self.create_and_save()
        study = copy.deepcopy(self.design)
        dim = study["projects"][0]["dimensions"][1]
        old = dim["questions"][1]
        dim["questions"][1] = {**old, "key": "price-3", "text": "Which oat milk is the cheapest?",
                               "lineage": [{"version": 2, "change": "new_intent", "replaces": "price-2"}]}
        dim["retired"] = [{"key": "price-2", "text": old["text"], "version": 2}]
        self.write_study(study)
        after = sentl_project(study, first_id=2000)
        after["project"]["dimensions"][1]["id"] = self.read("sentl.json")["projects"][KEY]["dimensions"]["price"]
        self.bind(after)
        changes = self.read(f"history/versions/{KEY}-003.json")["changes"]
        self.assertIn({"question": "price-3", "change": "new_intent", "replaces": "price-2"}, changes)
        self.assertIn({"question": "price-2", "change": "retired"}, changes)

    def test_an_unchanged_project_only_refreshes_the_last_time_it_was_seen(self):
        saved = self.create_and_save()
        self.bind(saved, at="2026-11-09T09:00:00Z")
        self.assertFalse((self.study / "history" / "versions" / f"{KEY}-003.json").exists())
        self.assertEqual(self.read(f"history/versions/{KEY}-002.json")["seen_at"], "2026-11-09T09:00:00Z")

    def test_a_save_that_did_not_apply_is_refused_and_writes_nothing(self):
        saved = self.create_and_save()
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"][1]["questions"][0]["text"] = "What is the price of Avenello oat milk?"
        self.write_study(study)
        before = (self.study / "sentl.json").read_text(encoding="utf-8")
        proc = self.bind(saved, check=2)
        self.assertIn("price-1", proc.stderr)
        self.assertEqual((self.study / "sentl.json").read_text(encoding="utf-8"), before)
        self.assertFalse((self.study / "history" / "versions" / f"{KEY}-003.json").exists())

    def test_a_save_that_lost_a_rubric_is_refused(self):
        self.bind(empty_project(self.design))
        saved = sentl_project(self.design)
        saved["project"]["dimensions"][0]["questions"][0]["grading_rubric"]["3"] = "something else"
        self.assertIn("health-1", self.bind(saved, check=2).stderr)

    def test_a_dimension_the_study_has_and_the_project_lacks_is_refused(self):
        self.bind(empty_project(self.design))
        saved = sentl_project(self.design)
        saved["project"]["dimensions"].pop()
        self.assertIn("Availability", self.bind(saved, check=2).stderr)

    def test_a_project_that_is_not_the_bound_one_is_refused(self):
        self.create_and_save()
        saved = sentl_project(self.design, project_id=4242)
        self.bind(saved, check=2)

    def test_settings_that_differ_from_the_study_are_recorded_as_sentl_has_them_and_named(self):
        saved = empty_project(self.design)
        saved["project"]["rounds"] = 2
        proc = self.bind(saved)
        self.assertEqual(self.read(f"history/versions/{KEY}-001.json")["settings"]["rounds"], 2)
        self.assertIn("rounds", proc.stdout)


class BindChecksTheLatestRun(SetupCase):
    """The saved project must hold every text the latest run asked, as for adopt."""

    def setUp(self):
        super().setUp()
        self.saved = self.create_and_save()
        self.run = self.asking("Health", "Is Avenello oat milk bad for you?")

    def asking(self, dimension, question):
        return {"run": {"id": 8001, "project_id": PROJECT_ID, "status": "completed", "reputation_score": 4.0,
                        "started_at": "2026-11-02T06:00:00Z",
                        "responses": [{"id": 1, "model_id": GPT, "question": question, "dimension": dimension,
                                       "answer": "No.", "judge_score": 4, "sentiment": "positive", "sources": []}]}}

    def run_file(self):
        return self.save("run-latest.json", self.run)

    def test_a_saved_project_that_holds_the_text_of_the_latest_run_is_bound(self):
        self.bind(self.saved, "--run", self.run_file())

    def test_a_saved_project_missing_a_text_of_the_latest_run_is_refused(self):
        self.run = self.asking("Health", "Is Avenello oat milk a risk to your health?")
        before = (self.study / "sentl.json").read_text(encoding="utf-8")
        proc = self.bind(self.saved, "--run", self.run_file(), check=2)
        self.assertIn("Is Avenello oat milk a risk to your health?", proc.stderr)
        self.assertEqual((self.study / "sentl.json").read_text(encoding="utf-8"), before)

    def test_a_dimension_of_the_latest_run_that_the_saved_project_lacks_is_refused(self):
        self.run = self.asking("Safety", "Is Avenello oat milk bad for you?")
        self.assertIn("Safety", self.bind(self.saved, "--run", self.run_file(), check=2).stderr)

    def test_a_text_the_study_rewords_on_purpose_is_not_missing(self):
        study = copy.deepcopy(self.design)
        study["projects"][0]["dimensions"][0]["questions"][0]["text"] = "Is Avenello oat milk harmful?"
        self.write_study(study)
        self.bind(sentl_project(study), "--run", self.run_file())

    def test_a_run_of_another_project_is_refused(self):
        self.run["run"]["project_id"] = 12
        self.bind(self.saved, "--run", self.run_file(), check=2)


if __name__ == "__main__":
    unittest.main()
