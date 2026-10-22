# Architecture

sentl-monitor is a set of route playbooks that an assistant follows, plus one
standard-library script, `scripts/monitor.py`, for everything that must be deterministic:
search demand, validation, the arguments sent to Sentl, run ingestion, comparison, the
method sections of the report and the final check. The assistant calls the Sentl MCP tools
and saves their responses into the study folder; the script reads those files and never
calls Sentl.

## Stages and the files they write

| Stage | Reads | Writes | Stops for |
|---|---|---|---|
| `brief <subject>` | the client's documents, Google autocomplete, a keyword-data source if present | `brief.md`, `seeds.json`, `volumes.json` (optional), `search-demand.json` | the operator's review of the themes and their origins |
| `design` | `brief.md`, `search-demand.json`, a saved `list-ai-models` response | `study.json`, `study-review.md` | the operator's review of the questions, rubrics and credit estimate |
| `setup` | `study.json`, `sentl.json` | Sentl projects; `sentl.json`, `history/versions/` | the operator's go before a run starts or a schedule is activated |
| `adopt <project>` | saved `get-project-tool` and `get-run-results-tool` responses (the latest completed run) | `study.json`, `sentl.json`, `history/versions/` | the operator's answers on purpose, audience, theme origins, market, report language and cadence, who wrote the criteria, and optionally the foils' domains and the current and outdated terms of facts that carry a figure or a name |
| `report` | `study.json`, `sentl.json`, saved `list-runs-tool`, `get-run-results-tool` and `get-project-tool` responses | `history/versions/` (a detected edit; an adopted project's `study.json` and `sentl.json` follow it), `history/runs/`, `history/unavailable.json`, `history/periods/`, `history/material/`, `reports/<date>.md`, `history/reports.json`; `reports/<date>.charts.md` when the operator asks for charts | nothing when run unattended |
| `snapshot <subject>` | the operator's answers and facts, `catalogue.md`, saved `list-ai-models`, `estimate-run-tool`, `list-runs-tool` and `get-run-results-tool` responses | `study.json` (`kind: snapshot`), `study-review.md`, one Sentl project; `sentl.json`, `history/versions/`, `history/runs/`, `history/periods/`, `history/material/`, `reports/<date>.md` | the operator's review of the questions and rubrics, then the go after the credit estimate |

## The study folder

One folder per monitored subject, kept for the whole engagement. A change to the questions
is a new version inside the same folder, so the history stays in one place.

```
<study>/
  brief.md                       themes, origins, search demand, who asks: the first gate
  seeds.json                     seed queries per theme
  volumes.json                   volumes and related searches from a keyword-data source (optional)
  search-demand.json             merged search demand, every figure dated with its source
  study.json                     the design; source of truth for what the study should ask
  study-review.md                printed by `monitor.py review`: the second gate
  sentl.json                     Sentl organization, project, dimension and question ids
  inbox/                         MCP responses saved for the script, one file per call
  history/
    versions/<project>-<NNN>.json   the configuration in force in Sentl, numbered
    runs/<project>/<run_id>.json.gz one normalized snapshot per ingested run
    unavailable.json                completed runs whose results Sentl could not return, retried at each invocation
    periods/<YYYY-MM-DD>.json       metrics of one report period and its comparison
    periods/<YYYY-MM-DD>.first.json the halves of a first period with no earlier one (and .second.json)
    material/<YYYY-MM-DD>.md        the figures and candidate answers the insights are written from
    reports.json                    index of reports: period, runs, status
    last-report.json                outcome of the latest `report` invocation
  reports/<YYYY-MM-DD>.md        the reports
  reports/<YYYY-MM-DD>.charts.md the report's figures as md2 chart tables for a deck (optional)
```

A snapshot folder has the same layout without `brief.md`, `seeds.json`, `volumes.json` and
`search-demand.json`, and holds one run and one report.

On a host that deletes its files when the conversation ends, the folder travels between
conversations as a pack (§Hosts without a lasting folder).

The skill's repository ignores study and snapshot folders. They hold client data.

## Where state lives

| Sentl holds | The study folder holds |
|---|---|
| organization, role, credits | the theme inventory with origins, and the search demand |
| project settings: name, researcher models, rounds, schedule, active | purpose, research question, who asks and why, the reasons for each design choice |
| dimensions: name, order, archived | subject aliases, foils, components, owned domains, market and language |
| questions: label, text, rubric, judge instructions | per question: stable key, framing, pair, persona, dated facts, lineage |
| runs: status, trigger, times, score | the ids binding each local key to Sentl (`sentl.json`) |
| responses: model, answer, sources, score, sentiment | the configuration in force at each run (`history/versions/`) |
| | a normalized copy of every run ingested, the period metrics, the reports |

Two rules keep them consistent:

- `study.json` is the source of truth for what the study should ask; Sentl is the source of
  truth for what was asked and answered. When `report` or `setup` finds that a project in
  Sentl differs from the latest recorded version (an edit made in the Sentl web panel), it
  records a `detected` version and tells the operator. It never overwrites either side
  without the operator's choice. An adopted project's questions are Sentl's, as the operator
  chose by adopting it, so its entry in `study.json` follows the detected version; a
  designed study keeps its `study.json` until the operator chooses.
- A run is ingested once and kept. Every route that writes to Sentl first ingests every
  completed run not yet in `history/runs/`, so that each run is matched against the version
  recorded for its time: the results of a run show the wording asked when it ran
  (Assumptions, A1), and after an edit that wording survives only in the recorded versions.
  A run whose results Sentl returns as a server error is recorded in
  `history/unavailable.json`, listed to the operator and requested again at every
  invocation; it blocks neither a report nor a write.

**Why the script never calls Sentl.** The assistant already holds the MCP connection with
whatever authentication the operator chose (OAuth or token). A script that called the
endpoint itself would need its own token, stored on disk. Keeping every call in the
assistant also keeps every write behind the assistant's approval prompt.

## File schemas

All JSON files carry `"schema": "sentl-monitor/<name>@<n>"`. Dates are ISO 8601.

### `search-demand.json`

```json
{
  "schema": "sentl-monitor/search-demand@1",
  "market": {"country": "IT", "language": "it"},
  "themes": {
    "health": {
      "seeds": ["latte d'avena fa male", "latte d'avena salute"],
      "autocomplete": [{"prefix": "latte d'avena fa", "suggestions": ["latte d'avena fa male", "..."],
                        "source": "google autocomplete hl=it gl=it", "collected": "2026-10-16"}],
      "volumes": [{"keyword": "latte d'avena fa male", "monthly_volume": 1900, "class": "component",
                   "provider": "<server or file>", "tool": "<tool name>", "collected": "2026-10-16",
                   "related": [{"keyword": "latte d'avena fa ingrassare", "monthly_volume": 320,
                                "class": "component"}],
                   "related_dropped": 14}]
    }
  },
  "volume_source": {"providers": ["<server or file>"], "from": "2026-10-16", "to": "2026-10-16"}
}
```

`class` is `subject` (the keyword contains an alias of the subject), `foil`, `component` (it
contains a component term and no subject alias) or `generic`; a keyword that fits several is
given the first in that order, with `foil` before `component`. `volume_source` is the providers
and the first and last collection dates, or `null` when no keyword-data source was used.

`seeds.json` holds what the commands need to class and filter keywords:

```json
{
  "schema": "sentl-monitor/seeds@1",
  "market": {"country": "IT", "language": "it"},
  "subject": {"aliases": ["Avenello"]},
  "foils": [{"aliases": ["Avoria"]}],
  "components": [{"terms": ["latte d'avena", "bevanda all'avena"]}],
  "themes": {"health": ["latte d'avena fa male", "avenello zuccheri"]}
}
```

`volumes.json` is what the assistant saves from a keyword-data server: `provider`, `tool` and
`collected` (a date) for the whole file, and `keywords`, each with its `theme`, `keyword`,
`monthly_volume` (a whole number) and optional `related` searches with the same two fields.

### `study.json`

```json
{
  "schema": "sentl-monitor/study@1",
  "kind": "study",
  "subject": {"id": "avenello", "label": "Avenello", "kind": "brand",
              "aliases": ["Avenello", "Avenello Oat"], "owned_domains": ["avenello.example"]},
  "foils": [{"id": "cow-milk", "label": "latte vaccino", "aliases": ["latte vaccino", "latte di mucca"]},
            {"id": "avoria", "label": "Avoria", "aliases": ["Avoria"], "domains": ["avoria.example"]}],
  "components": [{"id": "oat-drink", "label": "bevanda all'avena",
                  "terms": ["latte d'avena", "latte di avena", "bevanda all'avena"]}],
  "market": {"country": "IT", "language": "it"},
  "report_language": "it",
  "report_every": "monthly",
  "organization": "<Sentl organization slug>",
  "narrative": {
    "criteria": {"by": "il team marketing di Avenello", "date": "2026-09-15"},
    "research_question": "Cosa viene detto a chi chiede a un assistente AI delle bevande all'avena e di Avenello?",
    "purpose": "Sapere cosa dicono gli assistenti AI a chi sceglie una bevanda vegetale, per decidere quali pagine scrivere e quali affermazioni correggere.",
    "audience": {"choice": "personas",
                 "reason": "Un genitore, un celiaco e chi fa sport fanno domande diverse sullo stesso prodotto."},
    "design_rationale": [{"choice": "Due progetti: con il marchio e senza marchio",
                          "reason": "Il primo si legge dal punteggio medio, il secondo da quante risposte nominano Avenello."}],
    "score_axis": "stance"
  },
  "themes": [
    {"id": "health", "label": "Bevande all'avena e salute",
     "origins": [{"kind": "client_issue", "detail": "Domande al servizio clienti, 2026"},
                 {"kind": "search", "detail": "Google autocomplete, Italia, ottobre 2026"}],
     "dimension": "health"}
  ],
  "projects": [
    {"key": "brand", "name": "Avenello · Con il marchio",
     "question": "Cosa sente dire di Avenello chi la nomina?",
     "decision": "Quali affermazioni correggere nelle pagine di prodotto",
     "models": ["<id from list-ai-models>"], "rounds": 1, "schedule": "weekly",
     "dimensions": [
       {"key": "health", "name": "Salute", "search_lean": "negative", "axis": "stance",
        "questions": [
          {"key": "health-1", "label": "Avenello fa male", "branded": true,
           "text": "Il latte d'avena Avenello fa male?",
           "framing": "negative", "pair": "health-a",
           "persona": "chi beve latte d'avena ogni mattina e ha letto che fa male",
           "rubric": {"1": "...", "2": "...", "3": "...", "4": "...", "5": "..."},
           "instructions": "...",
           "facts": [{"fact": "...", "source": "https://avenello.example/...", "date": "2026-10-01",
                      "current": ["2,10 €"], "outdated": ["1,90 €"]}],
           "lineage": [{"version": 1, "change": "created"}]}
        ]}
     ]}
  ]
}
```

- `kind` at the top is `study` or `snapshot`. A snapshot has one project, 4–5 dimensions
  with one question each, `rounds` 1 and no `schedule`; `themes` is empty, and each
  dimension carries `catalogue`, the id of the catalogue entry it was taken from.
- `report_every` is `weekly` or `monthly`: how often a report is written. With each
  project's `schedule` it sets how many runs a period pools. A snapshot has none.
- `kind` of a theme origin is `client_material`, `client_issue`, `client_analysis`, `search`
  or `probe` (a pilot run of questions).
- `search_lean` is `positive`, `negative` or `none`, set from the theme's searches.
- `framing` is `positive`, `negative` or `neutral`; two questions with the same `pair` ask the
  same thing with opposite leans.
- `axis` is `stance` (1 against the subject, 5 for it with grounds) or `fidelity` (1 wrong as
  fact, 5 accurate with the conditions the evidence sets). The report explains the score by it.
- Sentl's `additional_instructions` is composed from `instructions` and the dated `facts`.
- A fact may carry `current` and `outdated` terms, as answers write them; `period` counts the
  answers stating each (§Insights). A foil may carry `domains`, the sites it owns; a cited page
  on one of them, or on a subdomain, is the foil's.

**Sentl's limits, checked before any save:** dimension name and question label at most 100
characters; question at most 500; each rubric anchor at most 300; judge instructions,
facts included, at most 500; at least one question per dimension; rounds at least 1;
schedule `daily`, `weekly` or `monthly`.

### `sentl.json`

```json
{
  "schema": "sentl-monitor/binding@1",
  "organization": "<slug>",
  "projects": {
    "brand": {"project_id": 0, "version": 3,
              "dimensions": {"health": 0},
              "questions": {"health-1": 0}}
  }
}
```

It is kept apart from `study.json` so the same design can be set up again in another
organization.

A snapshot's project also carries `closed`, written by the route's last step:
`{"paused_at": "<time>", "archive": "operator"}`. `archive` is `operator` while the operator
must archive or delete the project in the Sentl web panel (gap G16), and `mcp` once the route
can archive it itself.

### Version snapshot, `history/versions/<project>-<NNN>.json`

```json
{
  "schema": "sentl-monitor/version@1",
  "project": "brand", "version": 3,
  "source": "detected", "recorded_at": "2026-11-30T09:14:00Z", "seen_at": "2026-11-30T09:14:00Z",
  "window": {"from": "2026-10-31T09:02:00Z", "to": "2026-11-30T09:14:00Z"},
  "settings": {"models": ["..."], "rounds": 1, "schedule": "weekly", "active": true},
  "dimensions": [{"key": "health", "id": 0, "name": "Salute", "archived": false,
                  "questions": [{"key": "health-1", "id": 0, "text": "...",
                                 "criteria_hash": "<hash of rubric and judge instructions>"}]}],
  "changes": [{"question": "health-2", "change": "reworded"},
              {"change": "models", "added": ["<model id>"], "removed": []}]
}
```

`source` is `setup` (saved by the skill), `adopt`, or `detected` (found to differ from the
previous version by `monitor.py detect`). `seen_at` is the last time a saved
`get-project-tool` response matched the version. A detected version carries `window`: the
previous version's `seen_at` and the time the difference was found; the edit was made
between the two. `change` is `created`, `reworded`, `new_intent` (with `replaces`, the key it
retires), `criteria`, `retired`, `renumbered` (with `from` and `to`, the old and new Sentl
ids), `models` (with `added` and `removed`), `rounds` (with `from` and `to`),
`dimension_added`, `dimension_archived`, `dimension_renamed` or `dimension_renumbered` (with
`from` and `to`); a question taken in by `adopt` starts its lineage with `adopted`. A question
or a dimension keeps its key through its Sentl id. One whose id changed while its text, or its
name, is that of a question of the same dimension, or of a dimension, whose id is gone is the
same one renumbered: it keeps that key, so its comparison goes on, and the lineage does not
record it. A text that differs from the version's only by the normalization of §Matching
is a transcription, not an edit. Schedule and activation are recorded and not compared.

### Run snapshot, `history/runs/<project>/<run_id>.json.gz`

```json
{
  "schema": "sentl-monitor/run@1",
  "run_id": 0, "project": "brand", "status": "completed", "trigger": "scheduled",
  "started_at": "...", "finished_at": "...", "sentl_score": 3.4, "error": null,
  "version": 3, "ingested_at": "...",
  "plan": {"questions": ["health-1"], "models": ["<model id>"], "rounds": 1},
  "expected": 48, "received": 48, "judged": 47,
  "responses": [
    {"response_id": 0, "question": "health-1", "dimension": "health", "model": "<model id>",
     "score": 4, "sentiment": "positive", "answer": "...",
     "sources": [{"url": "...", "title": "...", "domain": "example.org"}],
     "match": "exact"}
  ]
}
```

- `plan` is the questions, models and rounds of the version in force, and `expected` their
  product; `received` and `judged` are counted from the response. `criteria_unknown` lists
  the questions whose rubric the run cannot be placed under (§Matching).
- A run that started before the first recorded version (a run read from a project's history
  when it is adopted) has no known configuration (gap G2): `version` is `null`, and
  `plan` holds the distinct questions answered, the distinct models and the largest number
  of responses of one question–model pair as its rounds. Its `expected` counts every
  distinct question it asked, matched or not, so a run asked in a wording no version holds
  falls under the run floor of §Coverage.
- `score` and `sentiment` are `null` for an answer the judge did not score. Sentl returns
  `judge_score: null` with `sentiment: "neutral"` on such an answer.
- `answer` is `null` when the model returned no answer; Sentl leaves its score `null` too.
  Such a response counts against coverage and is left out of presence, whose denominator is
  the answers given.
- A source's `domain` is its URL's host without `www.`. A grounding redirect
  (`vertexaisearch.cloud.google.com`, the URL of every source one assistant cites) hides the
  site; its title is the site's domain and is used instead.
- Whether an answer names the subject or a foil, and whether a cited domain is owned, is not
  stored: `period` computes it from the aliases and owned domains in `study.json` at the time,
  by string match (case- and accent-folded, on word boundaries), never by asking a model. An
  alias the operator corrects applies to the whole history. `position` is the subject's order
  among the subject and the foils named in the answer.
- `match` is `exact`, `version` (matched against the text of the other version tried for a
  run started inside a detection window) or `unmatched` (kept with the dimension and question
  Sentl returned under `asked`, excluded from every figure, listed to the operator).
- Runs are compressed because the history grows with every run: a project of 30 questions and
  4 models produces about 120 answers per run.

### Period metrics, `history/periods/<YYYY-MM-DD>.json`

```json
{
  "schema": "sentl-monitor/period@2",
  "date": "2026-11-30", "from": "2026-11-02T06:00:00Z", "to": "2026-11-30T06:00:00Z",
  "runs": {"brand": [0, 0, 0, 0]}, "versions": {"brand": [2, 3, 3, 3]},
  "starts": {"brand": ["2026-11-02T06:00:00Z", "..."]},
  "excluded": {"brand": [{"run_id": 0, "reason": "..."}]}, "dropped": {"brand": {"0": ["health-2"]}},
  "projects": {"brand": {"total": {}, "by_model": {},
     "dimensions": {"health": {"total": {}, "by_model": {},
        "questions": {"health-1": {"total": {}, "by_model": {}}}}}}},
  "names": {"<model id>": "<public name>"},
  "comparison": {"previous": "2026-10-31",
                 "previous_period": {"from": "...", "to": "...", "rebuilt": false},
                 "range_of": ["2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31"],
                 "dimensions": {"brand": {"health": {"project": "brand", "status": "compared",
                                           "models": ["<model id>"], "compared_questions": ["health-1"],
                                           "mean": {"now": 3.6, "previous": 3.1, "delta": 0.5,
                                                    "range": [2.9, 3.2], "periods": 4, "changed": true},
                                           "presence": {},
                                           "questions": {"health-1": {"status": "compared", "mean": {}, "presence": {}},
                                                         "health-3": {"status": "new_baseline", "reason": "criteria"}}}}},
                 "verdict_changes": [{"project": "brand", "dimension": "health", "question": "health-1",
                                      "model": "<model id>", "from": "mixed", "to": "favourable",
                                      "previous_mean": 3.0, "mean": 4.0,
                                      "previous_answer": {"run_id": 0, "response_id": 0, "score": 3},
                                      "answer": {"run_id": 0, "response_id": 0, "score": 4}}],
                 "domains": {"new": [{"project": "brand", "dimension": "health", "domain": "example.org",
                                      "answers": 3, "owned": false}], "lost": []},
                 "design_changes": [{"project": "brand", "change": "reworded", "question": "health-2",
                                     "text": "...", "previous_text": "...", "since": "2026-11-09"}]}
}
```

Each cell also carries `readings` (the distinct readings among the answers given) and
`authors` (answers citing owned, a foil's and third-party pages, each out of `with_sources`,
and `foil_pages`, the foil pages most cited). A question's scope may carry `facts` (the terms;
per cell `given`, `stating`, `current_only`, `outdated_only`, `both`, `current_share`, for all
assistants, `by_model` and per run in `runs`), `group_sources` (per group, `outdated`, `current`,
`low` or `high`, up to five domains, each with `citing`, `answers` and `share` in the group and
the same under `other` for the opposite group), `presence_runs` (per run `named` of
`given`, for a question naming no brand), `episodes` (`measure`, `first`, `last`, `first_at`, `last_at` (the start
times of the episode's first and last run), `runs`,
`values`, `range`, `earlier`, `side`, `closed`, and on a closed episode `later`: the runs of the
period after it whose value lies on its side of `range`, each `date` and `value`) and `missing`
(per model `answers`, `given`,
`judged`, `mean`, `mean_without`); each is present only when it has content, except `later`,
  present on every closed episode, empty when no later run lies on its side. The comparison
carries `presence_sources`: per question whose presence changed, the domains `new` and `lost`
in the answers naming the subject. §Insights gives the rules.

The comparison's `dimensions` are keyed by project, then by dimension key, and its verdict,
domain and presence changes each name their project and dimension, because two projects of a study
may share a dimension key: `adopt` and `detect` keep keys unique across the study, except for a
dimension archived when its project was adopted and restored after another project took its key.
A period file of schema `period@1` keys them by dimension key alone, each entry naming its project;
`check` and `charts` read both shapes, and `period` writes the current one whenever it builds a
period.

The comparison also carries `projects`: per project, the `dimensions` compared and the
project's `mean` entry on them. A compared question whose facts have terms carries
`current_share`, an entry like `presence` for the share of its answers stating a current
term. On a first report that compares the two halves of its period (§Periods), `previous`,
`previous_period` and `range_of` are empty and `halves` holds `first` and `second`, each with
the `from` and `to` of its runs, and the `split` time; every other entry compares the second
half with the first, on the projects with runs in both; `first` and `second` also hold, per
project with runs in the half, the `runs` and `answers` of the half. The halves are written beside the period as `<date>.first.json` and
`<date>.second.json`, period files with `"half": "first"` or `"second"`, `names` and no
comparison.

`settings` holds, per project, the models, the rounds and the schedule of the period: those
of the latest version among its runs, or, for runs older than every version, the rounds and
the schedule the runs show (the largest number of answers of one question–model pair, and
the median gap between their starts), falling back on the first version's schedule for a
single run. `method` states them when the projects differ.

`excluded` lists the runs left out under the run floor, `dropped` the questions a run lost
because their criteria changed later in the period or are unknown for it (§Comparability,
§Matching), and `starts` the runs' start times beside `runs` and `versions`. `asked` holds,
per project, the dimensions and questions of the period with the names and wordings its
runs had: those of the latest version among its runs (the first version for runs older than
every version), less any with no answer expected. `method` and `check` read the period's
dimensions and questions from it, so an edit made after the period's last run belongs to the
next period. A comparison entry's `status` is `compared`, `new`
(nothing to compare with), `new_baseline` (with the `reason` for a question: `criteria` or
`new_intent`; for a dimension, no question comparable) or `no_figure`. Each `mean` and
`presence` entry gives the value now, the previous period's, the move, the range of the
earlier periods it rests on and how many, and whether a change is called (§What counts as a
change); presence values are rates. A design change's `since` is the start date of the
period's first run under the version that made it.

Each `total`, and each model under `by_model`, is a cell: `mean`, `figure` (false when fewer
than 80% of the expected answers were judged), `received`, `judged`, `expected`, `coverage`,
`bands` (answers scored 1–2, 3, 4–5), `presence` (`named` answers out of the `given` ones,
their `rate`, and the mean `position`), `unstable_pairs` (question–model pairs whose answers
in the period differ by two points or more), `domains` (domain → answers citing it) and
`owned` (answers citing an owned domain out of the answers citing any). `names` maps each
model of the period and of the periods compared with it to its public name, which `check`
needs to tell a name from a figure. A question's or a dimension's `mean` is the mean of its
judged answers; a project's `mean` is the mean of its dimension means, the way Sentl
computes a run's score (A4). A period rebuilt from a project's history carries
`"rebuilt": true` and no comparison (see Periods).

### `history/reports.json`

A list of `{date, file, status, period: {from, to}, runs, previous}`, in date order.
`monitor.py check` adds the report as `final` when it passes; `draft` is written by the
unattended mode (M6). `previous` is the date of the period the report compared with, a
rebuilt one included; it is null on a first report, including one that compares the two
halves of its period. `last-report.json` holds `{at, outcome, detail}`, where `outcome` is
`written`, `draft`, `nothing_new` or `below_floor`.

## The stages

### `brief <subject>`

1. **Read what the client gave.** Positioning decks, product sheets, complaint summaries,
   brand-health studies, social-listening reports. List every theme each document raises,
   with the document's name as the origin's `detail`. Origins: `client_material` (a document),
   `client_issue` (a concern the client raised in conversation), `client_analysis` (another
   analysis the client ran). Summarise back in three lines, then ask only about the gaps.
2. **Define the subject.** Label, kind (brand, category, method, organisation), aliases, the
   foils it is measured against with their aliases, the components (an ingredient, a
   material, a technology) with their terms, owned domains, market and language.
3. **Collect search demand** (next section). A theme that only search surfaced joins the
   inventory with origin `search`.
4. **Write `brief.md`**: the subject, the theme inventory (theme, origin, detail, search
   demand), the search-demand table with its source and date or the no-volume statement, a
   proposal for who asks with the reason, and the documents read.
5. **Stop.** Say which themes came from documents, which from the operator, which from search.

### Search demand

**Always, without a key.** `monitor.py demand autocomplete --seeds seeds.json --hl <lang>
--gl <country>` sends each seed to Google's suggestion endpoint in the market's language and
country, as typed and followed by each question stem (Italian: *è, fa, come, perché, quanto,
quale, si può*; English: *is, does, how, why, can, which, vs*; `--stems` for any other
language). Every prefix is recorded with its source and date. Prefixes that could not be
fetched are listed and the command exits 1; running it again fills them.

**With a keyword-data source.** The playbook asks for a capability: monthly volume and
related searches for a keyword, a location and a language. It reads the tool names from the
connected server when the step runs, and writes what the tool returned to `volumes.json`
with the provider, the tool and the date. An export file from such a tool is accepted in the
same shape. `monitor.py demand volumes volumes.json` merges it and then:

- **keeps a related search only when it concerns the subject**: it must contain a relevance
  term (an alias of the subject or a foil, a component term, or a non-stopword of the seed it
  came from). The count of dropped related searches is recorded per keyword, and the agent
  reviews the kept list before the brief;
- **classifies every keyword** as `subject`, `foil`, `component` or `generic`;
- **never adds volumes across classes**: a theme's volume is reported per class, so the
  searches that name the subject stay apart from the searches about a component alone.

**Without a volume source.** The agent says so to the operator when the step runs. `brief.md`
carries the line, and the report's themes section says: *the counts are Google suggestions:
they measure how many ways a theme is phrased, not how many people search it.*

`monitor.py demand import --provider P --tool T --theme X file.csv` reads an export of a
keyword tool (a keyword column, a volume column and, optionally, a `related to` column that
makes a row a related search of the keyword it names), writes `volumes.json` and merges it as
`volumes` does. A JSON file in the `volumes.json` shape is merged as it is. A volume that is
not a whole number refuses the file (exit 2), and so does a theme absent from `seeds.json`; a
refused file changes nothing.

`monitor.py demand summary` prints, per theme, the distinct suggestions, the volume per
class or none, and the top queries (by volume when there is one, else the first suggestions).
A keyword that appears twice in a theme counts once. `design` copies it into each theme's
`search` block.

### `design`

The steps run in the order the report tells them:

1. **Themes.** Merge duplicates; a theme with no origin is traced or dropped.
2. **Dimensions.** Each comes from one or more themes and is named the way the client names
   it. Five to seven per project, at least two questions each. A theme left out says why in
   `design_rationale`.
3. **Projects.** A project groups the dimensions the reader takes one decision with. **One
   study project is one Sentl project**, because Sentl computes one score per run per
   project: a project that mixes questions naming the subject (read by mean score) with
   questions naming no brand (read by presence) produces a score nobody can read. Projects
   also differ in models, rounds and schedule.
4. **Who asks.** `generic_consumer`, `personas`, `stakeholders` or `mixed`, with the reason.
   With personas or stakeholders, each question carries the `persona` in plain words.
5. **Questions.** Written as the person types them, in the market's language, starting from
   the top queries of the theme. A question that names no brand contains no alias of the
   subject or of a foil. Where a dimension's searches lean one way, the opposite question is
   added and the two are paired. The market is named in the question when it matters,
   because Sentl sets no location for the researcher models.
6. **Rubrics.** Five anchors per question, each an observable property of the answer, adapted
   from `catalogue.md` (the dimension catalogue, which arrives with M4). On a question that
   names no brand, 2 is *not mentioned* and 1 is *named negatively or advised against*. The
   axis is chosen before the anchors are written. Judge instructions carry the dated facts
   the judge needs to recognise an outdated or wrong statement.
7. **Narrative.** Research question (neutral: what is monitored, never one valence of it),
   purpose, audience, each project's question and decision, each design choice with its
   reason, score axis.
8. **Models, rounds, schedule, report cadence.** From the saved `list-ai-models` response.
   Rounds × runs per report period (from `schedule` and `report_every`) should reach three
   answers per question and model, so a period's figure does not rest on a single answer.

`monitor.py validate` refuses: a schema error; a field over Sentl's limits; a dimension fed
by no theme or a theme with no origin; an alias in a question marked as naming no brand; a
dimension with `search_lean` and no question of the opposite framing; a pair whose two
questions sit in different dimensions or share a framing; duplicate keys; two questions with
the same text in one dimension or two dimensions with the same name in one project (results
identify questions by dimension name and text); a model id absent from `list-ai-models`; a
narrative without research question, purpose, audience and reason, or a project without its
question and decision. It warns on: dimensions per project outside 5–7, fewer than two
questions in a dimension, a project mixing branded and unbranded questions, fewer than three
answers per question and model per report period.

`monitor.py review` writes `study-review.md`: the narrative, the theme inventory with
origins and search demand, projects and dimensions with question counts, every question with
its persona, framing and rubric, and the credit estimate from the models' tariffs.

**Revising a study.** A question keeps its `key` when it is reworded with the same intent
(lineage `reworded`), and gets a new key when the intent changes (`new_intent`; the old key
is retired). A change to the rubric, the judge instructions or the facts is `criteria`.
The operator confirms each classification at the gate. Comparison across versions follows
these labels (see Comparability).

### `setup`

1. Preflight: `list-organizations` (connection and role), `get-organization-tool` (credits,
   subscription).
2. Ingest every completed run not yet in `history/runs/` for projects that already exist;
   runs Sentl cannot return go to `history/unavailable.json` and do not block the save.
3. New project: `create-project-tool` (it is created paused), then
   `update-project-settings-tool` for any setting the create call did not take.
4. Questions: `monitor.py payload` builds the `save-project-questions-tool` arguments, keeping
   every id from `sentl.json`. The tool is called with `dry_run: true` first and the changes
   are shown to the operator; then for real. `delete_missing` is never sent unless the
   operator approves the listed deletions. A dimension to drop is archived.
5. Bind: `get-project-tool`, saved; `monitor.py bind` records the ids in `sentl.json` and a
   `setup` version in `history/versions/`.
6. `estimate-run-tool`: credits per model, judging credits, available credits, whether the
   run can start. Shown to the operator.
7. Only on the operator's explicit go: `trigger-run-tool` for a first run, and
   `update-project-settings-tool` with `is_active: true` for the schedule. If a run is already
   open, the skill follows it and starts nothing.
8. `project-edit-link-tool` gives the operator the project's page in Sentl.

### `adopt <project>`

`list-projects-tool` to find it, `get-project-tool` saved, and the results of the project's
latest completed run saved. `monitor.py adopt` writes `study.json`, `sentl.json` and an
`adopt` version. It refuses a saved project in which a question text or a dimension name of
that run is not found (see Responses saved by the assistant), and the assistant saves the
project again. Every question gets a key; every dimension a theme placeholder. The agent
then asks the operator for what Sentl does not hold: purpose, research question, who asks
and why, the origin of each dimension's themes, subject aliases, foils with their domains and
owned domains, market and language, report language, `report_every`, who wrote the criteria
and when, and for the questions whose facts carry a figure or a name (prices, fees, people in
charge) the current and outdated terms.
`list-runs-tool`, saved and read by `monitor.py runs`, names the latest completed run by start
time and the runs available; the first `report` rebuilds the periods before the first one from
them (see Periods).

### `report`

1. `list-runs-tool` for each project in `sentl.json`, saved; `monitor.py runs` prints the
   runs to fetch, ordered by start time, never by their position in the listing, which is
   newest first with exceptions. New runs: completed (`completed` or
   `completed_with_warnings`) and not in `history/runs/`, started after the last run of the
   previous report and up to the end of the report's date; on the first report, those started
   in the last `report_every` interval and the K = 4 intervals before it. Runs in
   `history/unavailable.json` are requested again. Runs not final yet and statuses never seen
   are listed apart and not fetched (§Responses from Sentl). The listing has no paging (gap
   G8): when its oldest run started after the start of the window, `runs` warns that it may
   be cut. None: write `nothing_new` to `last-report.json` and stop.
2. `get-project-tool` for each project, saved; `monitor.py detect` compares it with the latest
   version and records a `detected` version on a difference. With the operator present it
   runs with `--dry-run` first: a reworded question keeps its key unless the operator says it
   now asks something else, and is then recorded with `--new-intent <key>`.
3. `get-run-results-tool` for each new run, saved to `inbox/`; `monitor.py ingest` writes the
   run snapshot. A saved response that does not parse as complete JSON is refused, since a
   host that truncates output cuts it mid-string. Fewer answers than expected count against
   coverage. A run whose results come back as a server error goes to
   `history/unavailable.json`.
4. `monitor.py period` builds the period: the runs since the previous report, pooled; on the
   first report, the rebuilt periods as well, or the two halves of the period when there is
   no earlier one (see Periods). It computes the cells, the
   comparison with the previous period and the range of the K periods before (K = 4), and
   writes `history/periods/<date>.json` and `history/material/<date>.md`. It refuses a study
   without `report_every`.
5. `monitor.py method` writes the method sections (`purpose`, `themes`, `dimensions`,
   `questions`, `scoring`) from `study.json`, the versions and the period, and lays out the
   sections in the order §The report sets: the first-report order when
   `history/reports.json` holds no final report, the later-report order otherwise.
   `list-ai-models` gives the models' public names.
6. The agent reads the material and the answers and writes `findings` and `changes`, then
   the `summary` from them.
7. `monitor.py check reports/<date>.md` (below). Pass: the report is added to
   `history/reports.json` with status `final`. Fail, when unattended:
   the file is saved as `reports/<date>.draft.md`, status `draft`, and `last-report.json`
   says which check failed.
8. In the chat, never in the report: the runs covered, runs left out, unmatched responses,
   versions detected, facts older than 90 days.
9. Optional, when the report is presented as a deck: `monitor.py charts` writes the report's
   figures as md2 chart tables (§Charts for a deck).

### `snapshot <subject>`

A one-off check in its own folder: a small study, one Sentl project, one run, one report,
and nothing left running in Sentl. `study.json` carries `"kind": "snapshot"`. Invoked again
in the same folder, the route resumes at the first step whose output is missing: no
`study.json` → design; no binding in `sentl.json` → project; no run → cost and go; a run
open → follow it; a completed run not in `history/runs/` → report; no `closed` in
`sentl.json` → archive.

1. **Preflight.** `list-organizations` (connection, and the Owner or Admin role in the
   organization the operator picks), `get-organization-tool` (credits, subscription),
   `list-projects-tool` (the operator is told of any project already named after the
   subject).
2. **Subject and facts.** What the reader needs to decide; the subject's label, kind,
   aliases, competitors as foils, owned domains, market and language; 5–10 facts from
   primary sources, each with its source and the date it was read. `catalogue.md` lists the
   facts each dimension needs. A statement taken from an AI answer is not accepted as a fact.
3. **Dimensions.** 4–5 entries of `catalogue.md`, chosen from what the reader needs to
   decide and by the catalogue's rules: at least one dimension naming no brand unless the
   operator wants reputation only; a dimension whose facts cannot be found is replaced by
   another. Each dimension records its catalogue id, and the reason it was picked goes in
   `design_rationale`.
4. **Questions and rubrics.** One question per dimension, written as the person types it,
   from the catalogue entry's pattern, in the market's language. Five anchors per question,
   adapted from the entry; judge instructions carry the dated facts. Researcher models are
   the operator's choice from a saved `list-ai-models` response, with each model's tariff
   shown; one round; no schedule.
5. **Gate.** `monitor.py validate` in snapshot mode (below) and `monitor.py review`, which
   writes `study-review.md` with the questions, the rubrics and a credit estimate from the
   tariffs. Stops for the operator's approval.
6. **Project.** `create-project-tool` with the name `Snapshot · <subject> · <date>` and
   neither `is_active` nor `schedule_frequency`, so the project is created paused with no
   schedule. `save-project-questions-tool` with `dry_run: true`, then for real.
   `get-project-tool` saved; `monitor.py bind` records the ids and a `setup` version.
7. **Cost.** `estimate-run-tool`: credits per researcher model, credits for judging, the
   total, the credits available in the organization, and whether the run can start. Shown
   to the operator in Sentl credits. Stops for the go.
8. **Run.** On the go, `trigger-run-tool` once. `list-runs-tool` follows the run until its
   status is final. If the session ends first, the next invocation follows the same run and
   starts nothing.
9. **Report.** `get-run-results-tool` saved to `inbox/`; `monitor.py ingest`, then `period`
   on the one run, with no comparison, then `method`. The agent writes `findings`;
   `monitor.py check` verifies the report in the snapshot order of §The report. Written to
   `reports/<date>.md`.
10. **Archive.** The Sentl MCP has no tool that archives or deletes a project (gap G16).
    The route calls `update-project-settings-tool` with `is_active: false`, so no scheduled
    run can start and no further credits are spent, and writes `closed` to `sentl.json`.
    `project-edit-link-tool` gives the operator the project's page in the Sentl web panel,
    where the operator archives or deletes it by hand. Deleting loses nothing the report
    needs, because the run is saved in the snapshot folder. Once the MCP can archive a
    project, this step archives it and records `archive: mcp`.

**`validate` in snapshot mode** refuses: fewer than 4 or more than 5 dimensions; a
dimension with more or fewer than one question; a dimension without a catalogue id or with
an id absent from `catalogue.md`; a field over Sentl's limits; an alias in a question marked
as naming no brand; a model id absent from `list-ai-models`; rounds other than 1; a
schedule; a narrative without research question and purpose. It warns when every dimension
names the subject. The study rules on themes, origins, pairs, search lean and answers per
period do not apply.

**Reading a snapshot.** Its one project mixes questions that name the subject with questions
that name no brand, so Sentl's run score mixes two readings. The report reads each dimension
on its own: by its score when the question names the subject, by whether and where the
subject appears when it names no brand. It gives no figure for the whole project. The run
floor of §Coverage does not apply to a snapshot's single run; a dimension under 80% judged is
shown without a figure, and the operator is told.

## MCP mapping

The Sentl tools by route. R reads, W writes. No route calls a write tool without the
operator's approval in that session.

| Tool | brief | design | setup | adopt | report | snapshot |
|---|---|---|---|---|---|---|
| `list-organizations` (R) | preflight | preflight | preflight | preflight | preflight | preflight |
| `get-organization-tool` (R) | | | credits, subscription | | | credits, subscription |
| `list-ai-models` (R) | | models and tariffs | ids still offered | | public names | models, tariffs, public names |
| `list-projects-tool` (R) | existing project for the subject | | | find the project | | existing project for the subject |
| `get-project-tool` (R) | | | bind, edits | read the project | detect edits | bind |
| `project-edit-link-tool` (R) | | | link for the operator | | | link to archive by hand |
| `estimate-run-tool` (R) | | | credit estimate | | | credit estimate before the go |
| `list-runs-tool` (R) | | | pending runs | runs available | new runs | follow the run |
| `get-run-results-tool` (R) | | | ingest pending runs | | ingest | ingest |
| `create-project-tool` (W) | | | new project, paused | | | snapshot project, paused, no schedule |
| `update-project-settings-tool` (W) | | | settings, activation on go | | | pause after the report |
| `save-project-questions-tool` (W) | | | dry run, then save | | | dry run, then save |
| `trigger-run-tool` (W) | | | first run on go | | | the single run, on go |

`brief` also uses Google autocomplete and, when present, the keyword-data source.

## History and comparison

### Matching responses to questions

`get-run-results-tool` identifies a response by the question's text and the dimension's
name, with no ids and no round number. The results of a run show the text asked when it ran
(A1). `ingest` matches each response against the version in force at the run's start; inside
a detection window it also tries the previous version. The run then takes the version of the
two that explains it: the one whose models and rounds are those of its responses, then the
one with fewer questions that the run asked and the version does not hold, or that the
version holds and the run never asked, so a run made before a question or a dimension was
added keeps the earlier version; the later one on a tie. A response that matches only the
other version's text is `version`. A tie leaves the rubric of the run's answers unknown for
every question whose criteria changed between the two versions: the run lists them in
`criteria_unknown`, and `period` leaves them out of it, so such a question's new baseline
starts from the first run known to be under the new criteria. A run older than the first recorded version is matched
against that version alone, so a question reworded before it was recorded leaves that run's
answers to the earlier wording `unmatched`. Texts are compared after normalization: Unicode
NFKC, typographic quotes and apostrophes folded to plain ones, whitespace collapsed. A
response that matches nothing is kept as `unmatched`, excluded from every figure and listed
to the operator. This is why `validate` refuses duplicate texts in a dimension and duplicate
dimension names in a project.

### Responses saved by the assistant

The host saves a large response to a file, and the assistant copies the file to `inbox/`:
the results of a run of 39 answers came to about 250,000 characters, and Claude Code saved
them as complete JSON. A small response (`get-project-tool`, `list-runs-tool`,
`list-ai-models`) arrives inline, and reaches `inbox/` only by the assistant writing it out,
which can alter a character. Three rules contain it:

- matching uses the normalization above;
- `adopt` and `bind` refuse a saved project in which a question text or a dimension name of
  the project's latest completed run is not found, and the assistant saves it again; with
  no completed run the check is skipped and the operator is told;
- `payload` never sends a text that differs from the one in the latest saved
  `get-project-tool` response only by that normalization, so a transcription never rewords
  a question in Sentl.

### Responses from Sentl

`scripts/sentlmon/schema.py` states the fields, types and ranges the skill reads from each
tool's response. `adopt`, `detect`, `runs` and `ingest` check a saved response against it, and
`period` and `method` check the saved `list-ai-models`, before anything is written. A field
that is missing, renamed, of another type or out of range is refused with exit 5, naming the
tool, the field, what was expected and what was found; the same change in many items is
listed once with their count. Fields the skill does not read, or only copies into the run
snapshot (`trigger`, `finished_at`, `error`, `sentiment`), are accepted with any value. A file
that holds another tool's response (its top-level key is that tool's), or that cannot be read,
is refused with exit 2: it is to be saved again.

