"""Search demand: Google suggestions, volumes from a keyword-data source, keyword classes,
the per-theme summary, and the report's themes section. No test makes a network call or
resolves a hostname."""

import contextlib
import csv
import json
import re
import socket
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse

from fixtures import StudyCase, models

from sentlmon import demand
from sentlmon.i18n import TEXT

AT = "2026-10-16T09:00:00Z"
TEXT_TITLE = {"it": "Da dove vengono i temi", "en": "Where the themes came from"}
PROVIDER, TOOL = "Acme Keywords", "get_keyword_volume"

SEEDS = {
    "schema": "sentl-monitor/seeds@1",
    "market": {"country": "IT", "language": "it"},
    "subject": {"aliases": ["Avenello"]},
    "foils": [{"aliases": ["Avoria"]}],
    "components": [{"terms": ["latte d'avena", "bevanda all'avena"]}],
    "themes": {
        "salute": ["latte d'avena fa male", "avenello zuccheri"],
        "prezzo": ["latte d'avena prezzo"],
    },
}
IT_STEMS = ["è", "fa", "come", "perché", "quanto", "quale", "si può"]
EN_STEMS = ["is", "does", "how", "why", "can", "which", "vs"]


def asked(url):
    query = parse_qs(urlparse(url).query)
    return query["q"][0], query


def echo(url):
    """A suggestion endpoint that answers every prefix with two suggestions."""
    prefix, _ = asked(url)
    return json.dumps([prefix, [prefix + " opinioni", prefix + " ogni giorno"]], ensure_ascii=False)


class DemandCase(StudyCase):

    def setUp(self):
        super().setUp()
        guard = mock.patch.object(socket, "getaddrinfo", side_effect=AssertionError("a hostname was resolved"))
        guard.start()
        self.addCleanup(guard.stop)
        pause = mock.patch.object(demand, "DELAY", 0)
        pause.start()
        self.addCleanup(pause.stop)

    def seeds(self, **changes):
        data = {**SEEDS, **changes}
        path = self.study / "seeds.json"
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return path

    def autocomplete(self, fetch=echo, check=0, *extra, hl="it", gl="IT"):
        with mock.patch.object(demand, "_get", side_effect=fetch) as get:
            proc = self.cli("demand", "autocomplete", "--study", self.study, "--seeds", self.seeds(),
                            "--hl", hl, "--gl", gl, *extra, check=check, at=AT)
        self.get = get
        return proc

    def volumes(self, keywords, check=0, **head):
        data = {"provider": PROVIDER, "tool": TOOL, "collected": "2026-10-16", "keywords": keywords, **head}
        path = self.save("volumes.json", {k: v for k, v in data.items() if v is not None})
        return self.cli("demand", "volumes", "--study", self.study, "--seeds", self.seeds(), path,
                        check=check, at=AT)

    def demand_file(self):
        return self.read("search-demand.json")


