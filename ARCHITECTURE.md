# Architecture

sentl-monitor is a set of route playbooks that an assistant follows, plus one
standard-library script, `scripts/monitor.py`, for everything that must be deterministic:
search demand, validation, the arguments sent to Sentl, run ingestion, comparison, the
figures of the deck and its check. The assistant calls the Sentl MCP tools
and saves their responses into the study folder; the script reads those files and never
calls Sentl.

## Stages and the files they write

| Stage | Reads | Writes | Stops for |
|---|---|---|---|
| `brief <subject>` | the client's documents, Google autocomplete, a keyword-data source if present | `brief.md`, `seeds.json`, `volumes.json` (optional), `search-demand.json` | the operator's review of the themes and their origins |
| `design` | `brief.md`, `search-demand.json`, a saved `list-ai-models` response | `study.json`, `study-review.md` | the operator's review of the questions, rubrics and credit estimate |
| `setup` | `study.json`, `sentl.json` | Sentl projects; `sentl.json`, `history/versions/` | the operator's go before a run starts or a schedule is activated |
| `adopt <project>` | saved `get-project-tool` and `get-run-results-tool` responses (the latest completed run) | `study.json`, `sentl.json`, `history/versions/` | the operator's answers on purpose, audience, theme origins, market, the deck's language and the period, who wrote the criteria, and optionally the foils' domains and the current and outdated terms of facts that carry a figure or a name |
| `report` | `study.json`, `sentl.json`, saved `list-runs-tool`, `get-run-results-tool` and `get-project-tool` responses | `history/versions/` (a detected edit; an adopted project's `study.json` and `sentl.json` follow it), `history/runs/`, `history/unavailable.json`, `history/periods/`, `history/material/`, then, through `report/DECK.md`, `history/deck/`, `reports/<date>.deck.json`, `reports/<date>.deck.pdf`, `reports/share/` and `history/reports.json` | nothing when run unattended |
| `snapshot <subject>` | the operator's answers and facts, `catalogue.md`, saved `list-ai-models`, `estimate-run-tool`, `list-runs-tool` and `get-run-results-tool` responses | `study.json` (`kind: snapshot`), `study-review.md`, one Sentl project; `sentl.json`, `history/versions/`, `history/runs/`, `history/periods/`, `history/material/`, then the deck as in `report` | the operator's review of the questions and rubrics, then the go after the credit estimate |
| `compare` | two snapshot folders with their periods | `reports/<date>.compare.md` and `history/compare/<date>.json` in the later folder |

## The study folder

One folder per monitored subject, kept for the whole engagement. A change to the questions
is a new version inside the same folder, so the history stays in one place.

```
<study>/
  brief.md                       themes, origins, search demand, who asks, personas: the first gate
  seeds.json                     seed queries per theme and per persona, the personas, the sources to watch
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
    periods/<YYYY-MM-DD>.json       metrics of one period and its comparison
    periods/<YYYY-MM-DD>.first.json the halves of a first period with no earlier one (and .second.json)
    material/<YYYY-MM-DD>.md        the figures and every answer of the period, which the deck's writer reads
    deck/<YYYY-MM-DD>.figures.md    the figures of the deck and of the material, with the answers taken out
    deck/<YYYY-MM-DD>.notes.md      what the writer has found so far, for a session that starts again
    reports.json                    index of periods: dates, runs, status, the deck that recorded it
    last-report.json                outcome of the latest `report` invocation
  reports/<YYYY-MM-DD>.deck.json the deck's text; .deck.html and .deck.pdf, the deck drawn from it (§The deck)
  reports/share/                 the copy of each deck to send
```

A snapshot folder has the same layout without `brief.md` and `volumes.json`, and holds one run
and one deck. Its `seeds.json` holds one seed per dimension and its `search-demand.json` their
Google suggestions. On a host with no network, `seeds.json` is written before `demand
autocomplete` runs, and `autocomplete` writes `search-demand.json` with no suggestion in any
dimension's block before it exits 1. A snapshot made before personas and suggestions has
neither file.

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
| | a normalized copy of every run ingested, the period metrics, the decks |

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
  invocation; it blocks neither a period nor a write.

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
  "personas": {
    "genitore": {"seeds": ["latte d'avena bambini"],
                 "autocomplete": [{"prefix": "latte d'avena bambini", "suggestions": ["latte d'avena bambini 1 anno"],
                                   "source": "google autocomplete hl=it gl=it", "collected": "2026-10-16"}]}
  },
  "volume_source": {"providers": ["<server or file>"], "from": "2026-10-16", "to": "2026-10-16"}
}
```

`personas` is present only when `seeds.json` lists personas: one block per persona id, with its
seeds and their suggestions in the shape of a theme's. A persona whose seeds gave no suggestion
keeps its block with empty lists of suggestions; `brief.md` marks it as without search evidence.

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
  "themes": {"health": ["latte d'avena fa male", "avenello zuccheri"]},
  "personas": [
    {"id": "genitore", "label": "Un genitore che sceglie per i figli", "group": "chooses",
     "situation": "cerca una bevanda vegetale per un figlio intollerante al lattosio",
     "decision": "quale bevanda all'avena comprare",
     "asks": ["il latte d'avena va bene per i bambini?"],
     "seeds": ["latte d'avena bambini"]}
  ],
  "sources_to_watch": [{"label": "Un'associazione dei consumatori", "domains": ["consumatori.example"]}]
}
```

`personas` and `sources_to_watch` are optional. Every persona needs a unique `id` and a non-empty
`label`, `group`, `situation` and `decision`, one or more `asks` (the questions as the persona
types them) and `seeds` (the searches the persona types; an empty list when there is none).
`group` is `chooses`, `customer`, `buys_for_others`, `works_there`, or a group the operator
names. `sources_to_watch` lists the bodies the assistants cite and nobody asks as (regulators,
consumer associations, the press), each with a `label` and optional `domains`; their names are
never sent to Google. `demand` refuses a seeds file whose personas lack a field, repeat an id, or
share a label with a source to watch (exit 2).

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
  "personas": [
    {"id": "genitore", "label": "Un genitore che sceglie per i figli", "group": "chooses",
     "situation": "cerca una bevanda vegetale per un figlio intollerante al lattosio",
     "decision": "quale bevanda all'avena comprare", "asks": ["il latte d'avena va bene per i bambini?"]}
  ],
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
           "persona": "genitore",
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
  dimension carries `catalogue`, the id of the catalogue entry it was taken from, and
  `measures`, one sentence on what it measures for the subject. A snapshot needs no `audience`
  and no `report_every`; `design_rationale` holds one entry per dimension, whose `choice` is the
  dimension's name.
- `personas` is copied from the brief's `seeds.json` (`seeds` may stay behind). With an audience
  of `personas`, `stakeholders` or `mixed`, a question's `persona` is an id of that list; with
  `mixed` it may be left out. A study written before the list existed has no `personas` and a
  `persona` in plain words on each question, and validates as before.
- A snapshot's `narrative.reader` names who will read the deck and the decision it feeds;
  `review` prints it. A snapshot's `persona` is one line in plain words: who types the question and
  in what situation. `suggestion` is the Google suggestion a question starts from, as Google gave
  it; a snapshot designed with no network has none.
- `report_every` is `weekly` or `monthly`: how often a report is written. With each
  project's `schedule` it sets how many runs a period pools. A snapshot has none.
