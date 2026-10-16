# Devplan — sentl-monitor

**Status:** proposed 2026-10-16, awaiting the operator's approval. No milestone has started.

## Objective

A skill that designs a monitoring study, sets it up in Sentl through Sentl's MCP server, and
reports on its runs every period, comparing each period with the previous ones. Sentl is the
only measurement; the skill makes no model calls and needs no key of its own.

## Approach

Route playbooks for the assistant, plus one standard-library script, `scripts/monitor.py`,
for search demand, validation, the arguments sent to Sentl, run ingestion, comparison, the
report's method sections and the report check. The assistant calls the MCP tools and saves
their responses to the study's `inbox/`; the script never calls Sentl, so the skill uses
whatever authentication the host already has and every write stays behind the host's
approval prompt. The first milestone reports on a project that already exists in Sentl, so
the operator gets a report before the design routes exist. Files, schemas and rules are in
`ARCHITECTURE.md`; milestones cite its sections instead of repeating them.

## Risks

- Run results identify questions by text only (gap G1): responses are matched by dimension
  name and text to local keys, duplicate texts are refused, and every pending run is
  ingested before any write to Sentl.
- Large run results can exceed a host's tool-output limit (gap G3): `ingest` refuses
  truncated data; the skill relies on hosts that save oversize output to a file.
- One answer per question and model is noisy: periods pool runs, a change is called only
  outside the range of earlier periods, and unstable pairs are reported.
- Insights are written by the host assistant: `monitor.py check` verifies quotes, figures and
  section order before a report is final.
- The repository will be public: fixtures and examples use fictional subjects, study folders
  are ignored, and no file names a client, an organization or a machine path.

## Phases

### Phase A — Report on an existing project
- M1: Report on one run of an existing Sentl project — useful on its own, with no design route.
- M2: Compare each report period with the previous ones — the periodic part of monitoring.

### Phase B — Design a study
- M3: Build the theme inventory and collect search demand — steps 1–2 of the operator's process.
- M4: Design dimensions, questions and rubrics from the themes — steps 3–5.

### Phase C — Run it in Sentl, on a schedule
- M5: Create and update the Sentl projects through the MCP — step 6, without retyping.
- M6: Report unattended on a schedule — reports arrive without the operator starting them.

## Out of scope

- Model calls, OpenRouter, any key or token handled by the skill.
- Rendering: outputs are Markdown; PDF, slides and HTML are the operator's choice of tool.
- Scripts calling the Sentl endpoint directly.
- Merging sentl-snapshot into this skill (operator decision pending).
- A licence file (operator decision pending).

---

## M1: Report on one run of an existing Sentl project

**Why:** The operator has Sentl projects and no written report on them; a report on one run is useful before any design route exists.

**Approach:** Router `sentl-monitor/SKILL.md`, playbooks `adopt/ADOPT.md` and `report/REPORT.md`, and the `monitor.py` commands `adopt`, `ingest`, `period`, `method` and `check`, as ARCHITECTURE.md §`adopt` and §`report` describe; here `period` covers one run, without comparison. Report headings in `en` and `it`. `install.sh` and the test tiers (`tests/test_all.sh`, bash contracts, `tests/python/`, opt-in `tests/live/`) land here.

**Tasks:**
- [ ] Test: unit — `adopt` maps a fictional `get-project-tool` fixture to `study.json` and `sentl.json`
- [ ] Test: unit — `ingest`: text matching, `unmatched` rows, null score and sentiment, truncated input refused
- [ ] Test: unit — `period`: mean, coverage, presence, domains, owned split on a fictional run
- [ ] Test: unit — `check` refuses a paraphrased quote, an unknown figure, an id, a credit figure, a missing dimension
- [ ] Test: bash — layout, `SKILL.md` frontmatter and routes, `install.sh --dest` install
- [ ] Implement the two playbooks, the five `monitor.py` commands and `install.sh`
- [ ] Test: live — adopt a real project, report its latest run with read-only tools, record assumptions A2 and A4
- [ ] Commit

**Done when:** the suite is green and a report on a real project's latest run passes `check` with sections 1–7 in the order of ARCHITECTURE.md §The report.

## M2: Compare each report period with the previous ones

**Why:** A periodic report must say what moved since the last one, and keep comparing when questions, criteria or models change.

**Approach:** `report` saves `get-project-tool` at every invocation and records a `detected` version in `history/versions/` on a difference. `monitor.py period` pools the runs since the previous report and compares them with the previous period by ARCHITECTURE.md §Comparability and §What counts as a change. Section 7 is written from its output; `history/reports.json` indexes the reports.

**Tasks:**
- [ ] Test: unit — pooling four weekly runs into one period; deltas on models present in both periods
- [ ] Test: unit — each §Comparability row: reworded, new intent, criteria, model added, dimension archived
- [ ] Test: unit — range rule with 1, 2 and 4 previous periods; verdict bands; new and lost domains
- [ ] Test: unit — a detected edit creates a version; responses inside its window match the previous text
- [ ] Implement versions, the comparison in `period`, section 7, `reports.json`; update `REPORT.md`
- [ ] Record assumptions A3 and A5
- [ ] Commit