class ParseTest(unittest.TestCase):

    def test_a_suggestion_list_is_the_second_element_of_the_response(self):
        self.assertEqual(demand.parse_suggestions('["latte", ["latte di soia", "latte d’avena"], [], {}]'),
                         ["latte di soia", "latte d’avena"])

    def test_an_empty_list_of_suggestions_is_a_valid_answer(self):
        self.assertEqual(demand.parse_suggestions('["zzzx", []]'), [])

    def test_text_that_is_not_json_is_refused(self):
        with self.assertRaises(ValueError):
            demand.parse_suggestions("<html>429 Too Many Requests</html>")

    def test_json_of_another_shape_is_refused(self):
        for text in ('{"suggestions": []}', '["latte"]', '["latte", "x"]', '["latte", [1, 2]]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                demand.parse_suggestions(text)


class AutocompleteTest(DemandCase, unittest.TestCase):

    def prefixes(self):
        return [asked(call.args[0])[0] for call in self.get.call_args_list]

    def test_each_seed_is_sent_as_typed_and_with_each_stem_of_the_language(self):
        self.autocomplete()
        sent = self.prefixes()
        self.assertEqual(len(sent), 3 * 8)
        for seed in ("latte d'avena fa male", "avenello zuccheri", "latte d'avena prezzo"):
            self.assertIn(seed, sent)
            for stem in IT_STEMS:
                self.assertIn(f"{seed} {stem}", sent)

    def test_english_stems_apply_to_an_english_market(self):
        self.seeds(market={"country": "US", "language": "en"})
        self.autocomplete(hl="en", gl="US")
        self.assertIn("latte d'avena prezzo vs", self.prefixes())
        self.assertNotIn("latte d'avena prezzo perché", self.prefixes())
        self.assertEqual(len(self.prefixes()), 3 * (1 + len(EN_STEMS)))

    def test_the_request_carries_the_market_language_and_country_and_the_accents_intact(self):
        self.autocomplete()
        query = asked(self.get.call_args_list[0].args[0])[1]
        self.assertEqual((query["hl"], query["gl"]), (["it"], ["IT"]))
        self.assertIn("avenello zuccheri perché", self.prefixes())

    def test_a_prefix_records_its_suggestions_source_and_date(self):
        self.autocomplete()
        theme = self.demand_file()["themes"]["prezzo"]
        entry = next(e for e in theme["autocomplete"] if e["prefix"] == "latte d'avena prezzo quanto")
        self.assertEqual(entry["suggestions"], ["latte d'avena prezzo quanto opinioni",
                                                "latte d'avena prezzo quanto ogni giorno"])
        self.assertEqual(entry["source"], "google autocomplete hl=it gl=IT")
        self.assertEqual(entry["collected"], "2026-10-16")
        self.assertEqual(theme["seeds"], ["latte d'avena prezzo"])
        data = self.demand_file()
        self.assertEqual(data["schema"], "sentl-monitor/search-demand@1")
        self.assertEqual(data["market"], {"country": "IT", "language": "it"})
        self.assertIsNone(data["volume_source"])

    def test_the_stems_flag_replaces_the_default_stems(self):
        self.autocomplete(echo, 0, "--stems", "costa,dove")
        self.assertEqual(sorted(set(self.prefixes()) & {"latte d'avena prezzo costa", "latte d'avena prezzo dove",
                                                        "latte d'avena prezzo fa"}),
                         ["latte d'avena prezzo costa", "latte d'avena prezzo dove"])
        self.assertEqual(len(self.prefixes()), 3 * 3)

    def test_a_language_without_default_stems_needs_the_stems_flag(self):
        proc = self.autocomplete(echo, 2, hl="de", gl="DE")
        self.assertIn("--stems", proc.stderr)
        self.assertEqual(self.get.call_count, 0)
        self.assertFalse((self.study / "search-demand.json").exists())

    def test_a_prefix_that_fails_is_listed_and_the_command_exits_1_with_the_others_recorded(self):
        def flaky(url):
            if asked(url)[0] == "avenello zuccheri come":
                raise OSError("timed out")
            return echo(url)
        proc = self.autocomplete(flaky, 1)
        self.assertIn("avenello zuccheri come", proc.stdout)
        self.assertIn("1 prefix", proc.stdout)
        entries = self.demand_file()["themes"]["salute"]["autocomplete"]
        self.assertNotIn("avenello zuccheri come", [e["prefix"] for e in entries])
        self.assertEqual(len(entries), 2 * 8 - 1)

    def test_running_again_fetches_only_the_prefixes_still_missing(self):
        def flaky(url):
            if asked(url)[0] == "avenello zuccheri come":
                raise OSError("timed out")
            return echo(url)
        self.autocomplete(flaky, 1)
        self.autocomplete(echo, 0)
        self.assertEqual(self.prefixes(), ["avenello zuccheri come"])
        entries = self.demand_file()["themes"]["salute"]["autocomplete"]
        self.assertEqual(len(entries), 2 * 8)

    def test_a_response_that_is_not_a_suggestion_list_counts_as_a_failed_prefix(self):
        proc = self.autocomplete(lambda url: "<html>blocked</html>", 1)
        self.assertIn("24 prefixes", proc.stdout)
        self.assertEqual(self.demand_file()["themes"]["salute"]["autocomplete"], [])

    def test_a_seeds_file_of_another_schema_is_refused(self):
        self.seeds(schema="sentl-monitor/study@1")
        with mock.patch.object(demand, "_get", side_effect=echo):
            proc = self.cli("demand", "autocomplete", "--study", self.study, "--seeds", self.study / "seeds.json",
                            "--hl", "it", "--gl", "IT", check=2)
        self.assertIn("seeds", proc.stderr)


class VolumesTest(DemandCase, unittest.TestCase):

    def test_a_keyword_is_merged_with_its_volume_provider_tool_and_date(self):
        self.volumes([{"theme": "salute", "keyword": "latte d'avena fa male", "monthly_volume": 1900}])
        data = self.demand_file()
        entry = data["themes"]["salute"]["volumes"][0]
        self.assertEqual({k: entry[k] for k in ("keyword", "monthly_volume", "class", "provider", "tool", "collected")},
                         {"keyword": "latte d'avena fa male", "monthly_volume": 1900, "class": "component",
                          "provider": PROVIDER, "tool": TOOL, "collected": "2026-10-16"})
        self.assertEqual(data["volume_source"], {"providers": [PROVIDER], "from": "2026-10-16", "to": "2026-10-16"})

    def test_volumes_from_two_providers_widen_the_source(self):
        self.volumes([{"theme": "salute", "keyword": "avenello zuccheri", "monthly_volume": 90}])
        self.volumes([{"theme": "prezzo", "keyword": "latte d'avena prezzo", "monthly_volume": 500}],
                     provider="Orbit Terms", collected="2026-10-20")
        self.assertEqual(self.demand_file()["volume_source"],
                         {"providers": ["Acme Keywords", "Orbit Terms"], "from": "2026-10-16", "to": "2026-10-20"})

    def test_related_searches_that_do_not_concern_the_subject_are_dropped_and_counted(self):
        related = [
            {"keyword": "latte d'avena fa ingrassare", "monthly_volume": 320},
            {"keyword": "avenello recensioni", "monthly_volume": 40},
            {"keyword": "avoria o avenello", "monthly_volume": 10},
            {"keyword": "male di schiena rimedi", "monthly_volume": 800},
            {"keyword": "scarpe da corsa", "monthly_volume": 9000},
            {"keyword": "come si fa il pane", "monthly_volume": 7000},
        ]
        self.volumes([{"theme": "salute", "keyword": "latte d'avena fa male", "monthly_volume": 1900,
                       "related": related}])
        entry = self.demand_file()["themes"]["salute"]["volumes"][0]
        self.assertEqual([r["keyword"] for r in entry["related"]],
                         ["latte d'avena fa ingrassare", "avenello recensioni", "avoria o avenello",
                          "male di schiena rimedi"])
        self.assertEqual(entry["related_dropped"], 2)

    def test_a_related_search_sharing_only_stopwords_with_its_seed_is_dropped(self):
        self.volumes([{"theme": "salute", "keyword": "latte d'avena fa male", "monthly_volume": 1900,
                       "related": [{"keyword": "come si fa", "monthly_volume": 5000}]}])
        entry = self.demand_file()["themes"]["salute"]["volumes"][0]
        self.assertEqual((entry["related"], entry["related_dropped"]), ([], 1))

    def test_a_kept_related_search_is_classed(self):
        self.volumes([{"theme": "salute", "keyword": "latte d'avena fa male", "monthly_volume": 1900,
                       "related": [{"keyword": "avenello recensioni", "monthly_volume": 40},
                                   {"keyword": "avoria o avenello", "monthly_volume": 10}]}])
        related = self.demand_file()["themes"]["salute"]["volumes"][0]["related"]
        self.assertEqual([r["class"] for r in related], ["subject", "subject"])

    def test_merging_a_keyword_again_replaces_its_earlier_entry(self):
        keyword = {"theme": "salute", "keyword": "Latte d’avena fa male", "monthly_volume": 1900}
        self.volumes([keyword])
        self.volumes([{**keyword, "keyword": "latte d'avena fa male", "monthly_volume": 2400}],
                     collected="2026-11-16")
        entries = self.demand_file()["themes"]["salute"]["volumes"]
        self.assertEqual([(e["monthly_volume"], e["collected"]) for e in entries], [(2400, "2026-11-16")])

    def test_a_file_without_its_provider_tool_or_date_is_refused(self):
        keywords = [{"theme": "salute", "keyword": "avenello zuccheri", "monthly_volume": 90}]
        for field in ("provider", "tool", "collected"):
            with self.subTest(field=field):
                proc = self.volumes(keywords, 2, **{field: None})
                self.assertIn(field, proc.stderr)
        self.assertFalse((self.study / "search-demand.json").exists())

    def test_a_keyword_of_an_unknown_theme_is_refused_and_nothing_is_written(self):
        proc = self.volumes([{"theme": "colore", "keyword": "avenello zuccheri", "monthly_volume": 90}], 2)
        self.assertIn("colore", proc.stderr)
        self.assertFalse((self.study / "search-demand.json").exists())

    def test_a_volume_that_is_not_a_whole_number_is_refused(self):
        for value in (-5, "1900", 12.5, None, True):
            with self.subTest(value=value):
                self.volumes([{"theme": "salute", "keyword": "avenello zuccheri", "monthly_volume": value}], 2)

    def test_volumes_merge_into_the_suggestions_already_collected(self):
        self.autocomplete()
        self.volumes([{"theme": "salute", "keyword": "avenello zuccheri", "monthly_volume": 90}])
        theme = self.demand_file()["themes"]["salute"]
        self.assertEqual(len(theme["autocomplete"]), 16)
        self.assertEqual(len(theme["volumes"]), 1)


class ImportTest(DemandCase, unittest.TestCase):

    def export(self, header, rows, name="export.csv"):
        path = self.study / "inbox" / name
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)
        return path

    def run_import(self, path, check=0, *extra):
        return self.cli("demand", "import", "--study", self.study, "--seeds", self.seeds(), "--provider", PROVIDER,
                        "--tool", TOOL, "--theme", "salute", "--date", "2026-10-16", *extra, path, check=check)

    def test_an_export_with_keyword_and_volume_columns_is_merged_for_the_theme(self):
        path = self.export(["Keyword", "Search Volume"], [["latte d'avena fa male", "1900"], ["avenello zuccheri", "90"]])
        self.run_import(path)
        entries = self.demand_file()["themes"]["salute"]["volumes"]
        self.assertEqual({(e["keyword"], e["monthly_volume"], e["provider"], e["tool"]) for e in entries},
                         {("latte d'avena fa male", 1900, PROVIDER, TOOL), ("avenello zuccheri", 90, PROVIDER, TOOL)})

    def test_a_thousands_separator_in_a_volume_is_read(self):
        path = self.export(["keyword", "volume"], [["latte d'avena fa male", "1,900"]])
        self.run_import(path)
        self.assertEqual(self.demand_file()["themes"]["salute"]["volumes"][0]["monthly_volume"], 1900)

    def test_rows_naming_a_seed_are_its_related_searches_and_are_filtered(self):
        path = self.export(["keyword", "volume", "related to"],
                           [["latte d'avena fa male", "1900", ""],
                            ["latte d'avena fa ingrassare", "320", "latte d'avena fa male"],
                            ["scarpe da corsa", "9000", "latte d'avena fa male"]])
        self.run_import(path)
        entry = self.demand_file()["themes"]["salute"]["volumes"][0]
        self.assertEqual([r["keyword"] for r in entry["related"]], ["latte d'avena fa ingrassare"])
        self.assertEqual(entry["related_dropped"], 1)

    def test_a_file_without_a_volume_column_is_refused_naming_the_columns_found(self):
        path = self.export(["keyword", "difficulty"], [["avenello zuccheri", "12"]])
        proc = self.run_import(path, 2)
        self.assertIn("difficulty", proc.stderr)

    def test_a_volume_that_is_not_a_number_is_refused(self):
        path = self.export(["keyword", "volume"], [["avenello zuccheri", "n/a"]])
        self.run_import(path, 2)

    def test_a_json_file_in_the_volumes_shape_is_accepted(self):
        path = self.save("export.json", {"provider": "Orbit Terms", "tool": "export", "collected": "2026-10-18",
                                         "keywords": [{"theme": "prezzo", "keyword": "latte d'avena prezzo",
                                                       "monthly_volume": 500}]})
        self.cli("demand", "import", "--study", self.study, "--seeds", self.seeds(), path, check=0)
        entry = self.demand_file()["themes"]["prezzo"]["volumes"][0]
        self.assertEqual((entry["provider"], entry["collected"]), ("Orbit Terms", "2026-10-18"))