- `kind` of a theme origin is `client_material`, `client_issue`, `client_analysis`, `search`
  or `probe` (a pilot run of questions).
- `search_lean` is `positive`, `negative` or `none`, set from the theme's searches. A theme's
  `dimension` is the key of the dimension it feeds, or a list of keys. A dimension may carry
  `retired`: `[{"key", "text", "version"}]`, the questions withdrawn from it.
- `framing` is `positive`, `negative` or `neutral`; two questions with the same `pair` ask the
  same thing with opposite leans.
- `axis` is `stance` (1 against the subject, 5 for it with grounds) or `fidelity` (1 wrong as
  fact, 5 accurate with the conditions the evidence sets). The report explains the score by it.
- Sentl's `additional_instructions` is composed from `instructions` and the dated `facts`. Sentl refuses an empty one
  (`invalid_argument`, "field is required", seen live on 2026-11-07), so `validate` refuses a question with neither.
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

A snapshot also carries `closed`, written by the route's last step:
`{"closed_at": "<time>", "how": "kept" | "archived" | "deleted"}`. `kind` is the `kind` of the
saved `get-project-tool` response (`project` or `snapshot`) and is written only when Sentl returns
it; `promote` refuses a binding whose kind is `snapshot`, since a snapshot takes no schedule.

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
  the questions whose rubric the run cannot be placed under (§Matching). `criteria_settled`,
  present when it is not empty, holds each question placed after all, with its version and
  how it was placed: `rubric` or `updated_at`.
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
- A name counts in the answer's text as its reader reads it (`common.prose`): a Markdown link
  keeps its label and loses its address, a link whose label is itself a domain or an address
  goes whole, and so do bare addresses (`http://`, `https://`, `www.`) and the definitions of
  reference links. A domain written in a sentence ("see example.it for prices") stays a name.
  An answer whose only trace of the subject was `[example.it](https://example.it/page)` used to
  count as naming it. A period records the rule as `"names_counted_in": "prose"`; a period file
  without it was built before the rule and counted names anywhere in the answer. Such files are
  read as they are and never rebuilt: `deck` draws a period with the reader that counted it
  (`Reader.of`), so a deck drawn again from a period on file keeps its counts, and `period`
  tells the operator when it compares with a period counted the earlier way, since presence can
  differ by a few answers for that alone.
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
  "names_counted_in": "prose",
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
`period` reads both shapes when it compares with an earlier period, and writes the current one whenever it builds a
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
single run. The deck's method table states them per project.

`excluded` lists the runs left out under the run floor, `dropped` the questions a run lost
because their criteria changed later in the period or are unknown for it (§Comparability,
§Matching), and `starts` the runs' start times beside `runs` and `versions`. `asked` holds,
per project, the dimensions and questions of the period with the names and wordings its
runs had: those of the latest version among its runs (the first version for runs older than
every version), less any with no answer expected. The deck reads the period's
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
model of the period and of the periods compared with it to its public name, which the deck
prints and its `check` needs to tell a name from a figure. A question's or a dimension's `mean` is the mean of its
judged answers; a project's `mean` is the mean of its dimension means, the way Sentl
computes a run's score (A4). A period rebuilt from a project's history carries
`"rebuilt": true` and no comparison (see Periods).

### `history/reports.json`

A list of `{date, file, status, period: {from, to}, runs, previous, deck}`, in date order.
The deck's `check` writes the entry of its period when it passes, with the period's `runs`, as `final`, and `deck`, the
deck's text `reports/<date>.deck.json`; `check --unattended` on a deck that fails writes the period as `draft` when the
date has no entry yet, and the same deck passing later makes it `final`. The next period starts after the runs of the
latest entry, a draft included, and a draft counts as the previous period. An entry an earlier version wrote for its long
report carries `file`, `reports/<date>.md` or `.draft.md`, and is read like any other: its period bounds the next one and
it is the previous period. A deck checked beside such an entry keeps it and adds `deck`. A draft stays a draft when its
deck passes, and `last-report.json` keeps saying `draft`; the next deck reads the latest earlier entry with a `deck`, and
a pack holds that deck's text. An entry whose `file` names a deck, as earlier versions wrote it, loses that `file` at the
deck's next `check`. `previous` is the date of the period the entry's period compared with, a rebuilt one included; it is
null on a first period, including one that compares the two halves of its period. `last-report.json` holds `{at, outcome, detail}`, where `outcome` is
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
   material, a technology) with their terms, owned domains, market and language. Then the
   personas, each with its group, situation, decision, the questions it types and its search
   seeds, and the sources to watch: regulators, consumer associations, the press and other
   bodies the assistants cite and nobody asks as.
3. **Collect search demand** (next section). A theme that only search surfaced joins the
   inventory with origin `search`.
4. **Write `brief.md`**: the subject, the theme inventory (theme, origin, detail, search
   demand), the search-demand table with its source and date or the no-volume statement, a
   proposal for who asks with the reason, the persona table (`| id | label | group | situation |
   decision | asks | search evidence |`, a persona with no suggestion marked *without search
   evidence*), the sources to watch, and the documents read.
5. **Stop.** Say which themes came from documents, which from the operator, which from search.

### Search demand

**Always, without a key.** `monitor.py demand autocomplete --seeds seeds.json --hl <lang>
--gl <country>` sends each seed to Google's suggestion endpoint in the market's language and
country, as typed and followed by each question stem (Italian: *è, fa, come, perché, quanto,
quale, si può*; English: *is, does, how, why, can, which, vs*; `--stems` for any other
language). Every prefix is recorded with its source and date. Prefixes that could not be
fetched are listed and the command exits 1; running it again fills them. Each persona's seeds
are sent the same way and recorded under `personas` in `search-demand.json`; the sources to watch
are never sent.

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
carries the line, and `monitor.py demand summary` prints it: *the counts are Google suggestions:
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
`search` block. With `seeds.json` in the folder, `summary` then prints each persona by id and
label with its distinct suggestions and top suggestions, or `without search evidence`, and the
sources to watch on a line of their own.

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
   also differ in models, rounds and schedule. When the brief lists personas, projects are
   grouped by the personas they serve, with branded and unbranded questions still apart.
4. **Who asks.** `generic_consumer`, `personas`, `stakeholders` or `mixed`, with the reason.
   The brief's personas are copied into `study.json`; with personas, stakeholders or mixed,
   each question's `persona` is an id of that list.
5. **Questions.** Written as the person types them, in the market's language, starting from
   the top queries of the theme. A question that names no brand contains no alias of the
   subject or of a foil. Where a dimension's searches lean one way, the opposite question is
   added and the two are paired. The market is named in the question when it matters,
   because Sentl sets no location for the researcher models.
6. **Rubrics.** Five anchors per question, each an observable property of the answer, adapted
   from `catalogue.md` (the dimension catalogue). On a question that
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

