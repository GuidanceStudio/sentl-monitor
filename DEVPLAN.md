# Devplan — sentl-monitor

**Status:** approved 2026-10-16, after a revision the same day that followed a read of three
live Sentl projects with read-only tools. M1, M2, M2b, M2c, M2d, M2e and M2f done; R0–R4 (release to every Sentl user) approved 2026-10-19, R0, R2 and R4 done; R3a next, then R3b and R1; R3d waits for Sentl; M3 after the release.

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

## M2d: Export each report's figures as chart tables for a deck ✅

**Why:** a report is often presented as a deck, and the figures a deck shows as charts (a dimension profile in two periods, a fact's current share run by run, the subject's presence run by run, the sources behind a fact, the score by assistant) are in the period files, partly not in the report. Copying them by hand each month is slow and lets a figure drift from the checked one.

**Approach:** `monitor.py charts --study S --date D` reads the period file of `D` (and its comparison, or its halves) and writes `reports/D.charts.md`: one `:::chart` block per chart in md2's syntax (a Markdown table under a `:::chart <type>` line), each with a heading saying what it shows and the period or halves it covers, figures rounded as `check` rounds them. Charts:
- **Profile:** per project, a `radar` of the dimension means, one series per period compared (the previous period and this one, or the two halves; one series on a first measurement), and a `bar` with the same values.
- **Fact currency by run:** per question with `current` terms, a `line` of the share of the answers stating a current term, one point per run.
- **Presence by run:** per question whose answers do not name the subject in the text, a `column` of the share of answers naming it, one column per run.
- **Sources behind a fact or a score:** per pair of groups the material lists, a `bar` with two series, the share of each group citing each of the five domains.
- **By assistant:** per project with more than one assistant, a `bar` of each dimension's mean by assistant.
A chart with no data is left out and listed on stdout. The file is for the operator's deck; the report does not include it. `REPORT.md` gains a last optional step pointing to it; README and ARCHITECTURE.md describe it.

**Tasks:**
- [x] Test: unit — on a fictional study with two periods: the radar and bar of each project carry both periods' dimension means; on a halves report the two halves; on a first measurement one series
- [x] Test: unit — the line of a fact's current share has one point per run with the period file's values; the presence columns one per run; the sources bars the five domains with both groups' shares; the assistant bars one series per assistant
- [x] Test: unit — every value in the file equals the period file's figure as `check` rounds it; a chart with no data is omitted and listed; the output parses as md2 `:::chart` blocks (type line, table, closing `:::`)
- [x] Implement `monitor.py charts`; `REPORT.md` optional last step; README; ARCHITECTURE.md
- [x] Test: live — the live study's chart file for its latest report holds the profile radars of both projects and the fact-currency line
- [x] Review fix: a fact line with a 0% run is drawn on a raised axis by md2 (zeros pushed to the floor); fix md2's line axis to include 0, or emit a column (fixed in md2 M121; `line` kept)
- [x] Review fix: a by-run chart with one run is empty in md2 (N−1 segments); omit and list it, or draw a column
- [x] Review fix: two runs on the same day get the same label; add the time when a day repeats
- [x] Review fix: the profile series are comparison means on shared assistants and questions; the heading names them when they differ from the period's figures; unit test for that case
- [x] Review fix: the live test expects a radar per project with 3–12 dimensions asked, the code draws one for 3–12 with a value; align; its md2 check counts chart divs only
- [x] Review fix: headings use the project's own run span, not the whole period's; collapse whitespace in titles
- [x] Re-review fix, test first: series labels use the bounds the report prints (halves, previous period, period), a project's own run days only in its heading; the live test expects a line where the fact is stated in two runs or more; a line left out says in how many runs the fact is stated; singular notes for one assistant or one question; same-day times in UTC
- [x] Commit

**Done when:** `monitor.py charts` on the live study writes a chart file whose figures match its period file, and md2 renders every block in it.

