# Changelog

Each release of sentl-monitor, newest first. The version is `metadata.version` in
`skills/sentl-monitor/SKILL.md`.

## Unreleased

- `snapshot <subject>` runs a small study of a subject on Sentl once, in a folder of its own, and
  leaves no project running. The playbook designs four or five dimensions from the catalogue
  with one question each, creates one project paused with no schedule, shows `estimate-run-tool`
  in credits, starts one run only on the operator's go, writes a report in its own order (what
  was done, the dimensions, the questions, the scoring, the findings, and what a single run
  cannot show), then pauses the project and gives the operator the panel link to archive it,
  since Sentl's MCP cannot archive a project. `validate`, `review`, `payload`, `bind`, `period`,
  `method` and `check` have a snapshot mode: `validate` refuses other than four or five
  dimensions, a dimension with other than one question, an unknown catalogue id, rounds above
  one and a schedule; `check` refuses a changes section and a figure for the whole project.
  `monitor.py resume` names the step a folder is at, from its files and the run listing, and
  `monitor.py close` records `closed` with `archive: operator` in `sentl.json`.
- `report` runs unattended when a scheduler starts it. `monitor.py pending` reads the run
  listings the assistant saved and records `nothing_new` when no completed run is new, so two
  invocations on the same runs write one report. `period` records `below_floor` when no run
  has 90% of its answers judged. `check --unattended` keeps a report that fails as
  `reports/<date>.draft.md`, counted as the previous report. `history/last-report.json` holds
  the outcome of the latest invocation: `written`, `draft`, `nothing_new` or `below_floor`. The
  README gives two recipes: a local scheduler starting a headless assistant with an API token,
  and a cloud scheduled agent whose study folder is a private repository.
- `setup` creates the study's projects in Sentl, paused, and saves their questions without
  cutting the link between a question and its past results. `monitor.py payload` prints the
  arguments of `create-project-tool`, `update-project-settings-tool` and
  `save-project-questions-tool` from `study.json`, every id taken from `sentl.json`; a new
  question or dimension is sent without an id, a dropped dimension is sent archived, a text that
  differs from Sentl's only by quotes or spacing is sent as Sentl has it, and `delete_missing`
  is never set. It refuses while a completed run has not been ingested (a run recorded as
  unavailable does not block) and when the project in Sentl differs from its latest recorded
  version. `bind` records the ids and a `setup` version from a saved `get-project-tool`
  response, and refuses a saved project that lacks a text of the latest run or does not hold
  `study.json`. The playbook asks for the operator's go before every write, dry run included,
  and starts a run or a schedule only after `estimate-run-tool`.
- `design` turns the approved themes into a study: dimensions taken from a catalogue
  (`design/catalogue.md`, with question patterns, rubric anchors, the facts each dimension needs
  and the stance and fidelity axes), projects, who asks, questions with 1-5 rubrics and a
  narrative. `monitor.py validate` refuses a study that breaks Sentl's field limits or the design
  rules (a dimension fed by no theme, an alias in a question marked as naming no brand, a
  dimension leaning one way in search without a question of the opposite framing, a malformed
  pair, duplicate keys or texts, a model Sentl no longer offers) and warns about the rest.
  `review` writes `study-review.md` with the narrative, the theme inventory, every question and
  rubric and a credit estimate from the models' tariffs. `revise` records each changed
  question as reworded (same key), new intent (new key, old key retired) or criteria.
- `brief <subject>` lists the themes to monitor with the origin of each, collects how people
  search for them and writes `brief.md`. `monitor.py demand` sends each seed query, as typed and
  with each question stem, to Google's suggestions (the skill's only network call; exit 1 lists
  the prefixes that failed), merges search volumes that a keyword-data server returned or that an
  export file holds, classes every keyword as subject, foil, component or generic, and prints
  each theme's summary. Volumes are stated for each class and never added across classes.
- The report's themes section gives each theme's distinct Google suggestions and, when a volume
  source was used, its monthly searches for each class; without one it says what the counts measure.
- `import` writes the project, the run listing and the runs of Sentl's run export into the
  study folder; `download` fetches the export's link first. The link is fetched with no
  credential, only over https from Sentl's own hosts, and a file over 64 MB is refused. Exit 7
  means the link does not answer.
- `ingest --pages` joins the pages of one run, each checked by its `content_sha256` (RFC 8785).
- A response that carries `question_id` is matched to its question by id; one without it, by text.

## 0.1.0 (2026-10-19)

The first release. It reports on Sentl projects that already exist; the routes that design a
study and create projects in Sentl are planned (README, "Planned").

- `adopt <project>` takes an existing Sentl project into a study folder and asks for what Sentl
  does not hold: the research question and purpose, who asks, the subject and its competitors
  with their websites, the facts to track with their current and outdated values, the market,
  the report's language, the report cadence and where each theme came from. It only reads from
  Sentl.
- `report` writes a dated report on the runs of the last week or month: how the study was built,
  a summary, what the assistants say per dimension with verbatim excerpts and the cited domains,
  and what changed since the previous period. It only reads from Sentl and spends no credits.
- The first report compares with up to four earlier periods rebuilt from the project's runs, or,
  on a project younger than one period whose runs span at least 14 days, the second half of its
  period with the first.
- Each figure comes with what explains it: whether the answers state a fact as it is now or as
  it was, the pages cited with each, how many of the answers are independent (the rounds of a run
  that cite the same pages count as one), movements inside a period and the day they started, the
  subject's presence run by run, answers that found no evidence, and whether the cited pages are
  the subject's own, a competitor's or a third party's.
- Questions edited in the Sentl web panel are detected; a reworded question keeps its
  comparison, and a question that now asks something else starts a new one.
- `monitor.py check` refuses a report whose quotes are not verbatim, whose figures are not the
  period's, whose sections are out of order, or which shows an internal id, a file name or a
  credit figure.
- `monitor.py charts` writes a report's figures as chart tables for a deck in
  [md2](https://github.com/GuidanceStudio/md2), which turns Markdown into HTML presentations.
- `monitor.py doctor` checks Python and the study folder; `monitor.py --version` prints the
  version.
- `monitor.py pack` and `unpack` carry a study between conversations on a host that deletes its
  files when the conversation ends.
- Reports in English or Italian; Linux, macOS and Windows through WSL.
- Install as a Claude Code plugin, with `install.sh` for Claude Code, Codex and opencode, or as a
  zip for claude.ai and ChatGPT. Tested in Claude Code only. On claude.ai, ChatGPT and Codex the
  skill installs, but a report needs Sentl's run export, which is not available yet.
- A sample report on a fictional brand, in `examples/`.