| Tool | What the skill reads |
|---|---|
| `get-project-tool` | under `project`: `id`, `name`, `schedule_frequency` (text or null), `rounds` (1 or more), `is_active` (optional), `researcher_model_ids`; `dimensions` with `id`, `name`, `archived` (optional) and `questions`, each `id`, `question`, `label` (optional, text or null), `grading_rubric` (null, or an object whose keys are anchors from `1` to `5`, each a text or null: Sentl does not require every anchor), `additional_instructions` (optional, text or null) |
| `list-runs-tool` | `project_id`; `runs`, each `id`, `status` (any text), `started_at` (null only on a run that is not completed) |
| `get-run-results-tool` | under `run`: `id`, `project_id`, `status` (a known status), `started_at`, `reputation_score` (1 to 5, or null); `responses`, each `id`, `model_id`, `dimension`, `question`, `answer` (text or null), `judge_score` (an integer from 1 to 5, or null), `sources` (a list, or null for none), each `url` and `title` (optional, text or null). The results of a run not final yet are read for `id` and `status` only |
| `list-ai-models` | under `researcher_models`: each model id with its public `name` |

Times are ISO 8601; a time written without a time zone is read as UTC. The known statuses are `completed` and `completed_with_warnings`, final,
and `pending`, `queued` and `running`, not final yet (A2). `runs` lists a status outside them
as never seen, apart from the runs not final yet, and fetches neither; `ingest` refuses results
with such a status. Every error Sentl returns reads "An internal server error occurred.",
whatever its cause, so the playbooks call the tool once more and then record the run as
unavailable (`get-run-results-tool`) or stop (any other tool). Any other unexpected error in
`monitor.py` exits 6 with a one-line message; `--debug`, before or after the command, or
`SENTL_MONITOR_DEBUG=1`, prints the traceback. Ctrl-C exits 130 with one line. `runs` lists the
runs not final yet and the statuses never seen among the runs of the report's window and those
with no start time, so a run left open long ago is not reported at every report.