`validate --models <saved list-ai-models>` prints `validate failed: N problem(s)` and one line
per problem, exit 1, or `validate passed` and one `warning:` line per warning, exit 0. Beyond
the list above it refuses a pair with other than two questions or whose framings are not one
positive and one negative, a missing `persona` when the audience is `personas` or
`stakeholders`, a `persona` absent from the study's `personas` list when the audience is
`personas`, `stakeholders` or `mixed` and the list exists, a `personas` value of another type
than a list, a persona that lacks a field or repeats an id, a blank `suggestion` or one that
`search-demand.json` records under no theme and no persona (compared after folding case and
accents), and a dimension with no question. A question's judge instructions are counted
as Sentl receives them: the instructions followed by the dated facts with their `current` and
`outdated` terms (`compose_instructions`). A snapshot `study.json` is checked by the snapshot
mode of `validate` and `review` (§`snapshot <subject>`); any other `kind` is refused with exit 2. Answers per question and model per report period is
`rounds` times the runs in a period: daily 7 (weekly report) or 30 (monthly), weekly 1 or 4,
monthly 0.25 or 1.

`monitor.py review` writes `study-review.md`: the narrative, the theme inventory with
origins and search demand, the personas (each with its group, situation, decision, the questions
it types, its search evidence and the study's questions asked as it), projects and dimensions
with question counts, every question with its persona, framing and rubric, and the credit
estimate from the models' tariffs. The
estimate for a project is its questions times `rounds` times the sum of its models' `credits`
(the tariff per call in `list-ai-models`), for one run and for a report period; judging costs no
credits, and `estimate-run-tool` gives the total before a run starts. `review` refuses a
study that fails `validate` and a model whose `credits` the response does not give (exit 2).

**Revising a study.** A question keeps its `key` when it is reworded with the same intent
(lineage `reworded`), and gets a new key when the intent changes (`new_intent`; the old key
is retired). A change to the rubric, the judge instructions or the facts is `criteria`.
The operator confirms each classification at the gate. Comparison across versions follows
these labels (see Comparability).

`monitor.py revise --previous <the earlier study.json> [--new-intent KEY] [--dry-run]` compares
the edited `study.json` with the earlier one and writes the lineage: the next version number is
one more than the highest in any lineage; a question whose text changed gets `reworded` and
keeps its key, or, if named in `--new-intent`, takes the next free `<dimension>-<n>` key with
`{"change": "new_intent", "replaces": <old key>}` while the old key and text go to the
dimension's `retired` list with the version; a changed rubric, instruction or fact is
`criteria`; a question absent from the edit is retired; a new one gets `created`. A retired key
is never given again, and `validate` refuses a key that appears twice among questions and
retired entries.

### `setup`

1. Preflight: `list-organizations` (connection and role), `get-organization-tool` (credits,
   subscription).
2. Ingest every completed run not yet in `history/runs/` for projects that already exist;
   runs Sentl cannot return go to `history/unavailable.json` and do not block the save.
   `payload` enforces it: given the saved `list-runs-tool` response, it refuses (exit 2) while
   a completed run is neither ingested nor unavailable, and names the runs. A run still open is
   named in its notes. It also refuses a saved project that differs from the latest recorded
   version, since a save would overwrite an edit made in the panel; `detect` records it first.
3. New project: `payload` prints the `create-project-tool` arguments (the project is created
   paused); after the call, `get-project-tool` is saved and `monitor.py bind` records the
   project, which holds no question yet. `update-project-settings-tool` is called when the
   saved project's name, models, rounds or schedule differ from `study.json`; `payload` prints
   it and never sets `is_active`.
4. Questions: `monitor.py payload` builds the `save-project-questions-tool` arguments, keeping
   every id from `sentl.json`; a new question or dimension has none. Every write tool call,
   a dry run included, has the operator's explicit go. The tool is called with `dry_run: true`
   first and the changes are shown to the operator; then for real. `payload` never sets
   `delete_missing`: the playbook adds it to the real call only when the operator approves the
   listed deletions, and `payload`'s notes name the questions that would be deleted. A
   dimension to drop is sent archived with its id.
5. Bind: `get-project-tool`, saved; `monitor.py bind` records the ids in `sentl.json` and a
   `setup` version in `history/versions/`, with the changes between the versions (`created`,
   `reworded`, `new_intent`, `criteria`, `retired`, the dimension changes, `models`,
   `rounds`). It refuses a saved project that does not hold `study.json`: a dimension or
   question missing, a text, rubric or judge instructions that are not the study's (the save
   did not apply). A project with no dimension and none bound is just created and is bound
   without that check.
6. `estimate-run-tool`: credits per model, available credits, whether the
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
owned domains, market and language, the deck's language (`report_language`), `report_every`, who wrote the criteria
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
   previous period and up to the end of the period's date; on the first period, those started
   in the last `report_every` interval and the K = 4 intervals before it. Runs in
   `history/unavailable.json` are requested again. Runs not final yet, runs ended with no
   results, runs the listing shows under the floor and statuses never seen are listed apart and
   not fetched (§Responses from Sentl). `runs` without `--saved` prints the tool's arguments for
   the window; a listing whose `total` exceeds the runs read is refused, and one saved without
   `total` is warned about when its oldest run started after the window's start. Unattended, the
   listings are saved as `inbox/runs-<project id>.json`, later pages as `.p2.json` and on, and
   `monitor.py pending` reads them: when no project has a run to fetch and none holds a run
   ingested but not yet in a period, it writes `nothing_new` to `last-report.json` and the route
   stops. A period dated the day of the invocation counts as the previous one, so a second
   invocation on the same day finds nothing new.
2. `get-project-tool` for each project, saved; `monitor.py detect` compares it with the latest
   version and records a `detected` version on a difference. With the operator present it
   runs with `--dry-run` first: a reworded question keeps its key unless the operator says it
   now asks something else, and is then recorded with `--new-intent <key>`.
3. `get-run-results-tool` for each new run, saved to `inbox/`; `monitor.py ingest` writes the
   run snapshot. A saved response that does not parse as complete JSON is refused, since a
   host that truncates output cuts it mid-string. Fewer answers than expected count against
   coverage. A run whose results come back as a server error goes to
   `history/unavailable.json`.
4. `monitor.py period` builds the period: the runs since the previous period, pooled; on the
   first period, the rebuilt periods as well, or the two halves of the period when there is
   no earlier one (see Periods). It computes the cells, the
   comparison with the previous period and the range of the K periods before (K = 4), and
   writes `history/periods/<date>.json` and `history/material/<date>.md`. It refuses a study
   without `report_every`.
5. The route goes on into the deck, `report/DECK.md`, with the same date (§The deck): `monitor.py deck`
   writes the figures file and the text to fill, the agent writes `reports/<date>.deck.json`, and
   `monitor.py check` on it records the period in `history/reports.json` with status `final` and
   `last-report.json` says `written`. Fail, when unattended (`check --unattended`): the period is
   recorded as `draft` when its date has no entry yet, and `last-report.json` says `draft` and what
   failed; a later `check` that passes makes it `final`. `period` records `below_floor` in
   `last-report.json` when it ends with exit 4. `monitor.py pdf --deck` prints the deck and its copy
   to send. No long report is written.
6. In the chat, never in the deck: the runs covered, runs left out, unmatched responses,
   versions detected, facts older than 90 days.

### `compare <folder> <folder>`

Two snapshots of one subject, taken at two moments with no study between them. `report` already compares a
promoted study with its snapshot, so this serves only snapshots that were not promoted. The earlier folder comes first; a
folder with no period, or that is no snapshot, is refused. Questions are matched by Sentl's id when both folders bind one
project and by text otherwise, and a question on one side only is refused by name, as is a dimension whose questions sit in
two dimensions of the other side. The figures are the periods', pooled on the assistants both sides asked; the limits name
them when the two differ. A change follows §What counts as a change with a single previous period. The report takes the
later date and the order purpose, changes, limits, and its rows are written by the script. `check` on a `.compare.md`
reads the order, the rows and the limits against `history/compare/<date>.json` and the leaks of §The deck. It calls no
tool and spends nothing.