**Deviations:**
- The profile's two series are each compared dimension's comparison `mean` (`previous`, `now`), on the questions and assistants both sides share, so they match the changes section; a dimension not compared is left out and listed; when that basis differs from either side's own (an assistant added or removed, a question not comparable), the heading names the assistants and the questions left out.
- Sources: one bar per pair of groups, rows the union of the two groups' five domains (up to ten), each with both groups' shares.
- md2 reads an empty cell as 0, so rows without a value (a run with no answer stating the fact, a dimension without a figure) are left out and listed, like a chart with no data; a chart by run needs two runs with a value (stdout says in how many the fact is stated) and the radar 3 to 12 dimensions, otherwise it is left out and listed (the bar keeps the dimensions).
- Series carry the bounds the report prints (the period, the previous period, the two halves); a project whose runs start or end on other days has its own first and last run days after its name in the headings; run labels are the start day in UTC, with the UTC start time where two runs share a day; the basis notes are singular for one assistant or one question.
- Headings, titles and series labels are in the report's language (`i18n.CHARTS`); the command's own output is in English, for the operator.

## M2e: The comparison keys each dimension by its project ✅

**Why:** found while executing M2d: `compare.py` keys the comparison's dimensions by dimension key alone, so when two projects of a study share a key, one overwrites the other and the first project's dimension is reported as not compared, in the changes section and in the charts.

**Approach:** key the comparison's dimensions, verdicts and presence changes by project and dimension key, as `check` already keys findings; read them so in `period`'s material, `check` and `charts`.

**Tasks:**
- [x] Test: unit — two projects sharing a dimension key are both compared, in the material, `check` and the charts
- [x] Implement in `compare.py`, `period.py`, `check.py`, `charts.py`; ARCHITECTURE.md
- [x] Commit

**Done when:** a fictional study whose two projects share a dimension key gets both dimensions compared.

**Deviations:**
- `adopt` and `detect` already keep dimension keys unique across a study; two projects share one only when a dimension archived at adoption is restored after another project took its key, and the test builds that path. Its question keys are shared too, so the material reads question texts by project as well.
- The comparison's `dimensions` are `{project: {dimension key: entry}}`, schema `period@2`; `check` and `charts` read a `period@1` file (keyed by dimension alone, each entry naming its project) through `compare.dimension_entries`, so earlier period files are read, not rebuilt.
- The material names a dimension with its project only when another project shares its key or name, so a study whose projects share no dimension key or name gets the same material; design changes take dimension names from their own project, without it.
- Open: in the collision case themes stay keyed by dimension key across the study (`method`, `adopt`, `detect`), so the restored dimension shows the other project's theme; a collision implies names with the same slug, so the impact is small.
- Tests reading the comparison's raw shape now read it per project (9 files), and `test_period` expects `period@2`.

## M2f: An episode's close is one run, not the state after it ✅

**Why:** a report could describe an episode's close as the end of the movement while later runs of the period lay on the episode's side again. The close is the first run back inside the range; the runs after it are not described by it. Approved by the operator on 2026-10-18.

**Approach:** `INSIGHTS.md`'s example states the close as one date ("on 12 October it was back inside that range") and the rule says the runs after the close are read from the by-run figures, and that "only" is not written about an episode when a later run of the period lies on the same side. `period`'s material prints, under each closed episode, the later runs of the period that lie on the episode's side, with their values, so the finding can state them. `check` refuses "only" (and "solo" in Italian) in a sentence that names a closed episode's dates when the material lists such a later run.

**Tasks:**
- [x] Test: unit — the material lists, under a closed episode, the later runs on its side with their values; none when there is none
- [x] Test: unit — `check` refuses "only"/"solo" beside a closed episode's dates when a later run lies on its side, and accepts it when none does
- [x] Implement in `period.py` and `check.py`; `INSIGHTS.md` example and rule; `REPORT.md` step 7
- [x] Commit

**Done when:** on a fictional history with an episode and a later run on its side, the material lists that run and `check` refuses a finding that says the measure was high only during the episode.

**Deviations:**
- A closed episode always carries `later` (the runs after its last run on its side of `range`, each `date` and `value`; `[]` when none); a switch-ended one carries none. The later values are citable figures, and `check` refuses (exit 2) a period whose closed episodes lack the key, built before this milestone.
- The rule reads a clause rather than a sentence: a word for "only" (only, solely, exclusively, just; solo, soltanto, solamente, unicamente, esclusivamente) before the episode's span or its first, last or close date, with no `, ; : . ! ?` between them and the date within about 40 characters; quoted text is not read and a paragraph's lines are joined first.
- "Only" is accepted when the sentence names every later run of the episode; a finding is read against its own dimension's episodes, the summary and the changes against all of them.
- Left for a later item, from the review: "just" or "solo" followed by a number ("just 3 of 12") is refused although it makes no claim about the episode; a decimal comma or point ends the clause, so "only to 4.5 from 14 to 16 October" passes; the 40-character reach misses longer clauses; a «» quote holding a full stop is split before it is stripped; later runs named as "21 and 24 October" are not all read; a span in another month is refused.

