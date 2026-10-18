# Devplan — sentl-monitor

**Status:** approved 2026-10-16, after a revision the same day that followed a read of three
live Sentl projects with read-only tools. M1, M2, M2b and M2c done; M3 next.

**Decisions of 2026-10-16:** MIT licence, public repository at
github.com/GuidanceStudio/sentl-monitor; the one-off check of sentl-snapshot becomes the
`snapshot` route (M7); from the second report on, a report opens with what changed and closes
with the method sections. After the live read: a project's figure is the mean of its
dimension means, as Sentl computes a run's score (A4); the first report on an adopted project
rebuilds the K periods before it from the project's history and compares with them (M2).
Revised later the same day: assumption A1 is settled at the start of M2 on read-only data, a
live project whose earliest run predates an in-place edit of three of its questions, instead
of a test run; no credit is spent.

## Objective

A skill that designs a monitoring study, sets it up in Sentl through Sentl's MCP server, and
reports on its runs every period, comparing each period with the previous ones. It also runs
a one-off snapshot of a subject on Sentl and leaves no project running afterwards. Sentl is
the only measurement; the skill makes no model calls and needs no key of its own.

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
  truncated data; the skill relies on hosts that save oversize output to a file. Claude Code
  does: a run of 39 answers, about 250,000 characters, was saved as complete JSON.
- Small MCP responses arrive inline and reach `inbox/` only through the assistant writing them
  out, which can alter a character: matching normalizes quotes and whitespace, `adopt` and
  `bind` cross-check the saved project against the latest run, and `payload` never sends a
  text that differs from Sentl's only by normalization (ARCHITECTURE.md §Responses saved by
  the assistant).
- Sentl returns a server error on the results of some older runs (gap G17): they are recorded
  as unavailable, retried, and never block a report or a write.
- One answer per question and model is noisy: periods pool runs, a change is called only
  outside the range of earlier periods, and unstable pairs are reported.
- Insights are written by the host assistant: `monitor.py check` verifies quotes, figures and
  section order before a report is final.
- No MCP tool archives or deletes a project (gap G16): the `snapshot` route pauses its
  project and the operator archives it in the Sentl web panel by hand.
- A manual run on a paused project is assumed to start (assumption A6); M7 verifies it before
  the `snapshot` route relies on it.
- The repository is public: fixtures and examples use fictional subjects, study and snapshot
  folders are ignored, and no file names a client, an organization or a machine path.

## Phases

### Phase A — Report on an existing project
- M1: Report on one run of an existing Sentl project — useful on its own, with no design route.
- M2: Compare each report period with the previous ones — the periodic part of monitoring.
- M2b: Explain each figure with its facts, sources and readings — what the client needs to know to correct an answer.

### Phase B — Design a study
- M3: Build the theme inventory and collect search demand — steps 1–2 of the operator's process.
- M4: Design dimensions, questions and rubrics from the themes — steps 3–5.

### Phase C — Run it in Sentl, on a schedule
- M5: Create and update the Sentl projects through the MCP — step 6, without retyping.
- M6: Report unattended on a schedule — reports arrive without the operator starting them.

### Phase D — One-off snapshot
- M7: Run a one-off snapshot on Sentl — the quick check sentl-snapshot runs on OpenRouter, measured on Sentl. Depends on M1, M4 and M5.

## Out of scope

- Model calls, OpenRouter, any key or token handled by the skill.
- Rendering: outputs are Markdown; PDF, slides and HTML are the operator's choice of tool.
- Scripts calling the Sentl endpoint directly.
- A batch mode that runs a snapshot for each subject of a list, and a PDF of the snapshot report. sentl-snapshot
  has both; the operator decides whether M7 carries them before sentl-snapshot is retired.
- Retiring sentl-snapshot once M7 ships: an item of that skill's own repository.

---

## M1: Report on one run of an existing Sentl project ✅

**Why:** The operator has Sentl projects and no written report on them; a report on one run is useful before any design route exists.