### `snapshot <subject>`

A one-off check in its own folder: a small study, one snapshot in Sentl, one run, one deck,
and nothing left running in Sentl. Run end to end on Sentl on 2026-11-07 with skill 0.6.0 (M10). `study.json` carries `"kind": "snapshot"`. Invoked again
in the same folder, the route resumes at the first step whose output is missing: no
`study.json` → design; no binding in `sentl.json`, or a binding with no question → project; no
run → cost and go; a run open → follow it; a completed run not in `history/runs/`, or an ingested
run with no deck that passed `check` → deck; no `closed` in `sentl.json` → end.
`monitor.py resume [--runs <list-runs-tool, read now>]` reads the folder and prints
`Next step: design`, `project`, `cost`, `run`, `deck`, `end` or `done`, with the step of the
playbook; it needs `--runs` once the project holds questions, and refuses a listing of another
project.

The last step offers a choice (step 10). For a snapshot created as a project before Sentl had
snapshots, `monitor.py promote --answers <json> --models <list-ai-models>` turns it, finished and
not closed, into a monitored study: `kind` becomes `study`; the
schedule, `report_every`, the audience and the project's question and decision come from the
operator's answers; each dimension gets a theme whose origin is `probe` (the snapshot of that date);
questions, rubrics and rounds are untouched; `sentl.json` is untouched and `closed` is never written.
It validates the study as `design` does and writes nothing when that fails. It sends nothing to
Sentl: `setup` saves the schedule and activates on the operator's go. The snapshot's run and period
stay in `history/`, so the first `report` of the study compares its period with the snapshot's.

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
   `design_rationale`. The operator then names who will read the deck (`narrative.reader`)
   and the persona behind each question, one line each.
4. **Questions and rubrics.** One seed per dimension goes to `monitor.py demand autocomplete`,
   keyed by the dimension in `seeds.json`; `demand summary` gives each dimension's top
   suggestion. The question starts from it and from the persona's situation, and records it in
   `suggestion`. A host with no network skips the suggestions: the questions come from the
   catalogue entry's pattern alone, and the operator is told the suggestions could not be
   collected. One question per dimension, written as the person types it,
   from the catalogue entry's pattern, in the market's language. Five anchors per question,
   adapted from the entry; judge instructions carry the dated facts. Researcher models are
   the operator's choice from a saved `list-ai-models` response, with each model's tariff
   shown; one round; no schedule.
5. **Gate.** `monitor.py validate` in snapshot mode (below) and `monitor.py review`, which
   writes `study-review.md` with the questions, the rubrics and a credit estimate from the
   tariffs. Stops for the operator's approval.
6. **Snapshot.** `create-snapshot-tool` with the name `Snapshot · <subject> · <date>`, its
   models and one round; a snapshot takes none of the plan's project slots and has no schedule.
   `save-project-questions-tool` with `dry_run: true`, then for real, with the snapshot's id as
   `project_id`. `get-project-tool` saved; `monitor.py bind` records the ids and a `setup` version.
   `monitor.py payload` builds both calls in snapshot mode: `create-snapshot-tool` carries the
   name, models and rounds only, and the questions call is the one `setup` builds.
7. **Cost.** `estimate-run-tool`: credits per researcher model, the
   total, the credits available in the organization, and whether the run can start. Shown
   to the operator in Sentl credits. Stops for the go.
8. **Run.** On the go, `trigger-run-tool` once. `list-runs-tool` follows the run until its
   status is final. If the session ends first, the next invocation follows the same run and
   starts nothing.
9. **Period and deck.** `get-run-results-tool` saved to `inbox/`; `monitor.py ingest`, then `period`
   on the one run, with no comparison, then the deck of that period (`report/DECK.md`, §The deck).
   The deck's `check` records the period in `history/reports.json` as final; `pdf --deck` writes the
   copy to send.
10. **End.** The operator keeps the snapshot, deletes it, or follows the subject. Deleting is
    `delete-snapshot-tool` on the operator's go, then `monitor.py close --deleted`; keeping is
    `monitor.py close --saved <get-project-tool, read now>`, which refuses a project still active
    and records `archived` when Sentl says so. Both write `closed` to `sentl.json`; closing a
    closed snapshot changes nothing. Deleting loses nothing the deck needs, because the run is
    saved in the snapshot folder. Following the subject is `brief` and `design`, keeping the
    snapshot's deck and period as the first look: a snapshot takes no schedule. A snapshot created as a project before
    Sentl had snapshots is still promoted with `promote`, and archived with `archive-project-tool`.

**`validate` in snapshot mode** refuses: fewer than 4 or more than 5 dimensions; a
dimension with more or fewer than one question; a dimension without a catalogue id or with
an id absent from `catalogue.md`; a field over Sentl's limits; an alias in a question marked
as naming no brand; a model id absent from `list-ai-models`; rounds other than 1; a
schedule; a narrative without research question and purpose; a study with other than one
project; a dimension without `measures` or without an entry in `design_rationale`; a question
without a `persona`; a `suggestion` that `search-demand.json` does not record under the
question's dimension; a question with no `suggestion` when its dimension's block there holds
one; duplicate keys. It warns when every dimension names the subject. The study rules on themes, origins, pairs, search lean and answers per
period do not apply.

**Reading a snapshot.** Its one project mixes questions that name the subject with questions
that name no brand, so Sentl's run score mixes two readings. The deck places each question
in its block and reads each dimension on its own: by its score when the question names the subject, by whether and where the
subject appears when it names no brand. It gives no figure for the whole project. The run
floor of §Coverage does not apply to a snapshot's single run; a dimension under 80% judged is
shown without a figure, and the operator is told. `period` takes the project's one run with no
window, no floor and no comparison, and needs no `report_every`; it refuses a folder holding more
than one run.

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
every question whose criteria changed between the two versions, unless the run settles it. It
does when every answer to the question carries the rubric and instructions it was judged under
and they are one version's. It also does when the project read saved in the inbox
(`project-<Sentl id>.json`) says the question was last edited (`updated_at`) before the run
started and holds the later version's criteria: the run was then judged under the later version.
A question settled either way is recorded in `criteria_settled`; the others stay in
`criteria_unknown`, and `period` leaves them out of the run, so such a question's new baseline
starts from the first run known to be under the new criteria. `period` settles a run on file
again with the run's results and the project read the inbox holds then, without rewriting the
run's file, and names to the operator a question that no run of the period keeps. A run older than the first recorded version is matched
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
  no completed run the check is skipped and the operator is told. `bind` excepts a text that
  the latest recorded version holds and `study.json` rewords or drops on purpose;
- `payload` never sends a text that differs from the one in the latest saved
  `get-project-tool` response only by that normalization, so a transcription never rewords
  a question in Sentl.

### Responses from Sentl