## R0: The deny-list lives outside the repository ✅

**Why:** `tests/python/test_no_real_names.py` keeps the denied names as unsalted sha256 digests of lowercased words. A guess can be tested against them in seconds, so the public history discloses the names it protects. Every commit also carries the author's personal email. Approved by the operator on 2026-10-19, with the history rewritten while the repository stays public and the email replaced by the GitHub noreply address.

**Approach:** the test reads the digests from a file outside the repository, named by `SKILL_DENYLIST` or, when unset, `~/.config/skill-denylist/digests.txt`; a line is either a 64-character digest or a name, normalised and hashed as before; `#` starts a comment. With no file the name check is skipped and the token and path checks still run. The digests move to that file. `git filter-repo` removes every digest the file ever held from all commits and maps the author email to the noreply address; main is force-pushed. The repository's CLAUDE.md states that the list is never committed, in any form. llm-rep's test, which this one copied, gets the same change under its own devplan.

**Tasks:**
- [x] Test: unit — the name check reads digests and names from the file `SKILL_DENYLIST` names, reports a hit as `path:line`, and is skipped when the file is missing while the token and path checks still run
- [x] Implement in `test_no_real_names.py`; move the digests to the local file; CLAUDE.md rule
- [x] Rewrite the history: digests removed from every commit, author email mapped to the noreply address; force-push main; a fresh clone holds none of the digests and no personal email
- [x] Commit

**Done when:** a fresh clone of the public repository contains none of the digests and no personal email in any commit, and the test still fails on a planted denied name when the local file exists.

## R1: The README describes what works, for someone who has never seen the skill

**Why:** the README presents the planned routes (`brief`, `design`, `setup`, `snapshot`, scheduled reports) as working, and a newcomer cannot get from it to a first report. DEVPLAN.md, CLAUDE.md and the README point to skills that are not public.

**Approach:** the README opens with what works (`adopt`, `report`, `charts`) and its walk-through goes adopt → report on a fictional study; the planned routes move under "Planned". It adds prerequisites (Python 3.10+, with the macOS note; the Sentl MCP server), the answers `adopt` asks for, a sample report on the fictional subject, what each exit code means and what to do, how to update and uninstall, a version and a CHANGELOG, contribution and support. Notes about live studies, operator approvals and private skills leave the public files.

**Tasks:**
- [ ] Test: bash — the README's routes table lists only routes whose playbook exists, outside "Planned"; the sample report passes `check`
- [ ] README, CHANGELOG, sample report; public files cleaned
- [ ] Commit

**Done when:** a reader with a Sentl account and an assistant can go from the README alone to a first report, and no public file names a private skill or a live study.

## R2: Sentl's responses are checked against what the skill expects ✅

**Why:** read-only probes showed that a change on Sentl's side gives wrong figures with exit 0 (scores on another scale, renamed sources or rubric fields) or a Python traceback with exit 1, the code that means `check` found problems. The run listing has no paging and no script reads it.

**Approach:** one module states the fields, types and ranges the skill reads from each Sentl tool (scores 1–5 or null, the known statuses, sources as url and title); `adopt`, `detect` and `ingest` refuse a response that does not match, naming the field, with exit 5. Any other unexpected error exits 6 with a one-line message. A new `monitor.py runs` reads the saved run listing, prints the runs to fetch for the report, and warns when the oldest listed run is newer than the window's start. An unknown status is reported as such, apart from runs not final yet. A question or dimension whose id changed but whose text is identical to a retired one is linked to it. The playbooks say what to do when Sentl answers with an internal error.

**Tasks:**
- [x] Test: unit — each probed change (score scale, renamed field, wrong type, missing timestamp, unknown status) exits 5 naming the field; an unexpected error exits 6
- [x] Test: unit — `runs` lists the runs of the window and warns on a listing that does not reach its start; a renumbered question with identical text keeps its comparison
- [x] Implement; playbooks and SKILL.md exit codes
- [x] Review fixes, test first: a partial or missing rubric accepted; a timestamp without a zone read as UTC; another tool's file and a missing file exit 2; `runs` lists only the window's open and unseen runs; the adopt fallback list without the latest run; copied fields not type-checked; Ctrl-C exits 130 and `--debug` works before the command; never-seen statuses worded as listed apart
- [x] Dry run on a copy of a live study: re-ingested runs give period files and a check result identical to HEAD's
- [x] Commit