### Periods

A report covers the completed runs started after the last run of the previous report. With a
weekly schedule and a monthly report, a period pools about four runs; with matching
cadences, a period is one run and the comparison is run against run. Pooling gives each
question–model pair several answers, which a single run with one round cannot.

The first report covers the runs started in the last `report_every` interval before it: the
seven days, or the month, that end with the report's date (a monthly report dated the last
day of a month covers that calendar month). When the project has earlier runs (an adopted
project), the first report also rebuilds the K intervals before that one from them, one
period per interval, dated the interval's last day, written to `history/periods/` with
`"rebuilt": true` and given no report of their own. The first report then compares with them
as a later report compares with earlier periods. Runs Sentl cannot return are left out of a
rebuilt period and listed; so are runs under the run floor; an interval with no run left
gets no period.

With no earlier period at all, a monitor started less than one interval before its first
report, the first report compares the two halves of its own period when its runs span at
least 14 days. `period` splits the period's runs, as the period keeps them (§Comparability:
the runs of the latest criteria), at the midpoint between the first run's start and the end
of the report's date, and compares the second half with the first by §Comparability and §What
counts as a change, with the thresholds for a single previous period. A project with runs in
one half only is not compared, and the report says so; when no project has runs in both
halves, the report is the first measurement. The design changes stated are those made inside
the whole period, between its first run and its last, wherever they fall, a dimension archived
before either half's latest version included; assistants added or removed come from the
versions `detect` recorded and, for runs older than every version, whose model lists only say
who answered, from the second half against the first. The halves are
written beside the period with `"half": "first"` and `"second"` and get no report. The
insights the findings are written from (episodes, fact currency, presence by run) still read
the whole period; an episode is given beside a change between the halves, with its first
date, when it lies on the side of the range the change moves to and its last run starts after
the split; the material notes it once, under its question.
When the runs span less than 14 days, `period` tells the operator there is no earlier period
and the report's `changes` section says this is the first measurement. Building the first
period again replaces the rebuilt periods and that date's halves; the halves of another date
stay with its report.