class ClassTest(unittest.TestCase):
    TERMS = demand.terms_of(SEEDS)

    def classify(self, keyword):
        return demand.classify(keyword, self.TERMS)

    def test_a_keyword_naming_the_subject_is_subject(self):
        self.assertEqual(self.classify("avenello zuccheri"), "subject")

    def test_a_keyword_naming_a_foil_is_foil(self):
        self.assertEqual(self.classify("avoria prezzo"), "foil")

    def test_a_keyword_with_a_component_term_and_no_brand_is_component(self):
        self.assertEqual(self.classify("latte d’avena fa male"), "component")

    def test_a_keyword_with_nothing_of_the_three_is_generic(self):
        self.assertEqual(self.classify("latte di soia prezzo"), "generic")

    def test_the_subject_wins_over_a_component_term_and_over_a_foil(self):
        self.assertEqual(self.classify("avenello latte d'avena"), "subject")
        self.assertEqual(self.classify("avoria o avenello"), "subject")

    def test_the_foil_wins_over_a_component_term(self):
        self.assertEqual(self.classify("avoria latte d'avena"), "foil")

    def test_an_alias_is_found_on_word_boundaries_and_without_regard_to_case_or_accents(self):
        self.assertEqual(self.classify("AVENELLO"), "subject")
        self.assertEqual(self.classify("avenelloni"), "generic")
        self.assertEqual(self.classify("bevanda all’avena zuccheri"), "component")


