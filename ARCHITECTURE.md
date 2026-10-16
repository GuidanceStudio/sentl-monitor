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
| `adopt <project>` | a saved `get-project-tool` response | `study.json`, `sentl.json`, `history/versions/` | the operator's answers on purpose, audience and theme origins |
| `report` | `study.json`, `sentl.json`, saved `list-runs-tool`, `get-run-results-tool` and `get-project-tool` responses | `history/runs/`, `history/periods/`, `history/material/`, `reports/<date>.md`, `history/reports.json` | nothing when run unattended |
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
    periods/<YYYY-MM-DD>.json       metrics of one report period and its comparison
    material/<YYYY-MM-DD>.md        the figures and candidate answers the insights are written from
    reports.json                    index of reports: period, runs, status
    last-report.json                outcome of the latest `report` invocation
  reports/<YYYY-MM-DD>.md        the reports
```

A snapshot folder has the same layout without `brief.md`, `seeds.json`, `volumes.json` and
`search-demand.json`, and holds one run and one report.

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
  without the operator's choice.
- A run is ingested once and kept. Every route that writes to Sentl first ingests every
  completed run not yet in `history/runs/`, because an edit in Sentl can change how earlier
  results are linked to their questions (see Assumptions, A1).

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
  "volume_source": null
}
```

`class` is `subject` (the keyword contains an alias of the subject), `foil`, `component` (it
contains a component term and no subject alias) or `generic`. `volume_source` is the provider
and period, or `null` when no keyword-data source was used.

### `study.json`

```json
{
  "schema": "sentl-monitor/study@1",
  "kind": "study",
  "subject": {"id": "avenello", "label": "Avenello", "kind": "brand",
              "aliases": ["Avenello", "Avenello Oat"], "owned_domains": ["avenello.example"]},
  "foils": [{"id": "cow-milk", "label": "latte vaccino", "aliases": ["latte vaccino", "latte di mucca"]}],
  "components": [{"id": "oat-drink", "label": "bevanda all'avena",
                  "terms": ["latte d'avena", "latte di avena", "bevanda all'avena"]}],
  "market": {"country": "IT", "language": "it"},
  "report_language": "it",
  "organization": "<Sentl organization slug>",
  "narrative": {
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
           "facts": [{"fact": "...", "source": "https://avenello.example/...", "date": "2026-10-01"}],
           "lineage": [{"version": 1, "change": "created"}]}
        ]}
     ]}
  ]
}
```

- `kind` at the top is `study` or `snapshot`. A snapshot has one project, 4–5 dimensions
  with one question each, `rounds` 1 and no `schedule`; `themes` is empty, and each
  dimension carries `catalogue`, the id of the catalogue entry it was taken from.
- `kind` of a theme origin is `client_material`, `client_issue`, `client_analysis`, `search`
  or `probe` (a pilot run of questions).
- `search_lean` is `positive`, `negative` or `none`, set from the theme's searches.
- `framing` is `positive`, `negative` or `neutral`; two questions with the same `pair` ask the
  same thing with opposite leans.
- `axis` is `stance` (1 against the subject, 5 for it with grounds) or `fidelity` (1 wrong as
  fact, 5 accurate with the conditions the evidence sets). The report explains the score by it.