A later report covers, for each project, the completed runs started after the last run of
the previous report and up to the end of the report's date. The periods it compares with are
those of the earlier reports in `history/reports.json` and the rebuilt ones, the latest K.
The second report compares with the whole first period, never with its halves.

### Comparability

| Change between the two periods | Score and presence deltas | Verdict changes | The report says |
|---|---|---|---|
| none | shown | listed | — |
| question reworded, same key | shown | listed | the question was reworded on that date |
| question with a new intent (new key) | not computed: new baseline | not listed | the question replaced an earlier one |
| rubric, judge instructions or facts changed | not computed: new baseline | not listed | the criteria were updated on that date |
| researcher model added or removed | computed on the models present in both periods | models in both periods | which assistants changed |
| rounds changed | shown | listed | — |
| dimension added | new baseline | — | the dimension is new |
| dimension archived | — | — | the dimension is no longer measured |

A period that contains two versions of a question with a criteria change uses the runs of
the latest version only.

A dimension is compared on the questions asked in both periods whose criteria and intent did
not change, and on the models present in both, so a model added or a question restarted
changes neither side of the comparison. The range of earlier periods goes back to the last
new baseline of those questions, and stops at the first period missing one of those
questions or models, so every value of the range rests on the same questions and
assistants. A run with no version counts as judged under the first recorded version. A
dimension the earlier period asked, whose questions its runs dropped for a criteria change, is a
new baseline; one the earlier period never asked is new, and its design line says so. A question added in Sentl (`created`) is a new baseline,
like a new intent. New and lost domains are counted on the questions asked in both periods
and the models present in both.