**Done when:** three consecutive reports on a fictional history produce the expected section 7, including a reworded question, a criteria change and an added model.

## M3: Build the theme inventory and collect search demand

**Why:** The operator's process starts from themes found in the client's material and in Google searches, and the report's section 2 needs each theme's origin and its search demand.

**Approach:** `brief/BRIEF.md` follows ARCHITECTURE.md §`brief`. `monitor.py demand` gains `autocomplete`, `volumes`, `import` and `summary` as §Search demand describes: volumes come from a keyword-data MCP server whose tool names are read at run time, or from an export file; related searches are filtered for relevance; keywords are classed and never summed across classes. Without a volume source the brief carries the no-volume statement and `method` prints it in section 2.

**Tasks:**
- [ ] Test: unit — autocomplete parsing, prefixes with stems, partial failure exit 1 (fixtures, no network)
- [ ] Test: unit — volume merge with provider, tool and date; related-search filter and dropped count
- [ ] Test: unit — keyword classes; per-class volumes; `summary` per theme; no-volume statement
- [ ] Test: live — one autocomplete request with `RUN_LIVE=1`
- [ ] Implement `BRIEF.md`, `demand` commands, section 2 from `search-demand.json`
- [ ] Commit

**Done when:** a fictional brief produces `search-demand.json` whose subject and component volumes stay apart, and `brief.md` with the no-volume line when no source is given.

## M4: Design dimensions, questions and rubrics from the themes

**Why:** Steps 3–5 of the operator's process: dimensions and projects from the themes, who asks, questions as people type them, and how each is scored 1–5.

**Approach:** `design/DESIGN.md` in the order of ARCHITECTURE.md §`design`; one study project is one Sentl project. `design/anchors.md` adapts sentl-snapshot's dimension catalogue and adds the stance and fidelity axes. `monitor.py validate` implements every refusal and warning listed in §`design`, including Sentl's field limits and the opposite-framing rule for dimensions with `search_lean`. `review` writes `study-review.md`. Revisions classify each changed question as `reworded`, `new_intent` or `criteria` and append to its `lineage`.

**Tasks:**
- [ ] Test: unit — one fixture per `validate` refusal, one per warning, and a clean fictional study
- [ ] Test: unit — additional instructions composed from instructions and dated facts within 500 characters
- [ ] Test: unit — `review` prints narrative, inventory, questions, rubrics, credit estimate from tariffs
- [ ] Test: unit — revision lineage: reworded keeps the key, new intent retires it
- [ ] Implement `DESIGN.md`, `anchors.md`, `validate`, `review`
- [ ] Commit

**Done when:** the fictional study validates, a dimension leaning one way without its opposite question is refused, and `study-review.md` shows every section.

## M5: Create and update the Sentl projects through the MCP

**Why:** The approved design must reach Sentl without retyping, and later edits must keep past results linked to their questions.

**Approach:** `setup/SETUP.md` follows ARCHITECTURE.md §`setup`. `monitor.py payload` builds the arguments of `create-project-tool`, `update-project-settings-tool` and `save-project-questions-tool` from `study.json`, with every id from `sentl.json`; `bind` records ids and a `setup` version from a saved `get-project-tool` response. The playbook ingests pending runs before any save, saves with `dry_run` first, sends `delete_missing` only after the operator approves the listed deletions, and triggers a run or activates the schedule only on an explicit go after `estimate-run-tool`.

**Tasks:**
- [ ] Test: unit — payload keeps ids, adds new items without ids, archives a dropped dimension, never sets `delete_missing`
- [ ] Test: unit — `bind` writes ids and a version; the pending-run guard blocks a save
- [ ] Test: live — in an organization the operator designates for tests: create, dry run, save, bind; no run triggered
- [ ] Verify assumption A1 on that test project and record the result in ARCHITECTURE.md
- [ ] Implement `SETUP.md`, `payload`, `bind`
- [ ] Commit

**Done when:** the fictional study creates paused projects whose `get-project-tool` output matches `study.json`, and a reworded question keeps its id.

## M6: Report unattended on a schedule

**Why:** Monitoring means a report every period without the operator starting it.

**Approach:** `report` gains an unattended mode (ARCHITECTURE.md §`report`, §Scheduling, §Coverage): no questions asked; `nothing_new` when no completed run is new; runs under 90% judged left out; dimensions under 80% shown without a figure; a failed `check` saves `reports/<date>.draft.md`; `history/last-report.json` records the outcome. The README gains the two scheduling recipes: a local scheduler starting a headless assistant with the Sentl token method, and a cloud scheduled agent whose study folder is a private repository it commits to.

**Tasks:**
- [ ] Test: unit — `nothing_new`, `below_floor`, `draft` and `written` outcomes in `last-report.json`
- [ ] Test: unit — idempotence: two invocations on the same runs write one report
- [ ] Test: live — two scheduled invocations on a real project, one after a new run
- [ ] Implement the unattended mode in `REPORT.md` and `monitor.py`; README scheduling section
- [ ] Commit

**Done when:** two scheduled invocations in a row on a real project produce one report and then a `nothing_new` outcome.