- Sentl's `additional_instructions` is composed from `instructions` and the dated `facts`.

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
  "source": "setup", "recorded_at": "2026-11-02T09:14:00Z",
  "window": null,
  "settings": {"models": ["..."], "rounds": 1, "schedule": "weekly", "active": true},
  "dimensions": [{"key": "health", "id": 0, "name": "Salute", "archived": false,
                  "questions": [{"key": "health-1", "id": 0, "text": "...",
                                 "criteria_hash": "<hash of rubric and judge instructions>"}]}],
  "changes": [{"question": "health-2", "change": "reworded"}]
}
```

`source` is `setup` (saved by the skill), `adopt`, or `detected` (found to differ from the
previous version). A detected version carries `window`: the last time the previous version
was seen and the time the difference was found. `change` is `created`, `reworded`,
`new_intent`, `criteria`, `retired`, `models`, `rounds`, `dimension_added` or
`dimension_archived`.

### Run snapshot, `history/runs/<project>/<run_id>.json.gz`

```json
{
  "schema": "sentl-monitor/run@1",
  "run_id": 0, "project": "brand", "status": "completed", "trigger": "scheduled",
  "started_at": "...", "finished_at": "...", "sentl_score": 3.4, "error": null,
  "version": 3, "ingested_at": "...",
  "expected": 48, "received": 48, "judged": 47,
  "responses": [
    {"response_id": 0, "question": "health-1", "dimension": "health", "model": "<model id>",
     "score": 4, "sentiment": "positive", "answer": "...",
     "sources": [{"url": "...", "title": "...", "domain": "example.org", "owned": false}],
     "mentions": {"subject": true, "position": 1, "foils": ["cow-milk"], "components": ["oat-drink"]},
     "match": "exact"}
  ]
}
```

- `expected` is questions × models × rounds of the version in force; `received` and `judged`
  are counted from the response.
- `score` and `sentiment` are `null` for an answer the judge did not score.
- `mentions` is computed by string match on the aliases and terms (case- and accent-folded,
  on word boundaries), never asked of a model. `position` is the subject's order among the
  subject and foils named in the answer.
- `match` is `exact`, `version` (matched against an earlier version's text inside a detection
  window) or `unmatched` (kept, excluded from every figure, listed to the operator).
- Runs are compressed because the history grows with every run: a project of 30 questions and
  4 models produces about 120 answers per run.

### Period metrics, `history/periods/<YYYY-MM-DD>.json`

```json
{
  "schema": "sentl-monitor/period@1",
  "date": "2026-11-30", "runs": {"brand": [0, 0, 0, 0]}, "versions": {"brand": [3]},
  "projects": {"brand": {"total": {}, "by_model": {},
     "dimensions": {"health": {"total": {}, "by_model": {},
        "questions": {"health-1": {"total": {}, "by_model": {}}}}}}},
  "comparison": {"previous": "2026-10-31", "range_of": ["2026-07-31", "2026-08-31", "2026-09-30", "2026-10-31"],
                 "dimensions": {}, "verdict_changes": [], "domains": {"new": [], "lost": []},
                 "design_changes": []}
}
```

Each `total`, and each model under `by_model`, is a cell: `mean`, `judged`, `expected`, `coverage`, `bands` (answers scored 1–2, 3, 4–5),
`presence` (answers naming the subject out of the answers given, and the mean position),
`unstable_pairs` (question–model pairs whose answers in the period differ by two points or
more) and `domains` (domain → answers citing it).

### `history/reports.json`

A list of `{date, file, status, period: {from, to}, runs, previous}`. `status` is `final` or
`draft`. `last-report.json` holds `{at, outcome, detail}`, where `outcome` is `written`,
`draft`, `nothing_new` or `below_floor`.

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

`monitor.py demand summary` prints, per theme, the distinct suggestions, the volume per
class or none, and the top queries. `design` copies it into each theme's `search` block.

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
   from `catalogue.md` (the dimension catalogue ported from sentl-snapshot). On a question that
   names no brand, 2 is *not mentioned* and 1 is *named negatively or advised against*. The
   axis is chosen before the anchors are written. Judge instructions carry the dated facts
   the judge needs to recognise an outdated or wrong statement.
7. **Narrative.** Research question (neutral: what is monitored, never one valence of it),
   purpose, audience, each project's question and decision, each design choice with its
   reason, score axis.
8. **Models, rounds, schedule.** From the saved `list-ai-models` response. Rounds × runs per
   report period should reach three answers per question and model, so a period's figure does
   not rest on a single answer.

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
2. Ingest every completed run not yet in `history/runs/` for projects that already exist.
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

`list-projects-tool` to find it, `get-project-tool` saved, `monitor.py adopt` writes
`study.json`, `sentl.json` and an `adopt` version. Every question gets a key; every
dimension a theme placeholder. The agent then asks the operator for what Sentl does not
hold: purpose, research question, who asks and why, the origin of each dimension's themes,
subject aliases, foils and owned domains. `list-runs-tool` shows which runs are available
for a first report.

### `report`

1. `list-runs-tool` for each project in `sentl.json`; runs are ordered by start time, never
   by their position in the listing. New runs: completed (`completed` or
   `completed_with_warnings`) and not in `history/runs/`. None: write `nothing_new` to
   `last-report.json` and stop.
2. `get-project-tool` for each project; a difference from the latest version is recorded as
   a `detected` version.
3. `get-run-results-tool` for each new run, saved to `inbox/`; `monitor.py ingest` writes the
   run snapshot. A saved response that does not parse as complete JSON is refused, since a
   host that truncates output cuts it mid-string. Fewer answers than expected count against
   coverage.
4. `monitor.py period` builds the period: the runs since the previous report, pooled. It
   computes the cells, the comparison with the previous period and the range of the K
   periods before (K = 4), and writes `history/periods/<date>.json` and
   `history/material/<date>.md`.
5. `monitor.py method` writes the method sections (`purpose`, `themes`, `dimensions`,
   `questions`, `scoring`) from `study.json`, the versions and the period, and lays out the
   sections in the order §The report sets for the period: the first-report order when the
   period has no previous period, the later-report order otherwise. `list-ai-models` gives
   the models' public names.
6. The agent reads the material and the answers and writes `findings` and `changes`.
7. `monitor.py check reports/<date>.md` (below). Pass: status `final`. Fail, when unattended:
   the file is saved as `reports/<date>.draft.md`, status `draft`, and `last-report.json`
   says which check failed.
8. In the chat, never in the report: the runs covered, runs left out, unmatched responses,
   versions detected, facts older than 90 days.

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
name, with no ids. `ingest` matches each response, after whitespace normalization, against
the version in force at the run's start; inside a detection window it also tries the
previous version. A response that matches nothing is kept as `unmatched`, excluded from
every figure and listed to the operator. This is why `validate` refuses duplicate texts in a
dimension and duplicate dimension names in a project.

### Periods

A report covers the completed runs started after the last run of the previous report. With a
weekly schedule and a monthly report, a period pools about four runs; with matching
cadences, a period is one run and the comparison is run against run. Pooling gives each
question–model pair several answers, which a single run with one round cannot.

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

### What counts as a change

- **Dimension or question figure.** A change is called when the period's value lies outside
  the range of the K previous periods (K = 4, or as many as exist) and differs from the
  previous period by at least 0.3 points (presence: by at least 10 percentage points). With a
  single previous period, the threshold is 0.5 points (presence: 20 points). Smaller moves
  are reported as unchanged.
- **Verdict.** Each question–model pair has a band from its mean in the period: unfavourable
  (up to 2.4), mixed (2.5 to 3.4), favourable (3.5 and above). A pair whose band changed is
  a verdict change, listed with the two answers that show it.
- **Sources.** Per dimension, a domain is new when at least two answers cite it in this
  period and none did in the previous one; lost in the opposite case. Domains are compared
  rather than URLs, because pages change address. Owned domains and their subdomains are
  marked.
- **Instability.** A pair whose answers in one period differ by two points or more is
  unstable. Its figure is reported with that note; it says where the assistants have no
  settled answer.

### Coverage

A run with fewer than 90% of its expected answers judged is left out of the period and
listed to the operator. A dimension whose judged answers in the period are under 80% of the
expected ones shows its answers without a figure, with one line saying how many were judged.
A missing figure is never a zero.

The overall figure is the mean of the judged answers. Sentl's run score is recorded beside
it in the run snapshot; when the two differ by more than 0.05, the operator is told.

## The report

`reports/<YYYY-MM-DD>.md`, in `report_language`, self-contained: a reader who never saw an
earlier report understands it. The method sections are regenerated from `study.json` each
time, so they describe the questions actually asked in the period. Sections are numbered in
the order they appear.

### Sections

| Key | Section | Written by |
|---|---|---|
| — | Title: the research question; subject, period, date | `method` |
| `purpose` | What we did and to what end: the purpose; the assistants by public name; the questions asked, in positive and negative where paired; the answers collected and scored in the period; that each answer's cited sources were recorded | `method` |
| `themes` | Where the themes came from: themes grouped by origin; search demand per theme with its source and period, volumes per class, or the no-volume statement | `method` |
| `dimensions` | The dimensions and how we reached them: projects with their question and decision, the dimensions of each with the themes they come from, who asks and why. In a snapshot: each dimension, what it measures and why it was chosen for the subject | `method` |
| `questions` | The questions: per dimension, verbatim, paired questions side by side | `method` |
| `scoring` | How the answers are scored: per dimension what a 5, a 3 and a 1 mean; who wrote the criteria and when; that an independent model in Sentl applied them; the score axis; what a high or a low score does not mean | `method` |
| `findings` | What the assistants say, dimension by dimension, in chapters by project | the agent |
| `changes` | What changed since the last report: changes in the answers, then changes in the design and how they affect the comparison | the agent, from the output of `period` |
| `limits` | Snapshot only: one question per dimension and one answer from each assistant, on one date; what a monitoring study adds (several questions per dimension, paired questions, repeated runs compared period by period) | `method` |

### Order

| Report | Sections after the title |
|---|---|
| First report on a study: the period has no previous period | `purpose`, `themes`, `dimensions`, `questions`, `scoring`, `findings`, `changes` |
| Every later report: the period's `comparison.previous` is set | `changes`, `findings`, `purpose`, `themes`, `dimensions`, `questions`, `scoring` |
| Snapshot | `purpose`, `dimensions`, `questions`, `scoring`, `findings`, `limits` |

The first report tells how the study was built before what it found, because the reader
meets the method there for the first time. From the second report on, the reader opens it
for what moved: `changes` and `findings` come first, and the five method sections close the
report, with the same content they would have in a first report, so each report still
stands on its own. `method` takes the order from the period file.

**`findings`, per dimension:** a title that states what the person asking is told, never a
score; one or two verbatim excerpts, each with its question and assistant; the domains those
answers cite; the dimension's figure with its coverage in the body; one line on what it means
for the client. Every dimension gets its section, including those where nothing moved.

**`changes`, on the first report:** one line saying this is the first measurement and the
next report compares against it.

**Never in a report:** credits or any price; run, project or question ids; question keys;
file names; model ids (the public name is used); the skill's own steps or checks.

**`monitor.py check`** fails the report when: a quoted excerpt is not a verbatim substring
of an answer in the period's runs; a figure is not in the period metrics; a dimension of the
study has no `findings` entry; an id, a key, a model id, a file name or a credit figure
appears; a section is missing, or the sections are not in the order the table above sets for
the report (first, later or snapshot); a snapshot report carries a figure for the whole
project.

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

## Failure and degradation

| Situation | What the skill does |
|---|---|
| MCP server not connected, or 401 | stops and prints the connection steps for the operator's client |
| Role User in the organization | `brief`, `design`, `adopt`, `report` work; `setup` stops and names the role it needs |
| Insufficient credits or inactive subscription | `setup` shows the estimate and Sentl's message; no run starts |
| A run already open on the project | `setup` follows it and starts nothing |
| Run failed, or below 90% judged | left out of the period; listed to the operator |
| Run `completed_with_warnings` with enough judged answers | included; unscored answers excluded and counted in coverage |
| Unscored answer | `score` and `sentiment` set to `null` (Sentl returns a sentiment on it) |
| Run results too large for the assistant's tool output | read from the file the host saved; a truncated response is refused by `ingest` |
| Project edited in the Sentl web panel | a `detected` version; responses matched by text; unmatched ones listed |
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
| G8 | `list-runs-tool` filters: since a date, status, limit | P2 | reads the whole list at every report, a list that grows with every run |
| G9 | A market or location setting for the researcher models | P2 | names the market in the question text |
| G10 | Per-dimension and per-question means on each run in `list-runs-tool` | P3 | computes them from the full results |
| G11 | The model's public name on each response | P3 | uses `list-ai-models`, which no longer lists retired models |
| G12 | A run-to-run comparison tool | P3 | compares locally |
| G13 | A notification when a run completes, or a way to list runs completed since a time | P3 | polls on the report's schedule |
| G14 | The run score's definition documented; the "general rule" that `get-project-tool` describes returned or removed from the description | P3 | recomputes the score from the answers and records Sentl's beside it |
| G15 | The credits each run consumed, in `list-runs-tool` | P3 | tells the operator `estimate-run-tool`'s figure, never the spend |
| G16 | Archive a project and restore it, or delete it; archived projects left out of `list-projects-tool` unless asked for. Today a project has only `is_active`, set by `update-project-settings-tool` | P2 | pauses a snapshot project with `is_active: false` and gives the operator the link to archive or delete it in the Sentl web panel by hand |

## Assumptions to verify

| # | Assumption | Verified in |
|---|---|---|
| A1 | After a question is edited in Sentl, the results of an earlier run show the text asked at the time. If they show the current text, earlier runs not yet ingested would be matched to the new wording. | M5 |
| A2 | Run statuses other than `completed` and `completed_with_warnings`, and which of them are final. | M1 |
| A3 | With more than one round, each round appears as a separate response with no round number. | M2 |
| A4 | Sentl's run score is the mean of the judged answers rounded to one decimal (true on the runs inspected while designing). | M1 |
| A5 | Responses of a model later removed from `list-ai-models` keep its id. | M2 |
| A6 | `trigger-run-tool` starts a run on a paused project (`is_active: false`), so a snapshot project never needs a schedule. If it does not, `snapshot` activates the project only for the run, pauses it once the run is open, and M7 checks that pausing lets an open run complete. | M7 |