### What counts as a change

- **Dimension or question figure.** A change is called when the period's value lies outside
  the range of the K previous periods (K = 4, or as many as exist) and differs from the
  previous period by at least 0.3 points (presence: by at least 10 percentage points). With a
  single previous period, the threshold is 0.5 points (presence: 20 points). Smaller moves
  are reported as unchanged.
- **Project figure.** The mean of the project's compared dimensions, each on its compared
  questions and models, follows the same rule as a dimension's figure.
- **Fact currency.** For a question whose facts have terms, the share of its answers stating
  a current term (§Insights) follows the rule for presence. Earlier periods that counted
  other terms are not in its range.
- **Verdict.** Each question–model pair has a band from its unrounded mean in the period:
  unfavourable (below 2.5), mixed (2.5 and above, below 3.5), favourable (3.5 and above). A
  pair whose band changed is a verdict change when its mean also moved by at least the step
  a change of the question's figure needs (0.3 points, 0.5 with a single previous period or
  between the two halves), so a mean of 3.4 that becomes 3.5 is not one. It is listed with
  the two answers that show it: in each period, the pair's answer whose score is nearest the
  pair's mean, the latest on a tie.
- **Sources.** Per dimension, a domain is new when at least two answers cite it in this
  period and none did in the previous one; lost in the opposite case. Domains are compared
  rather than URLs, because pages change address. Owned domains and their subdomains are
  marked. The new and the lost are each listed five per list across all dimensions and
  projects: the five cited by most answers, ties broken by domain name.