`scripts/sentlmon/schema.py` states the fields, types and ranges the skill reads from each
tool's response. `adopt`, `detect`, `runs` and `ingest` check a saved response against it, and
`period` checks the saved `list-ai-models`, before anything is written. A field
that is missing, renamed, of another type or out of range is refused with exit 5, naming the
tool, the field, what was expected and what was found; the same change in many items is
listed once with their count. Fields the skill does not read, or only copies into the run
snapshot (`trigger`, `finished_at`, `error`, `sentiment`), are accepted with any value. A file
that holds another tool's response (its top-level key is that tool's), or that cannot be read,
is refused with exit 2: it is to be saved again.

| Tool | What the skill reads |
|---|---|
| `get-project-tool` | under `project`: `id`, `name`, `schedule_frequency` (text or null), `rounds` (1 or more), `is_active` (optional), `researcher_model_ids`; `dimensions` with `id`, `name`, `archived` (optional) and `questions`, each `id`, `question`, `label` (optional, text or null), `grading_rubric` (null, or an object whose keys are anchors from `1` to `5`, each a text or null: Sentl does not require every anchor), `additional_instructions` (optional, text or null), `updated_at` (optional, time or null) |
| `list-runs-tool` | `project_id`, `total` and `next_page` (optional); `runs`, each `id`, `status` (any text), `started_at` (null only on a run that is not completed), `expected` and `judged` (optional, a count or null) |
| `get-run-results-tool` | under `run`: `id`, `project_id`, `status` (a known status), `started_at`, `reputation_score` (1 to 5, or null); `responses`, each `id`, `model_id`, `dimension`, `question`, `answer` (text or null), `judge_score` (an integer from 1 to 5, or null), `sources` (a list, or null for none), each `url` and `title` (optional, text or null), `grading_rubric` and `additional_instructions` (optional, as on the project: what the answer was judged under). The results of a run not final yet are read for `id` and `status` only |
| `list-ai-models` | under `researcher_models`: each model id with its public `name`, and `credits` (the tariff per call; optional here, required by `review`) |

Times are ISO 8601; a time written without a time zone is read as UTC. The nine statuses are
`completed` and `completed_with_warnings`, final; `failed` and `stalled`, final with no results to
fetch; and `queued`, `pending`, `researching`, `running` and `judging`, not final yet (A2). `runs`
lists each group apart and a status outside them as never seen, and fetches none of them; `ingest`
exits 3 on an open run, 2 on a run ended with no results and 5 on a status never seen. A run the
listing shows under the 90% floor by `expected` and `judged` is left out before its results are
read and listed to the operator; a listing without those fields leaves it to the results. A
refusal carries `error.code` and a message, which the playbooks tell the operator as they came, and
a saved error is refused with exit 2. The read tools' codes are `internal`, called once more and
then recorded as unavailable (`get-run-results-tool`) or stopping the route (any other tool);
`not_found`, which stops and names the id; and `invalid_argument`, which stops because the skill
needs an update. The write tools also refuse with `project_limit_reached` and its `limit` and
`active`, and stop the route. Any other unexpected error in
`monitor.py` exits 6 with a one-line message; `--debug`, before or after the command, or
`SENTL_MONITOR_DEBUG=1`, prints the traceback. Ctrl-C exits 130 with one line. `runs` lists the
runs not final yet, ended with no results or of a status never seen among the runs of the report's
window and those with no start time, so a run left open long ago is not reported at every report.

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
and the material says this period is the first measurement. Building the first
period again replaces the rebuilt periods and that date's halves; the halves of another date
stay with its report.

A later report covers, for each project, the completed runs started after the last run of
the previous report and up to the end of the report's date. The periods it compares with are
those of the earlier reports in `history/reports.json` and the rebuilt ones, the latest K.
The second report compares with the whole first period, never with its halves.

### Comparability

| Change between the two periods | Score and presence deltas | Verdict changes | The material notes |
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

The figures that explain a mean, each computed by `period` and printed in the material, which
the deck's writer reads.

- **Fact currency.** An answer states a term when the term, folded like an alias, appears on
  word boundaries and not inside a longer number ("10 €" is not in "12,10 €", "£2" not in
  "£2.10"); a space between a number and a currency sign is optional on both sides. A phone
  number or another code, six digits or more with only spaces, dots, dashes, slashes or brackets
  between them, is matched on its digits: "800 123 456" is stated by "800123456" and
  "800-123-456", never by a longer number. Answers are counted as stating a current term only, an outdated term only,
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

## The deck

`report/DECK.md` turns one period into one slide deck, the only thing a client reads. The reader is the client's marketing manager: they know the market and the
competitors, and have never seen the questions, the ratings or the project names. So the slides run: cover, what this
report shows, what was found, what to do, the evidence block by block, the sources, the method, the list of questions.
The first four must be enough to decide. The second gives the two or three questions the report answers, in the reader's
words, each with real questions; the third answers them in the same order; every evidence slide carries the question it
belongs to.

**The second edition.** A deck that follows a final deck adds two slides after what was found. `_second` reads the earlier
deck's text and the two period files, no run: each block's figure on both dates over the questions the same assistants
answered in both, grouped by project unless `same_audience`, and a change by `compare.called` with the step of a rate with a
single previous period. The second slide prints each earlier action, its `read_next` and the writer's `earlier.now`. `check`
refuses a missing part, a `now` with no figure and a stated cause, since the deck does not know whether the client acted.

**Who writes what.** `deck.py` draws everything that is a figure: cards, charts, tables, sources, the method table,
every label (`DECK` in `i18n.py`), the list of questions. The writer fills only text, in `reports/<date>.deck.json`. A weaker model can then
write a weak sentence, but not a wrong chart or a broken page.

**Blocks.** A block comes from the type of a question, never from the name of a project, so every study shape fits:
a question naming no subject is `reach`, unless the subject is a category or a method; any other is `description`.
`facts` is a second reading of questions already placed: a `description` question with recorded facts always shows there,
and a `reach` question when an answer states the fact. The question also counts in its own block, because a topic reading
9 of 9 beside its own question reading 3 of 9 flatters the topic. `moved` in the deck's text sends to `description` a
question that names no subject and scores a position in a debate.

**Figures.** Reach: named in x answers of y, beside the answers naming each competitor and the subject's position among
the names monitored. A figure alone misleads: 72 of 120 reads as weak and can be second of ten. A competitor the question
itself names does not count on that question, because an assistant repeating a name it was given says nothing of who it
finds. Description: favourable answers (a score of 4 or 5), x of y, drawn with the neutral and unfavourable parts; the deck
draws no mean and never says "score", since a score means nothing to a reader who has not seen its criteria. Facts: answers
stating today's figure, x of y, one row per fact however many questions bring it out, with the fact's source and date, and the
pages cited by the answers with an old figure and hardly ever by those with today's, by who wrote them: a site usually feeds
both kinds of answer, so a site's count says nothing about where an old figure comes from. A
block's figure is one per project unless `same_audience` says otherwise: a count across audiences says nothing. Sources count
over all the block's answers, so one base serves the whole deck.