def themed(volumes, source=True):
    return {"schema": "sentl-monitor/search-demand@1", "market": {"country": "IT", "language": "it"},
            "themes": {"salute": volumes}, "volume_source": {"providers": [PROVIDER], "from": "2026-10-16",
                                                              "to": "2026-10-16"} if source else None}


def vol(keyword, volume, cls, related=()):
    return {"keyword": keyword, "monthly_volume": volume, "class": cls, "provider": PROVIDER, "tool": TOOL,
            "collected": "2026-10-16", "related": list(related), "related_dropped": 0}


def auto(prefix, *suggestions):
    return {"prefix": prefix, "suggestions": list(suggestions), "source": "google autocomplete hl=it gl=IT",
            "collected": "2026-10-16"}


class SummaryTest(DemandCase, unittest.TestCase):

    def write(self, data):
        (self.study / "search-demand.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def theme(self, **parts):
        return {"seeds": [], "autocomplete": [], "volumes": [], **parts}

    def test_volumes_are_added_within_a_class_and_never_across_classes(self):
        summary = demand.summarize(themed(self.theme(volumes=[
            vol("avenello zuccheri", 90, "subject"),
            vol("avenello recensioni", 40, "subject"),
            vol("latte d'avena fa male", 1900, "component", [
                {"keyword": "latte d'avena fa ingrassare", "monthly_volume": 320, "class": "component"}]),
            vol("latte di soia prezzo", 700, "generic")])))["salute"]
        self.assertEqual(summary["volume"], {"subject": 130, "component": 2220, "generic": 700})

    def test_a_keyword_listed_twice_is_counted_once(self):
        summary = demand.summarize(themed(self.theme(volumes=[
            vol("latte d'avena fa male", 1900, "component", [
                {"keyword": "latte d’avena fa ingrassare", "monthly_volume": 320, "class": "component"}]),
            vol("latte d'avena fa ingrassare", 320, "component")])))["salute"]
        self.assertEqual(summary["volume"], {"component": 2220})

    def test_a_theme_without_volumes_has_none(self):
        summary = demand.summarize(themed(self.theme(autocomplete=[auto("a", "a1")]), source=False))["salute"]
        self.assertIsNone(summary["volume"])

    def test_distinct_suggestions_are_counted_across_prefixes_without_regard_to_case(self):
        summary = demand.summarize(themed(self.theme(autocomplete=[
            auto("latte d'avena", "latte d'avena fa male", "latte d'avena prezzo"),
            auto("latte d'avena fa", "Latte d’avena fa male", "latte d'avena fa bene"),
            auto("latte d'avena è")]), source=False))["salute"]
        self.assertEqual((summary["suggestions"], summary["prefixes"]), (3, 3))

    def test_top_queries_follow_the_volume_when_there_is_one_and_the_suggestions_when_not(self):
        with_volume = demand.summarize(themed(self.theme(
            autocomplete=[auto("x", "uno", "due")],
            volumes=[vol("poco", 10, "generic"), vol("molto", 900, "generic"), vol("medio", 100, "generic")])))
        self.assertEqual(with_volume["salute"]["top"], [("molto", 900), ("medio", 100), ("poco", 10)])
        without = demand.summarize(themed(self.theme(autocomplete=[auto("x", "uno", "due"), auto("y", "tre")]),
                                          source=False))
        self.assertEqual(without["salute"]["top"], [("uno", None), ("due", None), ("tre", None)])

    def test_the_summary_prints_each_theme_with_its_counts_volume_per_class_and_top_queries(self):
        self.write(themed(self.theme(
            autocomplete=[auto("a", "uno", "due")],
            volumes=[vol("avenello zuccheri", 90, "subject"), vol("latte d'avena fa male", 1900, "component")])))
        out = self.cli("demand", "summary", "--study", self.study, check=0).stdout
        self.assertIn("salute: 2 distinct suggestions from 1 prefix", out)
        self.assertIn("volume per month: subject 90; component 1900", out)
        self.assertIn("latte d'avena fa male (1900)", out)
        self.assertNotIn("total", out.lower())
        self.assertNotIn(demand.NO_VOLUME, out)

    def test_without_a_volume_source_the_summary_carries_the_no_volume_statement(self):
        self.write(themed(self.theme(autocomplete=[auto("a", "uno", "due")]), source=False))
        out = self.cli("demand", "summary", "--study", self.study, check=0).stdout
        self.assertIn("volume per month: none", out)
        self.assertIn(demand.NO_VOLUME, out)
        self.assertEqual(demand.NO_VOLUME, "The counts are Google suggestions: they measure how many ways a theme "
                                           "is phrased, not how many people search it.")

    def test_a_study_without_search_demand_is_refused_with_the_command_to_run(self):
        proc = self.cli("demand", "summary", "--study", self.study, check=2)
        self.assertIn("demand autocomplete", proc.stderr)


class ThemesSectionTest(DemandCase, unittest.TestCase):
    """The themes section of the report, fed from search-demand.json."""

    def themes_section(self, lang="it"):
        study = self.read("study.json")
        study["report_language"] = lang
        (self.study / "study.json").write_text(json.dumps(study, ensure_ascii=False), encoding="utf-8")
        self.cli("method", "--study", self.study, "--date", "2026-10-31", "--force",
                 "--models", self.save("models.json", models()), check=0)
        text = (self.study / "reports" / "2026-10-31.md").read_text(encoding="utf-8")
        parts = re.split(r"^## \d+\. (.+)$", text, flags=re.M)
        return dict(zip(parts[1::2], parts[2::2]))[TEXT_TITLE[lang]]

    def collect(self, with_volumes):
        self.ready()
        self.autocomplete()
        if with_volumes:
            self.volumes([{"theme": "salute", "keyword": "avenello zuccheri", "monthly_volume": 90},
                          {"theme": "salute", "keyword": "latte d'avena fa male", "monthly_volume": 1900},
                          {"theme": "prezzo", "keyword": "latte d'avena prezzo", "monthly_volume": 500}])

    def test_each_theme_gets_its_distinct_suggestions_and_month_in_the_english_report(self):
        self.collect(False)
        section = self.themes_section("en")
        self.assertIn("- Salute: 32 distinct Google suggestions (October 2026)", section)
        self.assertIn("- Prezzo: 16 distinct Google suggestions (October 2026)", section)

    def test_without_a_volume_source_the_section_says_what_the_counts_measure(self):
        self.collect(False)
        section = self.themes_section("en")
        self.assertIn(TEXT["en"]["no_volume"], section)
        self.assertNotIn(TEXT["en"]["no_search"], section)
        self.assertIn(TEXT["it"]["no_volume"], self.themes_section("it"))

    def test_with_volumes_each_class_is_stated_apart_with_its_provider_and_date(self):
        self.collect(True)
        section = self.themes_section("en")
        self.assertIn("90 naming the subject; 1,900 about the component alone", section)
        self.assertIn("Acme Keywords, 16 October 2026", section)
        self.assertNotIn(TEXT["en"]["no_volume"], section)
        self.assertNotIn("1,990", section)

    def test_the_italian_section_writes_numbers_and_dates_the_italian_way(self):
        self.collect(True)
        self.volumes([{"theme": "salute", "keyword": "latte d'avena fa male", "monthly_volume": 2500}])
        section = self.themes_section("it")
        self.assertIn("2.500 sul solo componente", section)
        self.assertIn("16 ottobre 2026", section)
        self.assertIn("ottobre 2026", section)

    def test_a_study_without_search_demand_keeps_the_line_saying_none_was_collected(self):
        self.ready()
        self.assertIn(TEXT["en"]["no_search"], self.themes_section("en"))

    def test_a_theme_the_search_demand_does_not_cover_is_left_out_of_the_demand_lines(self):
        self.ready()
        (self.study / "search-demand.json").write_text(json.dumps(themed(
            {"seeds": [], "autocomplete": [auto("x", "uno")], "volumes": []}, source=False)), encoding="utf-8")
        section = self.themes_section("en")
        self.assertIn("- Salute: 1 distinct Google suggestion (October 2026)", section)
        self.assertNotRegex(section, r"Prezzo: \d")


if __name__ == "__main__":
    unittest.main()