- **Instability.** A pair whose answers in one period differ by two points or more is
  unstable. Its figure is reported with that note; it says where the assistants have no
  settled answer.

### Insights

The figures that explain a mean, each computed by `period` and stated as `report/INSIGHTS.md`
describes.

- **Fact currency.** An answer states a term when the term, folded like an alias, appears on
  word boundaries and not inside a longer number ("10 €" is not in "12,10 €", "£2" not in
  "£2.10"); a space between a number and a currency sign is optional on both sides. Answers are counted as stating a current term only, an outdated term only,
  both, or neither; the current share is the answers stating a current term out of those
  stating any.
- **Sources behind a fact or a score.** Four groups of a question's answers: those stating
  only an outdated term, those stating a current one, those scored 1–2 and those scored 4–5.
  Each group lists the five domains cited by most of its answers, ties broken by domain name,
  each with its count and share in the group and in the opposite group (outdated against
  current, 1–2 against 4–5). A share is out of the group's answers citing at least one source.
  A pair of groups is listed only when both groups have an answer citing a source; otherwise
  neither list of the pair is.
- **Readings.** The rounds of a question–model pair in one run that cite the same ordered list
  of pages are one reading. A page is its host and path without query or fragment; a grounding
  redirect, whose URL differs on every call, is the domain its title names. An answer citing
  nothing is a reading of its own.
- **Episodes.** For a question's mean and its current share, run by run: a value outside the
  range of the runs before it, in this period and the previous one and at least five of them,
  for three runs or more in a row on the same side. The values are computed on the
  assistants every run of the series has, and an earlier run judged under other criteria for
  the question (§Comparability) is left out. The range is the one before the first of those
  runs; the episode closes at the first value back inside it, or ends as a switch when the
  value jumps to the other side. A first period with no previous one reads its own earlier
  runs. The close date is the first run back inside the range; it says nothing about the
  runs after it: the later runs of the period that lie on a closed episode's side of its
  range are listed with it, so a report does not describe the measure as outside the range
  only during the episode.
- **Presence by run.** For a question whose text does not name the subject, the answers naming
  it in each run.
- **Missing evidence.** A phrase list per market language (`i18n.MISSING_EVIDENCE`) finds the
  answers in which the assistant says it found no source of the kind asked for. Each phrase is
  anchored on the assistant's own search (the first person, "the provided results", evidence
  not available or limited as such), so product sentences such as "limited integrations" do
  not match; a phrase in a sentence whose subject is a third party (`i18n.THIRD_PERSON`:
  users, customers, utenti, clienti) does not count. Per question–model pair: the answers found, and the mean with
  and without them.
- **Who wrote the sources.** Each cited domain is owned, a foil's (subdomains included) or a
  third party's. Per cell: the answers citing each kind out of those citing any source, and
  the foil pages cited most.
- **Presence changes.** For a question whose presence change is called, the domains cited by
  the answers naming the subject in this period and by no answer to the question in the
  previous one, and the reverse, on the questions and models compared; the five cited by
  most answers in each list, ties broken by domain name.

### Coverage

A run with fewer than 90% of its expected answers judged is left out of the period and
listed to the operator. A response with no answer is not judged and counts against it. A
dimension whose judged answers in the period are under 80% of the expected ones shows its
answers without a figure, with one line saying how many were judged. A missing figure is
never a zero.

A dimension's figure is the mean of its judged answers. A project's figure is the mean of
its dimension figures, the way Sentl computes a run's score, so the report and the Sentl
web panel show the same number for a run. Sentl's run score is recorded in the run snapshot
beside the figure computed for that run; when the two differ by more than 0.05, the
operator is told.

## The report

`reports/<YYYY-MM-DD>.md`, in `report_language`, self-contained: a reader who never saw an
earlier report understands it. The method sections are regenerated from `study.json` each
time, so they describe the questions actually asked in the period. Sections are numbered in
the order they appear.

### Sections

| Key | Section | Written by |
|---|---|---|
| — | Title: the research question; subject, period, date | `method` |
| `purpose` | What we did and to what end: the purpose; the assistants by public name; the questions asked, in positive and negative where paired, in one sentence, or one line per project (its questions, assistants, times each question is asked per run, how often it runs) when the projects differ in any of these; the answers collected and scored in the period; that each answer's cited sources were recorded | `method` |
| `themes` | Where the themes came from: themes grouped by origin, the themes that share an identical origin (kind and detail) on one line; search demand per theme with its source and period, volumes per class, or the no-volume statement. A study adopted without a brief: the themes with the origins the operator gave, and one line saying no search data was collected | `method` |
| `dimensions` | The dimensions and how we reached them: projects with their question and decision, the dimensions of each with the themes they come from, who asks and why. In a snapshot: each dimension, what it measures and why it was chosen for the subject | `method` |
| `questions` | The questions: per dimension, verbatim, paired questions side by side | `method` |
| `scoring` | How the answers are scored: a rubric that several questions share stated once for them with all five anchors, and per dimension what a 5, a 3 and a 1 mean for the other questions; who wrote the criteria and when; that an independent model in Sentl applied them; what counts as a change between periods and the verdict bands; the score axis; what a high or a low score does not mean | `method` |
| `summary` | In short: three to five plain sentences, a bulleted list, each stating one point with its figure | the agent, written last, from the findings and changes |
| `findings` | What the assistants say, dimension by dimension, in chapters by project | the agent |
| `changes` | What changed since the last report: the period compared with, changes in the answers, then changes in the design and how they affect the comparison | `method` writes the period compared with and the design changes; the agent writes the changes in the answers, from the output of `period` |
| `limits` | Snapshot only: one question per dimension and one answer from each assistant, on one date; what a monitoring study adds (several questions per dimension, paired questions, repeated runs compared period by period) | `method` |

### Order

| Report | Sections after the title |
|---|---|
| First report on a study: `history/reports.json` holds no final report before its date | `purpose`, `themes`, `dimensions`, `questions`, `scoring`, `summary`, `findings`, `changes` |
| Every later report | `summary`, `changes`, `findings`, `purpose`, `themes`, `dimensions`, `questions`, `scoring` |
| Snapshot | `purpose`, `dimensions`, `questions`, `scoring`, `findings`, `limits` |

The first report tells how the study was built before what it found, because the reader
meets the method there for the first time, and the summary stands between the method and
the findings. From the second report on, the reader opens it for what moved: `summary`,
`changes` and `findings` come first, and the five method sections close the report, with the same content they would have in a first report, so each report still
stands on its own. `method` takes the order from `history/reports.json`. A first report on
an adopted project keeps the first-report order even when it compares with rebuilt periods.

**`findings`, per dimension:** a title that states what the person asking is told, never a
score; one or two verbatim excerpts, each with its question and assistant; the domains those
answers cite, the subject's own first, then the most cited, five in all; the
dimension's figure with its coverage in the body; the insights the material
holds for it (§Insights), each in one sentence with its figure; last, one line on what it means
for the client. Every dimension gets its section, including those where nothing moved.

**`changes`, on the first report:** one line saying this is the first measurement and the
next report compares against it. When periods were rebuilt from the project's history, the
section compares with them instead, as a later report does. When there is no earlier period
and the runs span at least 14 days, the section opens with a line, written by `method`,
naming the two halves of the period and their dates and, for each project, the runs and the
answers in each half; the changes in the answers compare the second half with the first.

**`changes`, when it compares:** a line naming the period compared with (and, when it was
rebuilt, that no earlier report exists), or the two halves; the changes in the answers,
written by the agent: the project, dimensions and questions whose change is called, with the
first date of an episode that explains one, the facts whose current share changed, each
verdict change with its two answers quoted, the domains new or lost, the domains that came or
went with the subject where its presence changed, and one line saying the rest is unchanged;
then one
line per design change, written by `method` as the Comparability table says: a reworded
question with both wordings and the date, a new intent, new criteria, assistants added or
removed with the assistants the comparison rests on, a dimension new or no longer
measured.

**Never in a report:** credits or any price; run, project or question ids; question keys;
file names; model ids (the public name is used); the skill's own steps or checks.

**`monitor.py check`** fails the report when: a quoted excerpt is not a verbatim substring
of an answer in the period's runs; a figure is not in the period metrics; a dimension of the
study has no `findings` entry; an id, a key, a model id, a file name or a credit figure
appears; a section is missing, or the sections are not in the order the table above sets for
the report (first, later or snapshot); a snapshot report carries a figure for the whole
project. The rules it applies:

- **Excerpts** are Markdown blockquote lines in `findings` and `changes`. An excerpt may
  skip text with `[…]`; each piece, after the normalization of §Matching (dashes folded to a
  hyphen as well) and with Markdown emphasis and citation markers such as `[1]` dropped, must
  be a substring of one answer in the period's runs, or, in `changes`, of the period compared
  with, where a verdict change starts. A failure says where the excerpt stops matching its
  closest answer.