**Done when:** none of the probed changes produces a report or a traceback.

**Deviations:**
- `runs` without `--project` names the latest completed run by start time, and the ones to try after it, for `adopt`; it needs no study folder. ADOPT.md step 4 uses it.
- The schema reads `pending`, `queued` and `running` as not final yet; none was seen live (A2). `ingest` refuses any other status with exit 5, where it exited 3; `runs` lists it as never seen and does not fetch the run. The results of a run not final yet are read for `id` and `status` only.
- `period` and `method` also check the saved `list-ai-models` response (exit 5).
- A file holding another tool's response (that tool's top-level key) exits 2 naming the tool, and so does a missing or unreadable file, where both exited 6 or 5 before review; exit 5 is for the right tool's response in a shape the skill does not read.
- `runs` requests again every unavailable run the listing shows as completed, inside the window or not, as ARCHITECTURE.md §Where state lives says, and points to a run already saved in `inbox/`. Its warning cannot tell a cut listing from a project with no earlier run, so it names both; a first report on a project younger than five intervals always gets it. Runs not final yet and statuses never seen are listed only inside the report's window, or with no start time; the adopt view's fallback list starts after the latest run.
- Renumbering is read against the latest version only: a dimension is linked by its name to one whose id is gone, then a question by its normalized text to one of the same dimension whose id is gone. `renumbered` and `dimension_renumbered` are recorded in the version, so the binding takes the new ids, and not in the lineage. A question moved to another dimension under a new id stays created and retired.
- A rubric may be null, empty or partial, each anchor a text or null, since Sentl does not require the anchors; a list or a key outside 1–5 is refused. `method` prints a null anchor as empty, and a null `label` is stored as empty. `label` may be null and `additional_instructions` absent.
- `parse_time` reads a time without a time zone as UTC, so `runs` and `ingest` no longer exit 6 on one. This takes over R4's item on naive timestamps; R4's text is left as it is.
- Fields the skill only copies into the run snapshot (`trigger`, `finished_at`, `error`, `sentiment`) take any value; a source's `title` is optional, and `sources: null` is read as no source.
- `--debug` is accepted before or after the command; `SENTL_MONITOR_DEBUG=1` does the same. Ctrl-C exits 130 with one line. ARCHITECTURE.md gains §Responses from Sentl and gaps G18 (errors that say what failed) and G19 (run statuses documented); README's command list names `runs`.
- Suite run under Python 3.14 and 3.11: 326 tests before, 389 after.
- Dry run on a copy of a live study, deleted afterwards: its 30 saved runs re-ingested, `period` for its report date and `check` give period files, material and check output byte-identical to HEAD's and to the study's own period files; the saved project, listing and models files pass the schema.
- Open: `get-project-tool` returns `organization` as an object (`id`, `slug`, `name`), which `adopt` copies into `study.json` and `sentl.json` as it is, where ARCHITECTURE.md shows the slug; the schema does not read it.

## R3: Every host: Claude Code, opencode, Codex, claude.ai and ChatGPT

**Why:** the skill relies on Claude Code saving large tool results to a file; the operator wants it installable and usable in Claude Code, opencode, Codex and above all the claude.ai and ChatGPT web clients, where results are not saved to a file and the sandbox does not keep files between conversations. A run of 39 answers is about 250,000 characters; a monthly report reads 4 to 150 runs, more than a web conversation holds.

**Approach:** designed and approved by the operator on 2026-10-19. Split in parts: R3a distribution and install, R3b the study carried as a pack on web clients, R3d the data paths that need Sentl's changes, R3e host verification. R3c, a read-only fetch from the script with a token, was declined by the operator: the scripts keep calling no Sentl endpoint, and Codex waits for R3d. R3a and R3b need nothing from Sentl; R3d waits for Sentl's read-side changes, requested on 2026-10-19.

**Tasks:**
- [x] Design, approved by the operator
- [ ] R3a, R3b, R3d, R3e done

**Done when:** every host in the README's support table is backed by a recorded run on the released version.

## R3a: Install on every host from one repository and one zip

**Why:** claude.ai refuses a description over 200 characters, the Claude Code plugin format expects skills under `skills/`, Codex and opencode read `~/.agents/skills`, and web users install from a zip.