**Approach:** Router `sentl-monitor/SKILL.md`, playbooks `adopt/ADOPT.md` and `report/REPORT.md`, and the `monitor.py` commands `adopt`, `ingest`, `period`, `method` and `check`, as ARCHITECTURE.md §`adopt` and §`report` describe; here `period` covers the project's latest completed run, without comparison, so `method` lays out the first-report order of §The report. Fixtures follow the field names read from live Sentl on 2026-10-16 (`judge_score`, `reputation_score`, sources with `url` and `title` only), with fictional content. `check` applies the rules listed under §The report. Report headings in `en` and `it`. `install.sh` follows llm-rep's (`--force`, `--check`, `--dest`), and the test tiers (`tests/test_all.sh`, bash contracts, `tests/python/`, opt-in `tests/live/` with `RUN_LIVE=1`) land here, with the deny-list test the repository's CLAUDE.md requires.

**Tasks:**
- [x] Test: unit — deny-list: tracked files carry no name from a list kept as sha256 digests (llm-rep's pattern), no token-shaped string and no home-directory path
- [x] Test: unit — `adopt` maps a fictional `get-project-tool` fixture to `study.json` (with `report_every`) and `sentl.json`; refuses a saved project missing a question text of the latest run; matches across typographic quotes
- [x] Test: unit — `ingest`: text matching, `unmatched` rows, unscored answer with `neutral` sentiment set to null, `answer: null` counted against coverage and out of presence, a status not seen before treated as not final, a server error recorded in `unavailable.json`, truncated input refused
- [x] Test: unit — `period`: dimension mean, project mean as the mean of dimension means, coverage, presence, domains, owned split on a fictional run; Sentl's score recorded beside it
- [x] Test: unit — `method` writes the five method sections, the adopted-study `themes` line, and lays out the first-report order
- [x] Test: unit — `check` refuses a paraphrased quote, a quote split with `[…]` across two answers, an unknown figure with a decimal point or comma, an id after `run`, a key, a credit figure, a missing dimension, a section out of order; accepts integers that are counts or dates
- [x] Test: bash — layout, `SKILL.md` frontmatter and routes, `install.sh --dest` install and `--check` drift
- [x] Implement the two playbooks, the five `monitor.py` commands and `install.sh`
- [x] Test: live — adopt a real project, report its latest run with read-only tools; the study folder stays outside the repository and the project is named by an environment variable
- [x] Commit

**Done when:** the suite is green and a report on a real project's latest run passes `check` in the first-report order of ARCHITECTURE.md §The report.

**Deviations:**
- `monitor.py` dispatches to a `scripts/sentlmon/` package; run snapshots store their `plan` and no mention or owned flags, which `period` computes from the study as it stands.
- The live run showed one assistant's sources are grounding redirects (the domain comes from the title) and public model names carry version numbers (`period` records the names for `check`).
- `check` scopes each dimension's figures to that dimension, verifies "N of M" answer counts and the decimal separator, and refuses question keys only: dimension and project keys are ordinary words.
- A first report covers the latest run only, whatever `report_every` says; pooling arrives with M2.
- `install.sh` refuses a non-empty destination that is not a sentl-monitor install, since it replaces it with `rm -rf`.

## M2: Compare each report period with the previous ones ✅

**Why:** A periodic report must say what moved since the last one, and keep comparing when questions, criteria or models change.

**Approach:** Starts by settling assumption A1, because the handling of edits made in the Sentl web panel depends on it, on read-only data: a live project whose earliest run was read after three of its questions were reworded. Question ids are allocated in sequence across the account, so the reworded questions keeping their ids places the edit in place; the earlier run returning the earlier texts settles A1. `report` saves `get-project-tool` at every invocation and records a `detected` version in `history/versions/` on a difference. `monitor.py period` pools the runs since the previous report and compares them with the previous period by ARCHITECTURE.md §Comparability and §What counts as a change; on the first report of a project with earlier runs it rebuilds the K periods before it (§Periods). The `changes` section is written from its output; `history/reports.json` indexes the reports and sets the order: the first report in the first-report order, every later one with `changes` and `findings` first and the five method sections after them, complete.

**Tasks:**
- [x] Settle assumption A1 on a live project's run that predates an in-place edit of its questions, read with read-only tools; record the result and the evidence, with no account data, in ARCHITECTURE.md §Assumptions and, if it is false, the new-baseline rule in §Comparability
- [x] Test: unit — pooling four weekly runs into one period; deltas on models present in both periods, including a model absent from `list-ai-models` (A5) and rounds pooled as repeated responses (A3)
- [x] Test: unit — each §Comparability row: reworded, new intent, criteria, model added, dimension archived
- [x] Test: unit — range rule with 1, 2 and 4 previous periods; verdict bands with means on their edges (2.45, 2.5, 3.49, 3.5); new and lost domains
- [x] Test: unit — a detected edit creates a version; responses inside its window match the previous text
- [x] Test: unit — rebuilt periods: an adopted project with ten weeks of runs and a monthly cadence gets the K earlier periods with `rebuilt: true` and no report; runs before the adopt version have `version: null` and `expected` from their responses; an unavailable run is left out and listed
- [x] Test: unit — section order follows `reports.json`: the first report, rebuilt periods or not, in the first-report order with a `changes` section that compares when periods were rebuilt; later reports open with `changes` and `findings` and the method sections follow with the same content as in a first report; `check` refuses a later report in the first-report order, and the reverse
- [x] Implement versions, the comparison and the rebuilt periods in `period`, the `changes` section, the later-report order, `reports.json`; update `REPORT.md` and `ADOPT.md`
- [x] Commit

**Done when:** A1 is recorded as verified or refuted; three consecutive reports on a fictional history produce the expected `changes` section, including a reworded question, a criteria change and an added model, the first in the first-report order and the second and third opening with `changes` and closing with the method sections; a fictional adopted project's first report compares with its rebuilt periods.

**Deviations:**
- `period` refuses a study without `report_every`; versions gain `seen_at` and a `dimension_renamed` change; `monitor.py detect` (`--dry-run`, `--new-intent`) records detected versions.
- Inside a window a run takes the version matching its models, rounds and asked questions; on a criteria-only tie the changed questions are dropped from that run (`criteria_unknown`).
- Each period takes its questions and wording from its runs' latest version; the scoring section still shows the rubric from `study.json`, since a version holds only its hash.
- `check` keys findings by project and dimension, records a passing report as final in `reports.json`, and in `changes` accepts the previous period's quotes and comparison figures; the material prints figures as `check` rounds them.
- Open: an unavailable run is listed in every period's output, since its start time is not stored.

## M2b: Explain each figure with its facts, sources and readings ✅

**Why:** A dimension mean says how favourable the answers are, not why a figure moved or what the client should correct. The points a client acts on lie outside the means: an outdated fact quoted in most answers and the pages that carry it; an episode the period's mean averages away; a score drop caused by missing evidence rather than by negative answers; rounds of one run that cite the same sources; comparison pages written by competitors; the pages that brought the subject into an answer. `period` computes none of these, so a report written from its material cannot state them.

**Approach:** Each insight is a figure in the period file, so `check` verifies it like any other, and an entry in the period's material, so the findings are written from it. Depends on M2 (periods and comparison).
- **Fact currency.** A question's `facts` entry gains optional `current` and `outdated` term lists (ARCHITECTURE.md §`study.json`). `period` counts, per question, model and run, the answers stating a current term, an outdated one, or both, folded like aliases.
- **Sources behind a fact or a score.** Per question, for the answers stating only an outdated term, those stating a current one, those scored 1–2 and those scored 4–5: the five domains cited by most answers of the group, each with its share in that group and in the opposite one. Decided 2026-10-17 after the first live report, replacing a selection by difference between the two shares, which listed twenty or more domains per question and picked up sites cited by one assistant only.
- **Readings.** Rounds of a question–model pair in one run that cite the same list of sources are one reading. Each cell records `readings` beside `received`; the report states the readings a presence figure rests on when they are fewer than the answers.
- **Episodes.** A question's mean or a fact's current share that lies outside the range of the runs before it, in this period and the previous one and at least five of them, for at least three consecutive runs is an episode, with its first and last date; it closes at the first value back inside that range. A first period with no previous one is read against its own earlier runs, so a first monthly report still shows a movement inside the month.
- **Presence per run.** For each question whose answers do not name the subject in the text, the presence in each run of the period, so a finding can say in which readings the subject was named and in which it was not.
- **Missing evidence.** Answers in which the assistant says it found no source of the kind the question asks for are found by a phrase list per market language. `period` gives each question–model pair's mean with and without them, so a drop they account for is reported as missing evidence, not as a change in what is said.
- **Who wrote the sources.** `foils` gain optional `domains`. Each cited domain is owned, a foil's, or third party; per dimension, the share of answers citing a foil's pages and the foil pages cited most.
- **Presence changes.** For each question whose presence changed, the domains cited by the answers naming the subject in this period and by no answer in the previous one, and the reverse.
- **`report/INSIGHTS.md`.** One entry per insight: what it shows, the period figures it rests on, how a finding states it, its limit, with examples on the fictional oat-drink brand. `REPORT.md` points the findings and changes steps to it.
- **`adopt`** asks for the foils' domains and for the current and outdated terms of the facts that carry a figure or a name (prices, fees, people in charge).

**Tasks:**
- [x] Test: unit — fact currency: current, outdated and both, per model and per run, terms folded like aliases
- [x] Test: unit — sources behind an outdated fact and behind low scores: the five domains cited by most answers of each group, ties broken by name, each with its share in the opposite group
- [x] Test: unit — readings: three rounds with one source list are one reading, three different lists are three
- [x] Test: unit — episodes: three consecutive daily values outside the range of the earlier runs open one, two do not, fewer than five earlier runs open none; one that returns inside the range is closed with its dates; a first period is read against its own earlier runs
- [x] Test: unit — presence per run on an unbranded question: named in the last two of four weekly runs
- [x] Test: unit — missing evidence: phrase match in `en` and `it`; a pair's mean with and without the matched answers
- [x] Test: unit — domains split into owned, foil and third party; foil share per dimension
- [x] Test: unit — a presence change lists the domains new and lost in the answers naming the subject
- [x] Test: unit — `check` accepts each new figure taken from the period file and refuses one that is not in it
- [x] Implement in `period`, `adopt` and `check`; write `report/INSIGHTS.md`; update `REPORT.md`, `ADOPT.md` and ARCHITECTURE.md
- [x] Test: unit — `purpose` states each project's questions, assistants and how often they are asked when the projects of a study differ
- [x] Test: unit — `themes` lists together the dimensions that share an origin, the origin written once
- [x] Test: unit — `scoring` states a rubric shared by several questions once, for those questions, with all five anchors
- [x] Implement the three in `method`
- [x] Test: unit — a summary section: after the method sections in a first report, first in a later one; `check` refuses it with its marker left, with a figure that is not the period's, or with an excerpt
- [x] Implement the summary in `method` and `check`; a `REPORT.md` step to write it last, three to five plain sentences, each with its figure; ARCHITECTURE.md §Sections and §Order
- [x] Test: live — the first report on a real adopted project with several weeks of runs states the insights its history contains; the project is named by an environment variable
- [x] Commit

**Done when:** on a fictional history built to contain each pattern, the period's material lists every insight above with its figures, a report that states them passes `check`, and the live first report passes `check` with them.

**Deviations:**
- Sources behind a fact or a score: the five domains cited by most answers of each group, listed only when both groups of a pair cite a source (operator, 2026-10-17: the selection by difference listed twenty or more domains and picked up one assistant's homonym sites).
- An episode stays on one side of the range (a jump across ends it as a switch) and uses the assistants every run of its series has; missing-evidence phrases are anchored on the assistant's own search and exclude third-person subjects.
- The live report added, with the operator's approval: one `purpose` line per project when settings differ, shared origins and shared rubrics stated once, and an `In short` summary section.
- `check` keys findings by project and dimension, reads a fact term inside «» as text, and verifies a count before a verb of citing.
- Suite run under Python 3.14 and 3.11; 3.10 is not installed on the development machine.

## M2c: A first report on a monitor younger than its report interval compares the two halves of its period ✅

**Why:** A monitor started less than one `report_every` interval before its first report has no earlier interval to rebuild, so its `changes` section says this is the first measurement. The client was shown the first readings when the monitor started and reads the first periodic report for what moved since then. A live first monthly report, three and a half weeks of daily and weekly runs, said "first measurement" while its findings held a fact whose current value rose and fell, an assistant whose score on one question dropped a point, and unbranded questions that gained and lost the subject.

**Approach:** Applies only to a first report with no run before the period's interval, the case where `period` now tells the operator there is no earlier period. When the period's runs span at least 14 days, `period` splits them at the midpoint between the first run's start and the report's date and compares the second half with the first by ARCHITECTURE.md §What counts as a change, with the thresholds for a single previous period (0.5 points, 20 percentage points): dimension, project and question means, verdicts, presence per question, fact currency, new and lost domains. A half is a period built like a rebuilt one, `"half": "first"` or `"second"`, written to `history/periods/` and given no report; building the first report again replaces both. The `changes` section names the two halves and their dates, and when a change has an episode (M2b) it states the episode's first date. The episodes, fact currency and presence per run for the findings still read the whole period. Under 14 days the section stays the first measurement. Later reports compare with the whole first period, never with its halves.

**Tasks:**
- [x] Test: unit — a first report on a fictional monitor started 24 days before it: two halves split at the midpoint, compared with the single-previous-period thresholds, a dimension that moves by 0.5 and one that moves by 0.4, a question that gains the subject by 20 points and one by 10, a fact whose current share moves; under 14 days the first measurement; with an earlier interval the rebuilt periods, unchanged
- [x] Test: unit — the `changes` section names the halves and their dates, and states an episode's first date beside the change it explains; `check` refuses a halves report whose section names no halves, and accepts the figures of both halves
- [x] Test: unit — the second report compares with the whole first period; the halves are not read as earlier periods
- [x] Implement in `period`, `compare` and `check`; update `REPORT.md`, `ADOPT.md` §1 and §7 and ARCHITECTURE.md §Periods
- [x] Test, then implement: the halves split at the midpoint between the first run's start and the end of the report's date
- [x] Test, then implement: a verdict change is listed only when the pair's mean also moves by the change threshold (0.3 points, 0.5 with a single previous period), in every comparison; `change_rule` (en, it) and ARCHITECTURE.md §What counts as a change updated
- [x] Test, then implement: the new and lost domains, and the domains of a presence change, ranked by the answers citing them, five per list, ties broken by name; "1 answer" in the material
- [x] Test, then implement: the line naming the halves states each project's runs and answers in each half, and `check` still requires it; the material's halves header gives dates
- [x] The project mean and fact currency stay compared in every comparison (operator, after the first dry run)
- [x] Review fix, test first: an episode stands beside a change only on the side of its move and running in the later side of the comparison
- [x] Review fix, test first: the halves split the whole period's kept runs by time, so a criteria change drops its old answers from both halves
- [x] Review fix, test first: a project with runs in one half only is not compared and is stated; with no project in both halves the report is the first measurement
- [x] Review fix, test first: on a halves report the material says first and second half where a later report says previous and this period
- [x] Review fix, test first: every design change dated inside the period is stated on a halves report, inside the first half and across the split included
- [x] Review fix, test first: README says what the halves can date with weekly runs; ARCHITECTURE.md says the domain cap is five per list across all dimensions and projects
- [x] Review fix, test first: Italian date phrases elide before 8 and 11 and write the first of the month as 1°, through one helper
- [x] Review fix, test first: `check` refuses a report whose half file is missing; `period` deletes only the halves of the date it builds
- [x] Second review, test first: a dimension the earlier side never asked is new, with its design line; only one whose questions the earlier side dropped is a new baseline
- [x] Second review, test first: a dimension archived inside the first half is stated on a halves report
- [x] Second review, test first: on a halves report, assistants added or removed come from the recorded versions, and from half against half for runs older than every version
- [x] Second review, test first: the assistants a halves comparison rests on are said to be present in both halves
- [x] Second review, test first: the material's halves metric lines name the halves, "1 run" in the counts, episodes timed against the split instant, an episode note printed once under its question
- [x] Test: live — the live first report's `changes` section compares the two halves and passes `check`
- [x] Commit

**Done when:** a fictional monitor three and a half weeks old gets a first report whose `changes` section compares the second half with the first and passes `check`; the live first report does the same.

**Deviations:**
- Operator, after the first dry run: the split is the midpoint to the end of the report's date; a verdict change needs the pair's mean to move by the change step, in every comparison; the new and lost domains and a presence change's domains keep the five cited by most answers per list; the halves line states each project's runs and answers; the project mean and fact currency stay compared in every comparison (`comparison.projects`, a question's `current_share` on presence's thresholds).
- Reviews of the diff: the halves split the period's kept runs by time and compare per project (a project in one half only is stated and not compared; with none in both, the first measurement); they state every design change made inside the period, a dimension archived inside the first half included, assistants from the versions `detect` recorded and half against half for runs older than every version; an episode stands beside a change only on its side and when its last run starts after the split, once, under its question; a dimension whose questions the earlier side dropped for a criteria change is a new baseline, one it never asked is new.
- The halves are `<date>.first.json` and `<date>.second.json`, replaced only when that date is built; `check` refuses (exit 2) a report whose half file is missing; the comparison keeps `previous` null and gains `halves`; episodes gain `first_at` and `last_at`.
- The halves get their own changes marker, and `check` requires the line `method` wrote naming them; Italian dated sentences elide before 8 and 11 and write the first of the month as 1° through one helper (`i18n.phrase`); ADOPT.md §1 is the connection step, so its §6 cadence bullet was updated with §7.
- Existing tests updated for the new behaviour: `test_three_reports` asserts the halves line, `test_insights_period` fills the new marker, `test_rebuild` keeps its no-earlier-period case with two weeks of runs, `test_method` pins the title with 1°.
- Open: a dimension added inside the first half is compared between the halves and stated only by its questions' creation line, not as a dimension added.

## M3: Build the theme inventory and collect search demand

**Why:** The operator's process starts from themes found in the client's material and in Google searches, and the report's `themes` section needs each theme's origin and its search demand.

**Approach:** `brief/BRIEF.md` follows ARCHITECTURE.md §`brief`. `monitor.py demand` gains `autocomplete`, `volumes`, `import` and `summary` as §Search demand describes, ported from llm-rep's `scripts/search_demand.py` (Google suggest fetching and parsing, keyword classing; standard library): volumes come from a keyword-data MCP server whose tool names are read at run time, or from an export file; related searches are filtered for relevance; keywords are classed and never summed across classes. Without a volume source the brief carries the no-volume statement and `method` prints it in the `themes` section.

**Tasks:**
- [ ] Test: unit — autocomplete parsing, prefixes with stems, partial failure exit 1 (fixtures, no network)
- [ ] Test: unit — volume merge with provider, tool and date; related-search filter and dropped count
- [ ] Test: unit — keyword classes; per-class volumes; `summary` per theme; no-volume statement
- [ ] Test: live — one autocomplete request with `RUN_LIVE=1`
- [ ] Implement `BRIEF.md`, `demand` commands, the `themes` section from `search-demand.json`
- [ ] Commit

**Done when:** a fictional brief produces `search-demand.json` whose subject and component volumes stay apart, and `brief.md` with the no-volume line when no source is given.

## M4: Design dimensions, questions and rubrics from the themes

**Why:** Steps 3–5 of the operator's process: dimensions and projects from the themes, who asks, questions as people type them, and how each is scored 1–5.

**Approach:** `design/DESIGN.md` in the order of ARCHITECTURE.md §`design`; one study project is one Sentl project. `catalogue.md` ports sentl-snapshot's dimension catalogue (question patterns, rubric anchors, the facts each dimension needs, with catalogue ids) and adds the stance and fidelity axes; the `snapshot` route (M7) picks its dimensions from it. `monitor.py validate` implements every refusal and warning listed in §`design`, including Sentl's field limits and the opposite-framing rule for dimensions with `search_lean`. `review` writes `study-review.md`. Revisions classify each changed question as `reworded`, `new_intent` or `criteria` and append to its `lineage`.

**Tasks:**
- [ ] Test: unit — one fixture per `validate` refusal, one per warning, and a clean fictional study
- [ ] Test: unit — additional instructions composed from instructions and dated facts within 500 characters
- [ ] Test: unit — `review` prints narrative, inventory, questions, rubrics, credit estimate from tariffs
- [ ] Test: unit — revision lineage: reworded keeps the key, new intent retires it
- [ ] Implement `DESIGN.md`, `catalogue.md`, `validate`, `review`
- [ ] Commit

**Done when:** the fictional study validates, a dimension leaning one way without its opposite question is refused, and `study-review.md` shows every section.

## M5: Create and update the Sentl projects through the MCP

**Why:** The approved design must reach Sentl without retyping, and later edits must keep past results linked to their questions.

**Approach:** `setup/SETUP.md` follows ARCHITECTURE.md §`setup`. `monitor.py payload` builds the arguments of `create-project-tool`, `update-project-settings-tool` and `save-project-questions-tool` from `study.json`, with every id from `sentl.json`; `bind` records ids and a `setup` version from a saved `get-project-tool` response. The playbook ingests pending runs before any save, saves with `dry_run` first, sends `delete_missing` only after the operator approves the listed deletions, and triggers a run or activates the schedule only on an explicit go after `estimate-run-tool`.

**Tasks:**
- [ ] Test: unit — payload keeps ids, adds new items without ids, archives a dropped dimension, never sets `delete_missing`; a text that differs from Sentl's only by quotes or whitespace is sent as Sentl has it
- [ ] Test: unit — `bind` writes ids and a version; refuses a saved project missing a text of the latest run; the pending-run guard blocks a save, an unavailable run does not
- [ ] Test: live — in an organization the operator designates for tests: create, dry run, save, bind; no run triggered
- [ ] Implement `SETUP.md`, `payload`, `bind`
- [ ] Commit

**Done when:** the fictional study creates paused projects whose `get-project-tool` output matches `study.json`, and a reworded question keeps its id.

## M6: Report unattended on a schedule

**Why:** Monitoring means a report every period without the operator starting it.

**Approach:** `report` gains an unattended mode (ARCHITECTURE.md §`report`, §Scheduling, §Coverage): no questions asked; `nothing_new` when no completed run is new; runs under 90% judged left out; dimensions under 80% shown without a figure; a failed `check` saves `reports/<date>.draft.md`; `history/last-report.json` records the outcome. The README gains the two scheduling recipes: a local scheduler starting a headless assistant with the Sentl token method, and a cloud scheduled agent whose study folder is a private repository it commits to.

**Tasks:**
- [ ] Test: unit — `nothing_new`, `below_floor`, `draft` and `written` outcomes in `last-report.json`
- [ ] Test: unit — idempotence: two invocations on the same runs write one report
- [ ] Test: live — two scheduled invocations on a real project, one after a new run (a scheduled run of the project, or a manual one on the operator's go)
- [ ] Implement the unattended mode in `REPORT.md` and `monitor.py`; README scheduling section
- [ ] Commit

**Done when:** two scheduled invocations in a row on a real project produce one report and then a `nothing_new` outcome.

## M7: Run a one-off snapshot on Sentl

**Why:** A first look at a subject, for a prospect or before a study, needs a small study run once and a short report, with no project left running in Sentl. The route replaces the check sentl-snapshot runs on OpenRouter.

**Approach:** Depends on M1 (`ingest`, `period`, `method`, `check`), M4 (`catalogue.md`, `validate`, `review`) and M5 (`payload`, `bind`). `snapshot/SNAPSHOT.md` follows ARCHITECTURE.md §`snapshot <subject>`: subject and dated facts, 4–5 dimensions from `catalogue.md`, one question and one rubric each, one Sentl project created paused with no schedule, `estimate-run-tool` shown in credits before the go, one run, a report in the snapshot order of §The report, then the pause, `closed` in `sentl.json` and the panel link for archiving by hand (gap G16). `study.json` carries `"kind": "snapshot"`; `validate`, `review`, `payload`, `method` and `check` gain a snapshot mode. Invoked again in the same folder, the route resumes at the first step whose output is missing.

**Tasks:**
- [ ] Test: unit — snapshot `validate`: refuses 3 and 6 dimensions, a dimension with two questions, an unknown catalogue id, rounds above 1, a schedule; warns when every dimension names the subject
- [ ] Test: unit — snapshot `payload`: one project, one round, no `schedule_frequency`, `is_active` never sent as true
- [ ] Test: unit — snapshot report: `method` lays out the snapshot order with `limits` last; `check` refuses a `changes` section, a figure for the whole project, a credit figure
- [ ] Test: unit — resume: each folder state (no design, unbound, bound without a run, run open, run not ingested, project not closed) leads to the step ARCHITECTURE.md §`snapshot <subject>` names
- [ ] Test: unit — the archive step writes `closed` with `archive: operator` to `sentl.json`
- [ ] Test: bash — `SNAPSHOT.md` calls `estimate-run-tool` before `trigger-run-tool`, and `trigger-run-tool` only after the operator's go
- [ ] Test: live — a snapshot of a subject the operator picks, in the organization designated for tests: estimate, one run on the go, report, pause; verify assumption A6 and record the result in ARCHITECTURE.md
- [ ] Implement `SNAPSHOT.md` and the snapshot mode of `validate`, `review`, `payload`, `method` and `check`; list the route in `SKILL.md`
- [ ] Commit

**Done when:** `snapshot <subject>` in an empty folder ends with a report that passes `check` in the snapshot order, the Sentl project paused, and the operator holding the panel link to archive it.