**The text.** `check` runs on `reports/<date>.deck.json`. It reads the structure (who asks, the question and one or two real
questions per block, one answer per block, one to five actions, each with a class, a block, an evidence slide and a reason
carrying a figure), the length of each text against what its slide holds (`LIMITS`), each excerpt against the answers of its
own question and assistant, the figures against the period and the figures the deck draws, and the leaks below.
A count in the period's figures may still be the wrong one, so a count beside a name is held to that name: a site or a page on
the period, a block, a slide's questions, a topic or one question, for one assistant when the sentence says so; a competitor on
its figures, rows and questions. Such a count needs no place in the period's figures, and the refusal prints the counts the name
has, so that any writer can correct it. A site's count beside a page is refused, and a count beside a site needs its base. A
grounding redirect hides the page, so a page's count is a range. A site said to be cited most comes first, alone, among the sites
the sentence speaks of. A bare name ties a count only through brackets or a page, because "citare" also means naming in the text.
What a count of a word in the answers says, and a count written in words, stay with the reader and the audit.
A count in a slide's text on as many answers as a row its chart draws must be one that chart draws: "all 14" beside a row
drawn at 8 of 14 was accepted because 14 of 14 was a figure elsewhere in the period. A facts row counts the answers stating
any fact of its question, so a question holding two facts is refused: the row could be drawn as carried on a claim no
answer states.
It keeps the reader in mind where a rule can: a figure over a chart must be on that chart; a title holds at most two figures;
the first slides repeat a figure at most twice; a presence figure comes with a competitor, and a subject among the first two
is not played down; words of the study, project names and a topic as the subject of a sentence are refused; "none" and "all"
pass only beside the count that says so. It keeps an action answerable: its reason is on its own slide and rests on more than one
answer, since one answer in a hundred can come from a document years old, it names a site cited by at least five answers, and one in twenty, on that slide's questions, it does not dictate what the study does not record, and one action at
least is on the subject's own pages, since those are the only ones the reader controls. The sources slide says how many answers citing a site name the subject on the questions without the name: the reason for acting
on a site or leaving it alone is that count, and a sentence on what the site publishes was a guess the audit kept finding false.
The deck prints beside an action on a third
party how many answers cite the site, and on the action's slide the page they cite most, because a reader asked to write to a
site needs to know why that site and about which page. The figures file lists the other pages cited most, so the writer can
name a page and not guess what a site covers. An action on a third party also carries `pages`, the record of the page once opened:
the providers it lists, or the wrong figure it shows. Many pages the assistants cite are a seller's own catalogue, where nobody else
gets listed, and only opening them tells: a rule asking the writer to open them was ignored, so `check` requires the record, refuses
a page listing fewer than two others, and the deck prints it. A correction needs a page read to show the wrong figure, on the
subject's own site too: answers with an old figure cite pages that hold no figure at all. The deck prints the actions in the
writer's order, which ranks them by the answers and the part of the reader's purpose each moves, and marks each, from the
domains its `what` names, as work on the subject's own pages or a request to a third party: sorting the own pages first had
put the largest gap of one study, 0 answers of 18, third. The labels the code draws say what their numbers count: the sources
slide is headed by how many answers cite each source; a note under its table says that an answer can cite more than one kind
of source when its columns overlap, since they then add up past the answers citing; a cell under a count of answers with
nothing to count prints 0, never a word. The cover's total names the answers to the questions without the subject's name
and to those about it, which the next slide counts apart. A name close to the subject's on the chart of names says how many
answers it has more or fewer. Beside an action, a site's count takes the base of the action's reason when that reason gives
the site a count on one row of its slide, and names the row; otherwise it counts the slide's questions. A third party's site
whose name is the subject's or an alias, and which `study.json` does not own, is labelled as another organisation of that
name. The method table says how many times each project's questions were asked in the period, beside how often they are
scheduled. A question with fewer than three answers counts in its topic and in the list of
questions, and draws no row and no excerpt: one answer of two is no finding. A deck with unfavourable answers shows one, and its
excerpts come from more than one assistant, because a deck quoting only the good answers hides what the reader has to fix. An amount
in a sentence is a recorded fact or stands in an excerpt of its slide, and a doubt comes from an answer not rated favourable, or the
rating printed beside it contradicts it. An
excerpt that starts or ends inside a sentence needs a `[…]`, because a part of a sentence can say what the sentence does not. Passing records the deck in `history/reports.json` as `deck` in the entry of its date, beside the `file` of a long report an earlier version wrote and never in its place; with no entry for the date, it writes one with the period and no `file`.

**Leaks, excerpts and numbers.** Question keys, model ids and file names are distinctive strings and are refused anywhere
in the deck's text. A Sentl id of the study is an integer that looks like a count, so it is refused only where a word names
it (`run`, `id`, `#`, and the words for project, question and dimension in the deck's language); dimension and project
keys are ordinary words and are not checked. A credit figure is a number next to the word for credit. An excerpt may skip
text with `[…]`; each piece, after the normalization of §Matching (dashes folded to a hyphen as well) and with Markdown
emphasis and citation markers such as `[1]` dropped, must be found in one answer, in order, and a failure says where the
excerpt stops matching its closest answer. A decimal uses the language's separator (a point in English, a comma in
Italian) and has one decimal; a percentage is whole. Text inside «» that quotes a question, a fact term of the study or an
answer, and the assistants' public names (which can carry a version number), are not read as figures.

**The reader's test.** `check` knows whether a sentence is allowed, never whether it is understood. The playbook ends with a
fresh reader who sees only the PDF's text and must say, from the first four slides, what was done, what the numbers count,
whether the main result is good and against whom, and what to do first and why. A deck that fails is rewritten, not handed over.

**Reading a page.** `monitor.py page` (`livepage.py`) parses a page's HTML and prints its text, with attributes such as tooltips, closed
answers, title and description. A web tool returns what a reader sees at first, and two actions asked for what the page held in a
tooltip and in a closed FAQ. It uses no browser on purpose: chromium needs its sandbox to open a third party's page, and a machine
without one would run the site's scripts unprotected, while the HTML already holds what was missed. Only http and https pass,
since the addresses come from what assistants cite. A page built entirely by scripts is refused and left to the web tool.

**The audit.** A reader finds what is not understood, never what is false: a title generalising past a row of its own chart reads
well and passes `check`, since no pattern tells a true sentence from a false one. So the playbook ends with a second fresh agent,
given the deck's text, the figures, the study and a search over the answers, who reports only what is false, overstated or left
out. It can run alone on a deck that passes, so a fault found late costs one sentence and not a new deck. The same writer that wrote a sentence audits it
less well than a stronger model does, so `history/deck/D.audit.md` lets the operator run the audit elsewhere and hand the writer the report.

**The pages.** 13.333 x 7.5 inches. A slide has a minimum height and no fixed one, so too much text runs onto a new
page, the page count differs from the slide count, and `pdf --deck` refuses it and names the slide. That came after `check`
had passed, so `check` also estimates each slide's height (`fit.py`): it parses the slide's HTML, applies the deck's style
sheet over the browser's own rules, and lays the boxes out as the browser does (blocks with collapsed margins, flex rows
and columns, grids, tables with fixed and automatic column widths, balanced columns), wrapping text in Arial's advance
widths, which Liberation Sans and Helvetica share. A box's padding and border count beside its width: a fixed table's
cell and a growing flex item take them before the room left is shared. A line breaks at a space and where Chrome breaks
between two characters (after a hyphen or a dash before a letter, on both sides of an em dash and of an inline block),
never inside a minus sign's number. Line heights are read as a theme may set them: a number, a length, a percentage, `em`,
`rem` or `normal`, which is Liberation Sans's ascent, descent and gap; a value the estimate cannot read (`var()`,
`calc()`) leaves the inherited one standing. On the test fixture's slides and on trial decks it lands within half a pixel
of Chrome printing in Liberation Sans. A slide over 720 px is refused with the texts the writer can shorten; the lists of questions are flowed by the code and left out. Inter, SF and Segoe UI come first in the font stack
and are wider, so a host that has them can still run over: `pdf --deck` does not run the estimate, and its page count is
the final word. The theme of
§Theme applies. wkhtmltopdf is not used: it does not read flex or grid. A browser prints with its sandbox or not at all. Where the system restricts unprivileged user namespaces (AppArmor on Ubuntu 23.10 and
later) and the only browser has no profile that allows them, its print fails with "No usable sandbox". The next engine is
tried, and when none prints, `pdf` exits 1, naming the cause and what to install. `doctor` prints which engine prints a
test page here.