**Approach:** the payload moves to `skills/sentl-monitor/` (after R2 lands). SKILL.md gets a 165-character description, the routes and trigger phrases in a `## When to use` section, `license`, `compatibility` naming the hosts, `metadata.version` as the one version source. `tools/build_zip.py` builds `dist/sentl-monitor.zip` from the tracked payload files, deterministic, with the skill folder at its root and LICENSE inside; `release.yml` attaches it and its sha256 to each GitHub release under fixed names. `.claude-plugin/marketplace.json` and `plugin.json` (skill only); `agents/openai.yaml` with the display fields and the Sentl MCP dependency. `install.sh --host claude|agents`, detection of installed hosts, `--uninstall`, no more `~/.config/opencode/skills`. `monitor.py doctor` and `--version`. README install section per host and a support table that names a host only after a recorded run (R3e).

**Tasks:**
- [ ] Test: bash — frontmatter: name equals the folder and matches the spec, description ≤ 200 with no `<` or `>`, compatibility ≤ 500, version present; LICENSE in the payload equals the root one
- [ ] Test: bash — `build_zip.py`: one root folder `sentl-monitor/`, no `__pycache__`, `.pyc` or test file, two builds byte-identical, a frontmatter over a limit refused; the extracted copy runs `monitor.py --help` and `doctor`
- [ ] Test: bash — `install.sh --host claude`, `--host agents`, detection with fake hosts in a temporary HOME, refusal with none detected, `--check` listing every install and its version, `--uninstall`, an old `~/.config/opencode/skills` install removed after the prompt
- [ ] Test: bash — marketplace and plugin JSON parse, name and version equal SKILL.md's; `claude plugin validate .` when `claude` is on PATH
- [ ] Test: unit — `doctor` reports Python version, a writable study folder, a sandbox path as not lasting; `--version` prints SKILL.md's version
- [ ] Implement the move, SKILL.md, `build_zip.py`, the workflows, the manifests, `agents/openai.yaml`, `install.sh`, `doctor`; README install section and support table
- [ ] Commit

**Done when:** a tag produces a release whose zip uploads to claude.ai as a skill, `/plugin install` and `install.sh --host agents` install it, and the suite passes on Python 3.10 to 3.13.

## R3b: A study carried between web conversations as one pack

**Why:** on claude.ai and ChatGPT the sandbox keeps nothing after the conversation, while the next report needs the versions, the report index, the latest four period files and the previous period's runs.

**Approach:** `monitor.py pack` writes a zip with a manifest (schema, skill version, last report, files with sha256) and the state the next report needs: `study.json`, `sentl.json`, versions, `reports.json`, `unavailable.json`, `last-report.json`, the latest four period files and the latest halves, the runs of the latest report's period and any ingested after it; every run before the first final report; everything with `--full`. `unpack` verifies and refuses a changed file, an unsafe path, an unknown schema (exit 5), a stale pack, another project's study. SKILL.md gains "Hosts without a lasting folder": unpack first, pack last, both files offered for download; ADOPT.md and REPORT.md say where.

**Tasks:**
- [ ] Test: unit — on the fictional three-report study, the third report's period file built after pack and unpack equals the one built in the unpruned folder
- [ ] Test: unit — the slim pack holds only the files listed; before a first final report it holds every run; `--full` holds every run and period
- [ ] Test: unit — `unpack` refuses a file whose sha256 differs, an absolute path, `..`, a link, an unknown manifest schema (exit 5), a pack older than the folder's last report, a folder bound to other projects
- [ ] Test: bash — SKILL.md, ADOPT.md and REPORT.md name `unpack` before the first command and `pack` after `check` for hosts without a lasting folder
- [ ] Implement `pack`, `unpack`; playbooks
- [ ] Commit

**Done when:** a study packed after its second report and unpacked in an empty folder produces the same third report as the original folder.

## R3c: Read Sentl from the script on a CLI host — declined

Declined by the operator on 2026-10-19: the scripts call no Sentl endpoint and hold no token. Codex is supported once R3d reads Sentl's export.

## R3d: Read runs through Sentl's export, download link and pages

Depends on Sentl: the export of several runs in one file with a download link and a panel download, pages of `get-run-results-tool` with RFC 8785 checksums, `schema_version`, ids on each response.