- **Figures** are the numbers in `findings` and `changes` written with a decimal separator
  and the percentages. A decimal uses the report language's separator (a point in English, a
  comma in Italian) and has one decimal; a percentage is whole. Each must equal a value of
  the period file rounded the same way: its cells and, for a change, its comparison (the
  values now and before, the move, the range, the pair means of a verdict change); `changes`
  may also cite the overall figures of the period compared with, or of both halves. The insights' counts and
  shares of answers may be cited whatever the coverage; their means only where the question
  has a figure; the material prints no mean for a question without one. A fact term of the
  study quoted in «» is read as text, not as a figure. A dimension's entry may cite its own
  dimension's figures, its questions'
  insights and its project's overall figure, never another dimension's; a dimension shown
  without a figure has no mean to cite. A count of answers written "N su M" or "N of M" must be
  a pair of the period (judged of expected, named of given, and the like). Other integers are
  not checked: they are dates and points of the scale. Text inside «» that quotes a question
  or an answer, and the assistants' public names (which can carry a version number), are not
  read as figures.
- **Findings headings** carry no figure.
- **An episode's close.** A sentence fails when a word for "only" (only, solely, exclusively,
  just; solo, soltanto, solamente, unicamente, esclusivamente) comes before a closed episode's
  span or its first, last or close date in the same clause (no `, ; : . ! ?` between them, the
  date within about 40 characters), later runs of the period lie on the episode's side, and the
  sentence does not name all of them. A date is read as the report writes it, day and month with
  the year optional ("14 October", "October 14"), and a span as "14–16", "dal 2 all'8", "from 2
  to 8" or "tra il 2 e l'8"; quoted text is not read, and a paragraph's lines are joined first.
  A finding is read against its own dimension's episodes, the summary and the changes against all
  of them. The later runs' values may be cited. A period whose closed episodes do not record their
  later runs was built before this rule and is refused (exit 2) until `period` builds it again.
- **The halves.** A report whose period compares its two halves must keep, in `changes`, the
  line `method` wrote naming them, their dates and each project's runs and answers. `check`
  refuses the report when a half's file is missing, since the figures it allows come from it.
- **The summary** may cite any figure of the period, any dimension's or question's included,
  and in a later report the figures of its comparison; it holds no excerpt, and its
  `[[summary]]` marker left in place fails like any other.
- **Counts** "N of M" are checked when a word for answer, or for citing (cite, cites, citing,
  cita, citano), follows within the sentence.