**Later editions.** `reports/<date>.deck.json` keeps each action with its `read_next` figure, for the next deck to read
them; they are not printed. The slide of what changed is not written yet (DEVPLAN M18).

## Scheduling

Two clocks run independently. Sentl runs the measurement: the project's `schedule_frequency`
(`daily`, `weekly`, `monthly`) once `setup` activates it. The host runs `report`:

- **A local scheduler** (cron, launchd, a systemd timer) starts a headless assistant in the
  study folder with the `report` route. The Sentl MCP connection uses the token method,
  because OAuth needs a browser and a login unused for 30 days must be repeated.
- **An assistant's own scheduler** (a scheduled cloud agent) needs the study folder to
  persist between runs: keep it in a private repository the routine commits to.

`report` is idempotent: run twice on the same runs, it writes one deck and then
`nothing_new`. Unattended, it asks no question and treats every gate as described in the
`report` stage; the deck's `check` runs with `--unattended`, and the reader's test and the audit
are left to the operator. `pending` ends an invocation with no new run before anything else is
read from Sentl; `report/REPORT.md` ("Unattended mode") lists the Sentl tools it may call, all of
them read-only.

## Hosts without a lasting folder

On claude.ai and ChatGPT the scripts run in a sandbox whose files are deleted when the
conversation ends; `monitor.py doctor`, the first command of every conversation, reports it.
There the study travels between conversations as a pack: one zip the user downloads at the end
of a route and attaches to the next conversation, or keeps in the Project's files where the
host has Projects, replacing the previous pack. A conversation unpacks the pack with the latest
date before its next command and packs the study again once the deck's last `check` and `pdf`
have run (in `adopt`, once the operator's answers are written; in `snapshot`, after `close`);
`pdf`, once the deck prints in a sandbox, prints a reminder naming `monitor.py pack` and the deck's copy to send. The deck's copy to send, in
`reports/share/`, and the pack are copied to the folder the host offers for download. Claude Code, opencode and Codex keep the folder on disk and pack only to move or
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
| `search-demand.json`, when the study has one | `validate` checks each question's Google suggestion against it |
| `history/versions/` | `ingest` matches each run against the version in force when it started; `detect` compares with the latest |
| `history/reports.json`, `history/unavailable.json`, `history/last-report.json` | the cut after the latest report's last run and the report order; the runs to request again; the last outcome |
| the period files of the latest K = 4 dates among the reports and the rebuilt periods, and the halves of the latest report | the earlier periods `period` compares with and takes the range from |
| `reports/<date>.deck.json` of each entry whose deck passed `check`, a draft's included | the next deck's second edition |
| the runs of the latest report's period, as `reports.json` and its period file list them, those it left out under the judged floor included, and every run started after its last run | the previous period's answers (verdict changes, episodes, presence sources) and the runs of the next period |

Before the first final report the pack holds every run, since the first report rebuilds the
earlier periods from them. `--full` holds every run and every period file, to move a study to
a CLI host or archive it. `inbox/`, `history/material/` and `reports/` are never packed: the
inbox and the material are built again, and each report is downloaded on its own. A pack
without `--full` serves the next report. Building the latest report's period again from it
gives the same file when that report was the first one compared on the two halves of its
period; any other latest report also reads the runs of the period before it, or rebuilds the
periods before a first report from their runs, which only `--full` holds. `period` refuses to
build such a period again (exit 2) when a run it reads, or a rebuilt period it would replace
lists, is missing from `history/runs/`, and says to unpack a pack written with `--full`. The
deck's `check` reads the runs of its own period only, which the pack holds for the latest period. A pack
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

## Theme

`monitor.py pdf` renders the deck's page with `sentlmon/theme.py`. The page's rules read `--sl-*` variables only; a
theme sets the variables and the logo (an `<img>` with a data URI, on the cover and in each slide's foot), and never the structure.
Resolution, first hit wins: `--theme <file>`; the `theme` key of `study.json`; `theme.json` or `theme.css`
in the study folder; `theme.json` or `theme.css` in `$XDG_CONFIG_HOME/sentl-monitor` (default
`~/.config/sentl-monitor`); the built-in Sentl theme. A JSON theme is read over the built-in one, so what it
leaves out stays Sentl's; a CSS theme is appended after the page's own rules. Values that could leave the
stylesheet (`;`, braces, `<`) are refused. A logo that cannot be read falls back to Sentl's mark and the
command prints why. The page needs no network: the font is a stack and `font_url` is a link only when the
user sets it. `reports/share/` receives the themed PDF.

Where the built-in values come from (read 2026-10-29):

| Value | Source |
|---|---|
| Orange `#FF850D` (`--sl-primary`) | `--primary` in the `:root` of https://sentl.ai |
| Deep orange `#B85C00` (`--sl-deep`, text on white) | `--primary-deep` of https://sentl.ai |
| Text `#2C2C31` | the dark background of https://sentl.ai (`--app-bg`) |
| Mark | https://sentl.ai/brand/mark-sentl.webp, 61 x 70, lossless webp with alpha; `assets/sentl-mark.webp` is the file as fetched, `assets/sentl-mark.png` the same image as PNG so that every PDF engine reads it |
| Font | the site's system sans stack (`-apple-system`, Segoe UI, Roboto, Helvetica Neue, Arial) with Inter, the face https://app.sentl.ai/fonts/filament/filament/inter/index.css loads, used only where it is installed |
| Muted `#4B5563`, line `#E2E5EB`, tint `#FFF3E3` | chosen for a white page; Sentl publishes none for print |

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
| Run listing whose `total` exceeds the runs read | refused with exit 2, naming the page to read |
| Run listing saved without `total`, whose oldest run started after the window's start | `runs` warns that the listing may be cut or the project has no earlier run; the operator is told |
| A run ended `failed` or `stalled` | not fetched, left out of the period, listed to the operator with Sentl's error; unattended, `nothing_new` counts it |
| Unexpected error in `monitor.py` | exit 6 with a one-line message; `--debug` prints the traceback |
| Run results returned as a server error | recorded in `history/unavailable.json`, listed to the operator, requested again at every invocation; blocks neither a report nor a write |
| A pack changed after it was written, holding a link or a path outside the study folder, over the size caps, older than the folder's last report, or of another study's projects; a target that is not an empty folder or a study folder | `unpack` refuses it (exit 2) and writes nothing; the operator is told why |
| A folder the unpack writes into that cannot be written | `unpack` refuses it (exit 2) before any file moves |
| A write or a move that fails while unpacking | the files moved aside are put back, the new files and folders and the staging folder are removed, and the study folder is left as it was (exit 6) |
| A state over the size caps | `pack` refuses it (exit 2), naming the largest files |
| A period built again in a folder unpacked from a pack without `--full` | `period` refuses it (exit 2) when a run it reads is missing, and says to unpack a pack written with `--full` |
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
| No keyword-data source | autocomplete only; the no-volume statement in the brief and in `demand summary` |
| `check` fails | interactive: the agent fixes the deck; unattended: the period is recorded as a draft |
| Facts older than 90 days | listed to the operator after the report; the report is unaffected |
| Snapshot run still open when the session ends | the next `snapshot` invocation in the folder follows the same run and starts nothing |
| Snapshot left in the account | kept, or deleted with `delete-snapshot-tool` on the operator's go; it takes no project slot |
| Plan's project limit reached | `create-project-tool` answers `project_limit_reached`: nothing is created; the operator names a project to archive, or the study runs as a snapshot |
| A queued run ends `stalled` | not charged; `trigger-run-tool` once more on the operator's go. A second `trigger-run-tool` while a run is queued starts a second run |

## MCP gaps

What the design needs that the Sentl MCP does not offer today, as requests for the Sentl
team. P1 changes how reliable the history is; P2 removes work or a failure mode; P3 is
convenience.

| # | Request | Priority | Without it, the skill |
|---|---|---|---|
| G1 | `question_id`, `dimension_id` and the round number on each response in `get-run-results-tool` | P1 | closed 2026-11-07: `ingest` matches by `question_id`, then by text, then by `dimension_id` and text, and reads `round`; a null id says the question or dimension was deleted |
| G2 | A configuration snapshot per run: researcher models, rounds, and the questions with their text, rubric and instructions as they were when the run started | P1 | reconstructs it from local versions; edits made outside the skill leave a window matched by text |
| G3 | Pagination, filters (dimension, question, model) or a compact mode without answer text in `get-run-results-tool` | P1 | closed 2026-11-07: pages with `page`, `page_size`, `max_chars` and `content_sha256`, joined by `ingest --pages`, and the filter `question_id` |
| G4 | Metadata fields: on the project (purpose, research question, market, language, audience) and on dimensions and questions (theme, origins, framing, pair, persona), or one free JSON `metadata` field on each | P1 | keeps them in the study folder only; someone opening the project in Sentl sees none of the reasoning |
| G5 | The judge's justification for each score | P2 | Sentl returns `judge_report` on each judged answer since 2026-10-31 (seen live); the skill does not read it yet, so the agent reads the answer against the rubric itself and never states the judge's reason |
| G6 | Archive a single question, as dimensions can be archived | P2 | asks the operator to approve a deletion, after ingesting every pending run |
| G7 | `sentiment` set to `null` when the judge did not score the answer | P2 | closed 2026-11-07: documented; the skill still sets it to `null` itself, which changes nothing |
| G8 | `list-runs-tool` filters (since a date, status, limit) and paging, or a total or a has-more field | P2 | closed 2026-11-07: `runs` prints `started_after` for the report's window, reads `total` and `next_page`, refuses a listing with runs missing, and warns on a cut listing only when it was saved without `total` |
| G9 | A market or location setting for the researcher models | P2 | names the market in the question text |
| G10 | Per-dimension and per-question means on each run in `list-runs-tool` | P3 | computes them from the full results |
| G11 | The model's public name on each response | P3 | uses `list-ai-models`, which no longer lists retired models |
| G12 | A run-to-run comparison tool | P3 | compares locally |
| G13 | A notification when a run completes, or a way to list runs completed since a time | P3 | polls on the report's schedule |
| G14 | The run score's definition documented; the "general rule" that `get-project-tool` describes returned or removed from the description | P3 | closed 2026-11-07: documented as the mean of the dimension averages, one decimal, null when nothing was judged; the skill computes it and records Sentl's score beside it |
| G15 | The credits each run consumed, in `list-runs-tool` | P3 | tells the operator `estimate-run-tool`'s figure, never the spend |
| G16 | Archive a project and restore it, or delete it | P2 | closed 2026-10-29: `archive-project-tool`, `undo-project-archive-tool` (ten minutes), `restore-project-tool`, and `delete-snapshot-tool` for a snapshot; `list-projects-tool` returns `kind` and `archived`. The skill archives on the operator's go |
| G17 | The results of every run readable: `get-run-results-tool` returns a server error on some older runs | P2 | records them as unavailable, requests them again at every invocation, and reports without them |
| G18 | Errors that say what failed | P2 | closed 2026-11-07 for the read tools: `error.code` is `not_found`, `invalid_argument` or `internal`; a saved error is refused with exit 2, naming the code and the message. The write tools keep the rule of 2026-10-29 |
| G19 | The run statuses documented, with which are final | P3 | closed 2026-11-07: the nine statuses are read as Sentl documents them, and any other is listed as never seen |

## Assumptions

| # | Assumption | Status |
|---|---|---|
| A1 | After a question is edited in Sentl, the results of an earlier run show the text asked at the time. If they showed the current text, earlier runs not yet ingested would be matched to the new wording. | Verified 2026-10-16 on read-only data. Sentl allocates question ids in sequence across an account. In a project whose questions were reworded after its earliest run, the reworded questions kept their ids inside the project's contiguous id range, so they were edited in place, not replaced. Read after the edit, that earliest run returns the earlier texts for those questions, and every later run returns the current ones. So an earlier run's responses carry the wording asked then: inside a detected version's window they match the earlier text, and in a run older than the first recorded version they are `unmatched` (§Matching). |
| A2 | Run statuses other than `completed` and `completed_with_warnings`, and which of them are final. | Documented in the tool descriptions, read 2026-10-24: `queued`, `pending`, `researching`, `running`, `judging` open; `completed`, `completed_with_warnings`, `failed`, `stalled` final. `stalled` seen live on 2026-11-07, with `expected` set, `received` and `judged` 0 and Sentl's error. Seen live on 2026-11-07 (M10, skill 0.6.0): `trigger-run-tool` returns `queued`, then the listing shows `researching` with answers arriving, `judging` with all answers in, and `completed` with every answer judged, within a minute for a run of 12 answers. |
| A3 | With more than one round, each round appears as a separate response with no round number. | Replaced 2026-11-07: each answer carries `round`, from 1, seen live; `ingest` counts rounds by answers only on a response without it. |
| A4 | Sentl's run score is the mean of the dimension means, each the mean of the dimension's judged answers, rounded to one decimal. | Verified 2026-10-16 on 7 runs and documented in the tool descriptions on 2026-10-24. The mean of all judged answers, assumed while designing, differed on one of them (4.05 against a run score of 4.0). |
| A5 | Responses of a model later removed from `list-ai-models` keep its id. | Verified 2026-10-16: older runs carry a model id no longer listed. |
| A6 | `trigger-run-tool` starts a run on a paused project (`is_active: false`), so a snapshot project never needs a schedule. If it does not, `snapshot` activates the project only for the run, on a new go of the operator, and pauses it once the run is open; whether pausing lets an open run complete is not known either. | Verified on 2026-11-07 (M10, skill 0.6.0): a run started on a snapshot that was never active, and completed; the skill set no schedule. Sentl's response gives `schedule_frequency: daily` for a snapshot created through the MCP, which has no schedule. `tests/live/test_snapshot_live.py` checks, on the folder a live snapshot leaves, that a run was ingested for a project that was never active. |