**Why:** run results cannot pass through a web conversation; on claude.ai and ChatGPT they reach the sandbox only as a file the sandbox downloads or the user attaches.

**Approach:** `monitor.py import` checks an export (sha256, `schema_version` through R2's schema module) and writes the project, the run listing and each run's results to `inbox/` in the tools' shapes; `download` fetches a link without credentials and imports it, exit 7 when unreachable, only if the operator approves a script that downloads from Sentl when R3d starts; otherwise the user downloads the export and attaches it; `ingest` accepts the pages of one run and checks each page's checksum; `adopt` and `ingest` match responses by `question_id` when present, by text otherwise. Playbooks give the order: a file the host saved, an export the user attached, checksummed pages, and for small responses only, a copy written by the assistant; the report on a web host runs from the pack and the export alone.

**Tasks:**
- [ ] Test: unit — `import` writes the inbox files from an export fixture; refuses a changed byte (exit 2) and an unknown `schema_version` (exit 5)
- [ ] Test: unit — `download` against a local server: sha256 checked, size cap, expired link exit 7
- [ ] Test: unit — page assembly: a missing page, a duplicate response, a different run header and a checksum mismatch each refused naming the page; the RFC 8785 test vector matches
- [ ] Test: unit — responses with `question_id` match after a one-character change in the saved text
- [ ] Implement `import`, `download`, pages in `ingest`, id matching; playbooks
- [ ] Commit

**Done when:** a report written from a pack and an export file, without any MCP result written out by the assistant, equals the report Claude Code writes from the same runs.

## R3e: Each host tested before the README says it is supported

**Why:** the hosts document little about tool-result sizes, sandbox paths and Python versions; support is claimed only after a run on the host.

**Approach:** tests on the operator's machine for the CLI hosts and checklists run by hand on the operator's own claude.ai (Pro or Max) and ChatGPT (Plus or Pro) accounts, each recorded here with date, plan, version and outcome; the README's support table changes only on a recorded pass.

**Tasks:**
- [ ] Claude Code: live tests from the plugin install and from `install.sh`
- [ ] opencode: install, MCP spill measured, adopt and report
- [ ] Codex: install, truncation measured, report from an export file once R3d ships
- [ ] claude.ai: upload, `doctor`, connector, result size measured, adopt, report, pack, new conversation, report again; the export path on Pro or Max once R3d ships
- [ ] ChatGPT: skills, developer mode and the Sentl connector checked on Plus or Pro, then the same as claude.ai where they work; no Business workspace is available, so Business, Enterprise and Edu are not claimed until a recorded run
- [ ] README support table updated from the recorded results
- [ ] Commit

**Done when:** every host in the README's table is backed by a recorded run on the released version.

## R4: Portable across systems, time zones and languages ✅

**Why:** on Windows `detect` and `check` crash on a cp1252 console and a checkout gets CRLF in `install.sh`; the period boundaries are UTC midnights while the report date is local, and no doc says so; a report language other than `it` or `en` is refused with a message that does not say why; a timestamp without a time zone raises a TypeError.

**Approach:** the script writes UTF-8 to its output on every system; `.gitattributes` keeps `*.sh` in LF; the README states the supported systems. The docs state that periods are counted in UTC and how the report date maps to them. An unsupported report language is refused with the list of supported ones; a timestamp without a time zone is read as UTC.

**Tasks:**
- [x] Test: unit — output with non-ASCII text to a cp1252 stream; a report language outside the list is refused naming the supported ones; a naive timestamp is read as UTC
- [x] Test: structure — `.gitattributes` holds `*.sh text eol=lf` and `*.py text eol=lf`
- [x] Implement: UTF-8 output, `.gitattributes`, unsupported report language refused
- [x] Docs: periods counted in UTC in `report/REPORT.md`; README "Systems and languages"
- [x] Commit

**Deviations:**
- A timestamp without a time zone read as UTC: done in R2 (`common.parse_time`); nothing ticked for it here.
- The language check is `require_language` in `common.py`, reading the supported list from the keys of `i18n.SECTIONS`; `adopt` (on an existing study), `method` and `period` call it. A `report_language` that is not set is still the operator's to answer.
- `adopt`'s question for `report_language` and `missing_answers` read the same list.
- The UTF-8 test runs `detect --dry-run` in a subprocess with `PYTHONIOENCODING=cp1252` and `PYTHONUTF8=0`.

**Done when:** the tests pass and the README states systems, time zone and languages.

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