- **Ids** are integers that look like counts, so a Sentl id of the study is refused only
  where a word names it (`run`, `id`, `#`, and the words for project, question and dimension
  in the report's language). Question keys, model ids and file names are distinctive strings
  and are refused anywhere; dimension and project keys are ordinary words and are not
  checked. A credit figure is a number next to the word for credit.
- **Findings entries** are headed `### <dimension name>: <what the person asking is told>`
  (`####` under a `### <project name>` heading when the study has several projects, so two
  projects may have dimensions of the same name: each entry cites its own project's
  figures, and each project needs an entry for each of its dimensions). `method` leaves a
  `[[...]]` marker for each, and a report that still holds one fails.

## Charts for a deck

`monitor.py charts --date D` writes `reports/<D>.charts.md` from the period file of `D`, for an
operator who presents the report as a deck. The report does not include the file, and `check`
does not read it. Each chart is an md2 `:::chart` block (a Markdown table under a
`:::chart <type> --title "…"` line, closed by `:::`) under a `##` heading that says, in the
report's language, what the chart shows and the period or the halves it covers, with the bounds
the report prints for them; a project whose own runs start or end on other days than the period's
has its first and last run days after its name. The first column holds the labels and each further
column a series; a series is labelled with the report's bounds, never a project's own days. Values are bare numbers with a point, rounded
as `check` rounds them: a mean with one decimal, a share in whole percent; the title carries the
unit.

| Chart | md2 type | Rows | Series | Values |
|---|---|---|---|---|
| Profile, per project | `radar` and `bar` | the dimensions | the previous period and this one, or the two halves; this period alone on a first measurement or when no dimension of the project is compared | each compared dimension's `mean` in the comparison, `previous` and `now`, on the questions and assistants both sides share; when those differ from either side's own (an assistant added or removed, a question not comparable), the heading names the assistants and the questions left out; on one series, each dimension's figure |
| By assistant, per project with more than one assistant | `bar` | the dimensions | the assistants, by public name | each dimension's mean by assistant over the period |
| Fact currency, per question with current terms | `line` | the project's runs in the period, by start day in UTC, with the start time in UTC where two runs share a day | one | the share of the answers stating a current term, of those stating a term |
| Presence by run, per question whose text does not name the subject | `column` | the runs, labelled as for fact currency | one | the share of the answers naming the subject |
| Sources behind a fact or a score, per pair of groups the period lists | `bar` | the five domains of the first group, then those of the second not already listed | the two groups | each group's share of its answers citing a source that cite the domain |

md2 reads an empty cell as 0, so a value that does not exist is left out, never written. Left
out, and listed to the operator on stdout: a chart with no row; from the profile's two series, a
dimension not compared, and from one series a dimension without a figure; from the chart by
assistant, a dimension on which an assistant has no figure; from the fact line, a run with no
answer stating a term; from the presence columns, a run with no answer; a chart by run with fewer
than two runs left (the fact stated in one run only), since md2 draws a line between two runs or
more; the radar of a profile with fewer than
3 or more than 12 dimensions, which md2 does not draw (the bar keeps them).

## Scheduling

Two clocks run independently. Sentl runs the measurement: the project's `schedule_frequency`
(`daily`, `weekly`, `monthly`) once `setup` activates it. The host runs `report`:

- **A local scheduler** (cron, launchd, a systemd timer) starts a headless assistant in the
  study folder with the `report` route. The Sentl MCP connection uses the token method,
  because OAuth needs a browser and a login unused for 30 days must be repeated.
- **An assistant's own scheduler** (a scheduled cloud agent) needs the study folder to
  persist between runs: keep it in a private repository the routine commits to.

`report` is idempotent: run twice on the same runs, it writes one report and then
`nothing_new`. Unattended, it asks no question and treats every gate as described in the
`report` stage.

## Hosts without a lasting folder

On claude.ai and ChatGPT the scripts run in a sandbox whose files are deleted when the
conversation ends; `monitor.py doctor`, the first command of every conversation, reports it.
There the study travels between conversations as a pack: one zip the user downloads at the end
of a route and attaches to the next conversation, or keeps in the Project's files where the
host has Projects, replacing the previous pack. A conversation unpacks the pack with the latest
date before its next command and packs the study again once `check` passes (in `adopt`, once
the operator's answers are written); `check` passing in a sandbox prints a reminder to do so.
The report, its PDF if one was made, and the pack are copied to the folder the host offers for
download. Claude Code, opencode and Codex keep the folder on disk and pack only to move or
archive a study.

### The pack

`monitor.py pack --study S [--full] [--out FILE|FOLDER]` writes
`<study folder name>-<last final report date>.sentl-pack.zip`, or
`<study folder name>.sentl-pack.zip` before the first final report, next to the study folder;
`--out` names the zip or the folder to write it in. It holds `manifest.json` and the state the
next report reads:

| Held | What the next report reads it for |
|---|---|
| `study.json`, `sentl.json` | the operator's answers and the ids |
| `search-demand.json`, when the study has one | `method` states whether search demand was collected |
| `history/versions/` | `ingest` matches each run against the version in force when it started; `detect` compares with the latest |
| `history/reports.json`, `history/unavailable.json`, `history/last-report.json` | the cut after the latest report's last run and the report order; the runs to request again; the last outcome |
| the period files of the latest K = 4 dates among the reports and the rebuilt periods, and the halves of the latest report | the earlier periods `period` compares with and takes the range from |
| the runs of the latest report's period, as `reports.json` and its period file list them, those it left out under the judged floor included, and every run started after its last run | the previous period's answers (verdict changes, episodes, presence sources) and the runs of the next period |

Before the first final report the pack holds every run, since the first report rebuilds the
earlier periods from them. `--full` holds every run and every period file, to move a study to
a CLI host or archive it. `inbox/`, `history/material/` and `reports/` are never packed: the
inbox and the material are built again, and each report is downloaded on its own. A pack
without `--full` serves the next report. Building the latest report's period again from it
gives the same file when that report was the first one compared on the two halves of its
period; any other latest report also reads the runs of the period before it, or rebuilds the
periods before a first report from their runs, which only `--full` holds. `period` and `check`
refuse such a report (exit 2) when a run they read, or a rebuilt period they would replace
lists, is missing from `history/runs/`, and say to unpack a pack written with `--full`. A pack
holding 30 runs is about 2.4 MB.

The manifest:

```json
{
  "schema": "sentl-monitor/pack@1",
  "skill_version": "0.1.0",
  "full": false,
  "last_report": "2026-11-30",
  "final_reports": 2,
  "projects": [{"key": "brand", "project_id": 501}],
  "files": [{"path": "history/reports.json", "size": 1234, "sha256": "<64 hex digits>"}]
}
```

`last_report` is the date of the latest final report, or null. `pack` refuses (exit 2) a state
`unpack` would refuse, a file over 50 MB or more than 200 MB in all, naming the largest files. The zip follows the rules of
`tools/build_zip.py`: entries sorted, dated 1980-01-01, 0644 for a file and 0755 for a folder,
so two packs of one folder are identical byte for byte; the manifest holds no creation time for
the same reason.

`monitor.py unpack --study S PACK` checks the whole pack and the target before it writes a
file. It refuses, with exit 2: an entry that is a link, an absolute path (a drive letter
included), or holds `..`, a backslash or an empty part; an entry held twice; a file the
manifest does not list, or a listed file the zip lacks; a path a pack never holds (anything but
the state files, the versions and runs of the manifest's projects, and the period files); a
file declared over 50 MB, or more than 200 MB declared in all; a file whose size in the zip,
size read or sha256 differs from the manifest, read in chunks; a target where a part of a path
is a link, a file stands where a folder goes, or a folder where a file goes; a target that holds
files and no `sentl.json`; a study folder whose `sentl.json` binds a project the pack does not
hold; a pack whose last final report is older than the folder's. A manifest schema other than
`sentl-monitor/pack@1` is exit 5: a later version of the skill wrote the pack. A folder the pack
writes into, or the nearest existing folder above one it creates, that cannot be written is
refused with exit 2 too, before any file moves. The files are then written to a hidden staging
folder inside the target, on the target's file system, each created new without following a
link, and moved into place one by one; a file they replace is first moved aside into the staging
folder. On any failure the files moved aside are put back, the new files and folders are removed
(the target too, when the unpack created it), and the staging folder is removed: the target is as
it was, and the command exits 6. Unpacking leaves the folder's other files as they are; it prints the last final report's date, the runs
held per project, and that the next report covers the runs started after the last run of that
report.

## Failure and degradation

| Situation | What the skill does |
|---|---|
| MCP server not connected, or 401 | stops and prints the connection steps for the operator's client |
| Role User in the organization | `brief`, `design`, `adopt`, `report` work; `setup` stops and names the role it needs |
| Insufficient credits or inactive subscription | `setup` shows the estimate and Sentl's message; no run starts |
| A run already open on the project | `setup` follows it and starts nothing |
| Run failed, or below 90% judged | left out of the period; listed to the operator |
| Run status not seen before | `runs` lists it apart from the runs not final yet and does not fetch it; `ingest` refuses its results (exit 5); listed to the operator |
| A Sentl response without a field the skill reads, or with another type or range | refused (exit 5) naming the tool and the field; nothing written; the operator is told, and the skill needs an update |
| A saved file that holds another tool's response, or a file missing or unreadable | refused (exit 2) naming the tool it looks like; the assistant saves the right response |
| Sentl answers "An internal server error occurred." | the tool is called once more; then run results are recorded as unavailable, and any other tool stops the route |
| Run listing whose oldest run started after the window's start | `runs` warns that the listing may be cut (no paging) or the project has no earlier run; the operator is told |
| Unexpected error in `monitor.py` | exit 6 with a one-line message; `--debug` prints the traceback |
| Run results returned as a server error | recorded in `history/unavailable.json`, listed to the operator, requested again at every invocation; blocks neither a report nor a write |
| A pack changed after it was written, holding a link or a path outside the study folder, over the size caps, older than the folder's last report, or of another study's projects; a target that is not an empty folder or a study folder | `unpack` refuses it (exit 2) and writes nothing; the operator is told why |
| A folder the unpack writes into that cannot be written | `unpack` refuses it (exit 2) before any file moves |
| A write or a move that fails while unpacking | the files moved aside are put back, the new files and folders and the staging folder are removed, and the study folder is left as it was (exit 6) |
| A state over the size caps | `pack` refuses it (exit 2), naming the largest files |
| A report built or checked again in a folder unpacked from a pack without `--full` | `period` or `check` refuses it (exit 2) when a run it reads is missing, and says to unpack a pack written with `--full` |
| A pack whose manifest schema the skill does not read | `unpack` refuses it (exit 5): a later version wrote it, and the skill needs an update |
| Run `completed_with_warnings` with enough judged answers | included; unscored answers excluded and counted in coverage |
| Unscored answer | `score` and `sentiment` set to `null` (Sentl returns `neutral` on it) |
| Response with no answer | not judged, counted against coverage, left out of presence |
| Saved project lacks a text of its latest run | `adopt` or `bind` refuses it; the assistant saves the response again |
| Run results too large for the assistant's tool output | read from the file the host saved; a truncated response is refused by `ingest` |
| Project edited in the Sentl web panel | `detect` records a `detected` version; runs started inside its window are matched against both versions; unmatched responses listed |
| Model no longer in `list-ai-models` | the report writes its name from the id (provider and model); `setup` refuses to save it |
| Google autocomplete blocked or rate-limited | missing prefixes listed, exit 1; the step is re-run; the brief does not pass its gate with themes lacking search data unless the operator waives it |
| Keyword-data source rate-limited | waits and retries as the server says |
| Keyword-data quota exhausted | stops; themes without volumes show none, and no total mixes themes with and without |
| No keyword-data source | autocomplete only; the no-volume statement in the brief and the report |
| `check` fails | interactive: the agent fixes the report; unattended: saved as draft |
| Facts older than 90 days | listed to the operator after the report; the report is unaffected |
| Snapshot run still open when the session ends | the next `snapshot` invocation in the folder follows the same run and starts nothing |
| Snapshot project left in the account | paused through the MCP; the operator archives or deletes it in the Sentl web panel (gap G16) |

## MCP gaps

What the design needs that the Sentl MCP does not offer today, as requests for the Sentl
team. P1 changes how reliable the history is; P2 removes work or a failure mode; P3 is
convenience.

| # | Request | Priority | Without it, the skill |
|---|---|---|---|
| G1 | `question_id`, `dimension_id` and the round number on each response in `get-run-results-tool` | P1 | matches responses by dimension name and question text; refuses duplicate texts; ingests every pending run before any edit |
| G2 | A configuration snapshot per run: researcher models, rounds, and the questions with their text, rubric and instructions as they were when the run started | P1 | reconstructs it from local versions; edits made outside the skill leave a window matched by text |
| G3 | Pagination, filters (dimension, question, model) or a compact mode without answer text in `get-run-results-tool` | P1 | depends on the host saving oversize tool output to a file; a host that truncates cannot ingest large runs |
| G4 | Metadata fields: on the project (purpose, research question, market, language, audience) and on dimensions and questions (theme, origins, framing, pair, persona), or one free JSON `metadata` field on each | P1 | keeps them in the study folder only; someone opening the project in Sentl sees none of the reasoning |
| G5 | The judge's justification for each score | P2 | the agent reads the answer against the rubric itself and never states the judge's reason |
| G6 | Archive a single question, as dimensions can be archived | P2 | asks the operator to approve a deletion, after ingesting every pending run |
| G7 | `sentiment` set to `null` when the judge did not score the answer | P2 | sets it to `null` itself |
| G8 | `list-runs-tool` filters (since a date, status, limit) and paging, or a total or a has-more field | P2 | reads the whole list at every report, a list that grows with every run, and warns when its oldest run started after the report's window starts, since a cut listing cannot be told from a project with no earlier run |
| G9 | A market or location setting for the researcher models | P2 | names the market in the question text |
| G10 | Per-dimension and per-question means on each run in `list-runs-tool` | P3 | computes them from the full results |
| G11 | The model's public name on each response | P3 | uses `list-ai-models`, which no longer lists retired models |
| G12 | A run-to-run comparison tool | P3 | compares locally |
| G13 | A notification when a run completes, or a way to list runs completed since a time | P3 | polls on the report's schedule |
| G14 | The run score's definition documented; the "general rule" that `get-project-tool` describes returned or removed from the description | P3 | computes the project figure as the mean of the dimension means, the definition observed (A4), and records Sentl's score beside it |
| G15 | The credits each run consumed, in `list-runs-tool` | P3 | tells the operator `estimate-run-tool`'s figure, never the spend |
| G16 | Archive a project and restore it, or delete it; archived projects left out of `list-projects-tool` unless asked for. Today a project has only `is_active`, set by `update-project-settings-tool` | P2 | pauses a snapshot project with `is_active: false` and gives the operator the link to archive or delete it in the Sentl web panel by hand |
| G17 | The results of every run readable: `get-run-results-tool` returns a server error on some older runs | P2 | records them as unavailable, requests them again at every invocation, and reports without them |
| G18 | Errors that say what failed: every error reads "An internal server error occurred." | P2 | calls the tool once more, then records the run as unavailable or stops, without knowing whether the cause is the request, the data or the server |
| G19 | The run statuses documented, with which are final | P3 | reads `completed` and `completed_with_warnings` as final and `pending`, `queued` and `running` as not final yet, and lists any other as never seen |

## Assumptions

| # | Assumption | Status |
|---|---|---|
| A1 | After a question is edited in Sentl, the results of an earlier run show the text asked at the time. If they showed the current text, earlier runs not yet ingested would be matched to the new wording. | Verified 2026-10-16 on read-only data. Sentl allocates question ids in sequence across an account. In a project whose questions were reworded after its earliest run, the reworded questions kept their ids inside the project's contiguous id range, so they were edited in place, not replaced. Read after the edit, that earliest run returns the earlier texts for those questions, and every later run returns the current ones. So an earlier run's responses carry the wording asked then: inside a detected version's window they match the earlier text, and in a run older than the first recorded version they are `unmatched` (§Matching). |
| A2 | Run statuses other than `completed` and `completed_with_warnings`, and which of them are final. | Only those two seen on 2026-10-16. The skill reads `pending`, `queued` and `running` as not final yet, none seen live; `runs` lists any other status as never seen and does not fetch the run, and `ingest` refuses its results (R2). |
| A3 | With more than one round, each round appears as a separate response with no round number. | Verified 2026-10-16: a run of a project with 3 rounds returned each question–model pair three times, with no round field. |
| A4 | Sentl's run score is the mean of the dimension means, each the mean of the dimension's judged answers, rounded to one decimal. | Verified 2026-10-16 on 7 runs. The mean of all judged answers, assumed while designing, differed on one of them (4.05 against a run score of 4.0). |
| A5 | Responses of a model later removed from `list-ai-models` keep its id. | Verified 2026-10-16: older runs carry a model id no longer listed. |
| A6 | `trigger-run-tool` starts a run on a paused project (`is_active: false`), so a snapshot project never needs a schedule. If it does not, `snapshot` activates the project only for the run, pauses it once the run is open, and M7 checks that pausing lets an open run complete. | To verify in M7. |
