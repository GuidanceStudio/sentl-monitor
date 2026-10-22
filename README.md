# sentl-monitor

sentl-monitor is a skill for AI assistants such as Claude Code. It reads the runs of a
[Sentl](https://sentl.ai) project and writes a dated report on what AI assistants tell people
about a brand, a product category or an organisation, comparing each period with the earlier
ones. The report quotes the answers verbatim and says which facts they state, which pages they
cite and what moved since the previous period; it is meant for a consultant or an analyst who
reports to a client or to management every week or month.

Sentl measures how AI models describe a subject: a Sentl project asks its questions to several
AI assistants, and a judge scores each answer from 1 to 5 against a rubric written for that
question. The skill reads Sentl through Sentl's MCP server and makes no model calls of its own.

## What works today

| Route | What it does |
|---|---|
| `adopt <project>` | Takes a project that already exists in Sentl into a study folder on your computer, and asks you for what Sentl does not hold: the research question, the competitors, the facts to track, the market, the report's language and how often a report is written |
| `report` | Reads the runs completed since the previous report, compares the period with up to four earlier ones and writes `reports/<date>.md`; on request, also `reports/<date>.charts.md`, the report's figures as chart tables for [md2](https://github.com/GuidanceStudio/md2), a converter from Markdown to HTML presentations; started by a scheduler it runs [unattended](#scheduled-reports) |
| `brief <subject>` | Lists the themes to monitor, each with its origin (the client's material, the issues the client raised, Google searches), collects how people search for them and writes `brief.md` for your review |
| `design` | Turns the approved themes into dimensions, projects, questions as people type them and a 1–5 rubric for each, checks them against Sentl's limits and the design rules, and writes `study.json` and `study-review.md`, with the credit estimate, for your review |
| `setup` | Creates the study's projects in Sentl, paused, and later saves changed questions without cutting the link between a question and its past results; records the ids in `sentl.json`, shows Sentl's credit estimate, and starts a run or activates a schedule only on your explicit go |

`adopt` and `report` only read from Sentl: they create and change nothing in your account and
spend no credits. `brief` does not call Sentl at all, and `design` reads only the list of models
and their tariffs. `setup` writes to your account, and each write (creating a project, a dry
run and a save of its questions, a change of settings, a run, a schedule) waits for your go;
it needs the Owner or Admin role, and only a run spends credits. You invoke a route by asking the
assistant, for example `sentl-monitor adopt Avenello` or `sentl-monitor report`.

The routes run `monitor.py`, the skill's command-line script. Besides the steps of the
routes, it has `demand` (Google suggestions, search volumes and their summary, for `brief`), `validate`,
`review` and `revise` (the checks, the review and the question lineage of `design`), `payload` and `bind` (the arguments `setup` sends to Sentl, printed and never sent, and the ids it records from Sentl's response), `doctor` (checks Python and the study folder), `--version`, `runs` (lists the
runs a report needs), `pending` (says whether an unattended report has a run to report on) and `pack` and `unpack`, which carry a study between conversations on a
host that deletes its files when the conversation ends.

| Host | Install with | Status |
|---|---|---|
| Claude Code | the plugin, or `./install.sh --host claude` | Tested with `install.sh`: `adopt` and `report` work. The plugin install is not yet tested. |
| opencode | `./install.sh --host agents` | Not yet tested: it installs, and `adopt` and `report` have not been run there. |
| Codex | `./install.sh --host agents` | Not yet tested: it installs; a report reads Sentl's run export (`import`), which has not been run there. |
| claude.ai | the release zip, uploaded as a skill | Not yet tested: the zip is built to claude.ai's skill limits; a report reads Sentl's run export, which has not been run there. |
| ChatGPT | the release zip | Not yet tested; uploading the zip on chatgpt.com is not confirmed, and a report reads Sentl's run export, which has not been run there. |

A report reads the complete results of every run in its period; one run of 39 answers is about
250,000 characters. Those results reach the study folder only on a host that saves a large tool
result to a file, and today that means Claude Code. On claude.ai, ChatGPT and Codex a report
reads an export file of the runs from Sentl: the assistant calls Sentl's `export-runs-tool`, and
the skill's `download` or `import` command writes the runs into the study folder. These commands
are written and tested against the export's documented shape; they have not been run on those
hosts yet.
Whether opencode saves a large result to a file has not been measured.

## Prerequisites

- **Python 3.10 or later**, standard library only. `python3 --version` prints it. macOS ships
  Python 3.9: install 3.10 or newer, from python.org or Homebrew, before the first run.
- **A Sentl account** in an organization with a project that has completed runs. The User role
  is enough for `adopt` and `report`, which only read; `setup` needs Owner or Admin. The project's questions, rubrics and
  schedule are set in the Sentl web panel; `adopt` reads them.
- **The Sentl MCP server connected to your assistant.** Sentl's setup page,
  https://app.sentl.ai/mcp/setup, gives the configuration for each client and names the server
  `sentinel-reputation`; the steps for each host are under [Install](#install). The skill finds
  Sentl's tools by their suffix, so it works whatever the server is called. The
  assistant signs in through the browser (OAuth). For a client without OAuth, create a token in
  Sentl under **Integrations → API Tokens** and pass it as an `Authorization: Bearer` header, as
  the setup page shows. The skill never asks for the token and never stores it.

## Install

### Claude Code

From a clone of this repository, the install that has been tested:

```bash
git clone https://github.com/GuidanceStudio/sentl-monitor
cd sentl-monitor
./install.sh --host claude
```

The skill's folder is then `~/.claude/skills/sentl-monitor`.

Or as a plugin, not yet tested, in a terminal:

```bash
claude plugin install sentl-monitor --marketplace GuidanceStudio/sentl-monitor
```

The command adds the marketplace first when it is not added yet. If `claude plugin install
--help` does not list `--marketplace`, add the marketplace, then install:

```bash
claude plugin marketplace add GuidanceStudio/sentl-monitor
claude plugin install sentl-monitor@sentl-monitor
```

The skill's folder is then `skills/sentl-monitor` inside the `installPath` that
`claude plugin list --json` reports for `sentl-monitor@sentl-monitor`.

Connect Sentl for every folder you open Claude Code in (`--scope user`), then run `/mcp`, select
`sentinel-reputation` and sign in:

```bash
claude mcp add --scope user --transport http sentinel-reputation https://app.sentl.ai/mcp/reputation
```

### opencode

```bash
./install.sh --host agents
```

The skill's folder is then `~/.agents/skills/sentl-monitor`; opencode reads `~/.agents/skills`
and `~/.claude/skills`. Add Sentl to `opencode.json` as a remote MCP server, as Sentl's setup page
shows: https://app.sentl.ai/mcp/setup.

### Codex

```bash
./install.sh --host agents
```

The skill's folder is then `~/.agents/skills/sentl-monitor`. Connect Sentl as the server
`sentinel-reputation`, then sign in:

```bash
codex mcp add sentinel-reputation --url https://app.sentl.ai/mcp/reputation
codex mcp login sentinel-reputation
```

A report in Codex reads Sentl's run export; this has not been tested in Codex yet.

### claude.ai

1. Download `sentl-monitor.zip` from the latest release,
   https://github.com/GuidanceStudio/sentl-monitor/releases/latest/download/sentl-monitor.zip.
   Its sha256 is in `sentl-monitor.zip.sha256`, next to it. The link works once v0.1.0 is
   released.
2. In Settings → Capabilities, turn on code execution.
3. In Customize → Skills, upload the zip.
4. In Settings → Connectors, add a custom connector with the URL
   `https://app.sentl.ai/mcp/reputation`, and sign in.

On Team and Enterprise plans, an owner can add the skill for the whole organization. A report on
claude.ai reads Sentl's run export, since a run's results do not fit in a conversation; this has
not been tested on claude.ai yet.

### ChatGPT

OpenAI documents standalone skills in the ChatGPT desktop app, the Codex CLI and the
IDE extension, and on the web only inside plugins. Whether the release zip uploads as a skill
on chatgpt.com is not confirmed. Sentl connects as a connector in developer mode, with the URL
`https://app.sentl.ai/mcp/reputation`. A report in ChatGPT reads Sentl's run export; this has not been tested
in ChatGPT yet.

### Every assistant at once

```bash
./install.sh                # installs for every assistant it finds: ~/.claude, ~/.codex, ~/.config/opencode, codex or opencode on PATH
./install.sh --force        # overwrites without asking; needed without a terminal
```

### Check the install

`./install.sh --check`, run from the clone, lists every install of the skill with its version
and says whether it matches the clone. `doctor` reports the Python version, whether a study
folder can be written, and whether it lies in a web sandbox whose files are deleted when the
conversation ends; the assistant runs it first in every conversation.

```bash
./install.sh --check
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py doctor --study ./avenello-study
```

With `--host agents` or the plugin, put that install's skill folder in place of
`~/.claude/skills/sentl-monitor`.

On a host that deletes its files when the conversation ends, the study travels as a pack, one zip
file: at the end of each route the assistant writes it with `monitor.py pack` and offers it for
download, and in the next conversation you attach it and the assistant unpacks it first.

## A first report, step by step

Avenello is a fictional oat-milk brand. Its marketing team has a Sentl project, *Avenello · US
market*, that asks three questions every day to two AI assistants, Acme Chat and Orbit Reason,
three times each:

- Nutrition: «How much sugar is in Avenello oat milk?»
- Choice: «What is the best oat milk to buy?», which names no brand, so it measures whether
  Avenello is named at all.
- Sustainability: «Is Avenello oat milk good for the environment?»

The project has run every day since 1 October 2026. On 14 October you write the first weekly
report.

### 1. Adopt the project

In the assistant, opened in the folder where you keep client work, type:

```text
sentl-monitor adopt Avenello
```

The assistant lists your Sentl projects and picks the one whose name matches, asking you when
more than one does. It proposes the study folder `./avenello-study/`, checks it with
`monitor.py doctor`, and saves the project and its latest run into the folder's `inbox/`. Then it asks, in
one message, for what Sentl does not hold, proposing values from the project's rubrics where it
can. The answers appear in the report as written, so you write them in the report's language.
For Avenello:

| The assistant asks for | You answer |
|---|---|
| The research question, neutral: what is monitored, never one valence of it | What are people who ask an AI assistant about oat milk told about it and about Avenello? |
| The purpose: what the client will decide with the reports | Find the facts about Avenello that assistants state wrongly and the pages they take them from, to decide which pages to update. |
| Who asks the questions, and why | A generic consumer: the questions are the ones any shopper types; no persona changes them. |
| Who wrote the rubrics, and when | Avenello's marketing team, 15 September 2026 |
| The subject: its name as answers write it, and its own websites | Avenello; avenello.example |
| Foils: the competitors, as answers write them, and their websites | Avoria; avoria.example |
| Facts that carry a figure or a name, with the current and the outdated value as answers write them | On the sugar question: Avenello Original has 3 g of sugar per 100 ml since the March 2026 recipe, and had 5 g before; current «3 g», outdated «5 g»; source avenello.example/nutrition, read on 15 September 2026 |
| The market: country and language | United States, English |
| The report's language: English or Italian | English |
| How often a report is written: weekly or monthly | Weekly |
| Where each dimension's theme came from | Nutrition: customer-service questions about the new recipe. Choice: Google autocomplete, United States, September 2026. Sustainability: Avenello's 2025 sustainability report |

The assistant writes the answers into `avenello-study/study.json` and tells you the dimensions
and questions it adopted and how many completed runs the project has: 14, from 1 to 14 October.
The first report covers the last week, 8 to 14 October, and compares it with the week before,
rebuilt from the project's earlier runs. A first report compares with up to four earlier weeks
or months. A first monthly report on a project younger than a month compares the second half of
the month with the first, once its runs span 14 days. With daily runs a report also gives the day
a movement started; four weekly runs are too few to date one.

### 2. Write the report

```text
sentl-monitor report
```

The assistant saves the project again, to find questions edited in the Sentl web panel since the
last report; when one was reworded, it asks you whether the question still asks the same thing.
It saves the results of the 14 runs into `inbox/` and runs the script on them, from the skill's
folder (here the one `install.sh --host claude` writes); `market` is the short name `adopt` gave
the project in the study folder:

```bash
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py runs --study avenello-study --project market --saved avenello-study/inbox/runs-701.json --date 2026-10-14
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py ingest --study avenello-study --project market --results avenello-study/inbox/run-9408.json
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py period --study avenello-study --date 2026-10-14 --models avenello-study/inbox/models.json
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py method --study avenello-study --date 2026-10-14 --models avenello-study/inbox/models.json
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py check --study avenello-study avenello-study/reports/2026-10-14.md
```

`runs` lists the runs to fetch, `ingest` stores each one, `period` computes the figures of the
week and of the week before, and `method` writes the sections on how the study was built. The
assistant then writes what the assistants say, dimension by dimension, from the answers and the
figures `period` prepared, and `check` verifies the report: every quote is verbatim, every figure
is the period's, the sections are in order, and no internal id appears. The assistant corrects
the report until `check` passes.

What comes out:

```text
avenello-study/
  study.json              your answers, and the project's dimensions, questions and rubrics
  sentl.json              the Sentl project the study reads
  inbox/                  Sentl's responses, as the assistant saved them
  history/                the runs, the periods, the project's versions and the material each report is written from
  reports/2026-10-14.md   the report
```

In the chat, and never in the report, the assistant tells you the runs the report covers, the
week rebuilt from earlier runs, and anything to check: runs not final yet, runs left out, edits
found in Sentl. Ask for the charts and it writes `reports/2026-10-14.charts.md` with
`monitor.py charts`.

### 3. The next reports

A week later, `sentl-monitor report` again. It reads the runs started after the last run of the
previous report, compares the new week with up to four earlier ones, and the report opens with
what changed.

## A sample report

[examples/avenello-report-2026-10-14.md](examples/avenello-report-2026-10-14.md) is the first
report of the walk-through above, written on fictional runs by the same steps; a test checks
that it still passes `check`. Its sections:

1. **What we did and to what end**: the purpose, the questions, the assistants and how many
   answers were scored.
2. **Where the themes came from**: the origin of each dimension's theme.
3. **The dimensions and how we reached them**, and who asks the questions.
4. **The questions**, as Sentl asks them.
5. **How the answers are scored**: what 5, 3 and 1 mean for each question, and what counts as a
   change between periods.
6. **In short**: three to five sentences with the figures that matter.
7. **What the assistants say**: for each dimension, verbatim excerpts with their question and
   assistant, the cited domains, the score, and what explains it: the facts the answers state,
   current or outdated, the pages behind them, movements inside the week, the subject's presence
   run by run, and who wrote the cited pages.
8. **What changed**: the scores and shares that moved since the week before and, since the
   project runs daily, the day each movement started; the assistants whose verdict changed, with
   both answers; and the domains newly cited or no longer cited.

From the second report on, "What changed" and "What the assistants say" come first and the
sections on method close the report.
[examples/avenello-report-2026-10-14.charts.md](examples/avenello-report-2026-10-14.charts.md)
holds the same report's figures as chart tables for md2.

## Scheduled reports

Two clocks run independently. Sentl runs the measurement, on the project's schedule (daily,
weekly or monthly) once `setup` has activated it. A scheduler on your side starts the assistant
that writes the report. Started that way, `report` is unattended: it asks no question and
Sentl is only read.

- It lists each project's runs, and stops with `nothing_new` when no completed run is new since
  the previous report. A run still open is read at the next invocation.
- A run with under 90% of its answers judged is left out of the period; when no run is left it
  stops with `below_floor`. A dimension with under 80% of its answers judged is shown without a
  figure.
- A report that fails `check` is kept as `reports/<date>.draft.md`, not corrected, and the next
  invocation does not write it again. Fix it, rename it to `reports/<date>.md` and run `check`
  on it to make it final.
- `history/last-report.json` holds the time, the outcome (`written`, `draft`, `nothing_new` or
  `below_floor`) and a one-line detail of the latest invocation. Two invocations on the same
  runs write one report, and the second records `nothing_new`.

Start it after the project's scheduled run has completed. The study folder must have been set
up by `adopt` or `setup`, with its `study.json` answered in full, because nobody can answer
a question at 07:00.

### A local scheduler

cron, launchd or a systemd timer starts a headless assistant in the study folder. The Sentl
connection uses an API token, because signing in through the browser needs a person, and a
sign-in unused for 30 days must be repeated. A token with the User role is enough, since the
report only reads. Create it in Sentl under **Integrations → API Tokens**, then add the server to
Claude Code; the token is read from the terminal, stored in the assistant's own configuration and
never in the study folder:

```bash
read -rs SENTL_TOKEN
claude mcp add --scope user --transport http sentinel-reputation https://app.sentl.ai/mcp/reputation --header "Authorization: Bearer $SENTL_TOKEN"
unset SENTL_TOKEN
```

The crontab line below starts the report every Monday at 07:00. It allows the script, file edits
and the five Sentl tools the report reads, so the unattended assistant cannot create a project,
change a setting or start a run:

```text
0 7 * * 1  cd <study folder> && claude -p "Run the sentl-monitor skill: report, unattended, for the study in this folder." --allowedTools "Bash(python3 *)" Read Write Edit mcp__sentinel-reputation__list-organizations mcp__sentinel-reputation__get-project-tool mcp__sentinel-reputation__list-runs-tool mcp__sentinel-reputation__get-run-results-tool mcp__sentinel-reputation__list-ai-models >> <log file> 2>&1
```

The log file holds the assistant's closing message, which names the outcome. Read
`history/last-report.json` to see the outcome without the log. This recipe has not been run
on a schedule yet. Other assistants take the same prompt in their own headless mode; the skill needs the study folder as the working directory,
its Python and the Sentl tools.

### A cloud scheduled agent

An assistant's own scheduler, such as a scheduled cloud agent, starts every run in a fresh
environment, so the study folder must live somewhere that lasts: a **private** repository
holding the study folder. The reports and the saved answers are client data, so the repository
must not be public. Keep `inbox/` out of it, since the agent saves Sentl's responses there again
at each invocation:

```text
inbox/
```

Give the agent the repository, the skill (installed as under [Install](#install)) and the Sentl
server as a connector with an API token, then schedule this prompt, weekly at a time after the
project's scheduled run:

```text
In the repository's root, run the sentl-monitor skill: report, unattended. Then, if any file
changed, commit reports/ and history/ with the message "report <date>: <outcome>", where
<outcome> is the outcome in history/last-report.json, and push to <branch>.
```

The commit holds `history/last-report.json` too, so the repository shows the outcome of every
invocation.

## Exit codes

Every `monitor.py` command ends with one of these codes. The assistant reads them and follows
the playbook; this table is for when you run a command yourself or the assistant stops.

| Code | Meaning | What to do |
|---|---|---|
| 0 | Done. | Nothing. |
| 1 | `check` found problems in the report, or `validate` in the study, listed one per line, `doctor` found that the study folder cannot be written, or `demand autocomplete` could not fetch some of Google's suggestions and lists the prefixes. | The assistant corrects the report and runs `check` again until it passes. For `doctor`, choose another folder. For `demand autocomplete`, run it again: it fetches only the missing prefixes. |
| 2 | Input refused: a saved response is incomplete or belongs to another tool or project, a field of `study.json` is not filled in, a pack was changed, is older than the folder's last report or belongs to another study, or Python is older than 3.10. The message says why and what to do. | Follow the message: save the Sentl response again, answer the field it names, attach the latest pack, or install a newer Python. |
| 3 | A run is not final yet. | Nothing: the next report reads it. |
| 4 | No run of the period has 90% of its answers scored, or the period has no run. | Wait for the runs to complete, or check in the Sentl web panel why answers were not scored. |
| 5 | A Sentl response does not have the shape the skill reads, or a pack was written by a later version of the skill. The message names the tool and the field. | Do not edit the saved file. Update the skill; if the latest version still exits 5, open an issue naming the tool and the field. |
| 6 | Unexpected error. | Run the same command again with `--debug` and open an issue with its output. |
| 130 | Interrupted with Ctrl-C. | Run the command again. |

## Time zone, systems and languages

Periods are counted in UTC: a report dated D covers the runs started up to the end of D in UTC,
and the report date is today's local date unless one is given.

Linux and macOS are supported, and Windows through WSL. On native Windows the script runs, but
the playbooks' commands assume a POSIX shell.

Reports are written in English or Italian. The questions can be in any language. Answers in
which an assistant says it found no source of the kind asked for are detected in English and
Italian answers only.

## Update and uninstall

Plugin install, in Claude Code:

```bash
claude plugin update sentl-monitor@sentl-monitor
claude plugin uninstall sentl-monitor@sentl-monitor
```

Clone install: `git pull`, then `./install.sh --force`; `./install.sh --check` shows whether
every install matches the clone.

```bash
./install.sh --uninstall    # removes sentl-monitor from ~/.claude/skills, ~/.agents/skills and ~/.config/opencode/skills
```

`--uninstall` asks before removing each folder, and needs `--force` without a terminal; `--host`
or `--dest` limits it to one place.

claude.ai: remove the skill in Customize → Skills, then upload the zip of the new release;
removing it there uninstalls it.

Updating or uninstalling never touches a study folder.

## Version and changes

The version is `metadata.version` in `skills/sentl-monitor/SKILL.md`; the plugin manifests
repeat it, and `monitor.py --version` prints it. [CHANGELOG.md](CHANGELOG.md) lists what each release holds,
and the releases, with their zips, are at
https://github.com/GuidanceStudio/sentl-monitor/releases.

## Planned

This route is designed in [ARCHITECTURE.md](ARCHITECTURE.md) and scheduled in
[DEVPLAN.md](DEVPLAN.md); it is not available yet.

| Route | What it will do |
|---|---|
| `snapshot <subject>` | Run a small study on Sentl once, write a short report, and pause the project |

`snapshot` will spend Sentl credits and need the Owner or Admin role in the organization; it
will show Sentl's estimate before a run starts.

## Contributing and support

Report a bug or ask a question in the repository's issues,
https://github.com/GuidanceStudio/sentl-monitor/issues. Give the command, its exit code and its
message, and for exit 5 the tool and the field it names. Never paste a token, an account name or
a client's data: describe the shape instead.

The tests use the Python standard library and need no Sentl account:

```bash
bash tests/test_all.sh
```

It runs the bash suites (layout, skill, install, package) and the Python unit tests. The live
tier reads a real study folder outside the repository and runs only when asked:
`RUN_LIVE=1 SENTL_LIVE_STUDY=<folder> SENTL_LIVE_PROJECT=<project id> bash tests/test_all.sh`.
The `setup` live test checks a study folder that the route set up in an organization you
designate for tests, with no run started: `RUN_LIVE=1 SENTL_LIVE_SETUP_STUDY=<folder>
SENTL_LIVE_TEST_ORG=<organization slug> bash tests/test_all.sh`.
The search-demand live test needs only `RUN_LIVE=1`: it sends one request to Google's suggestion
endpoint.
`python3 tests/python/sample_study.py <empty folder>` builds the fictional study the sample
report was written from.

The repository is public: fixtures, examples and docs use fictional subjects, and a change must
not name a real client, brand or person. Design and plan are in [ARCHITECTURE.md](ARCHITECTURE.md)
and [DEVPLAN.md](DEVPLAN.md).

```
README.md              this file
CHANGELOG.md           what each release holds
LICENSE                MIT
ARCHITECTURE.md        stages, files, schemas, MCP mapping, history model, gaps
DEVPLAN.md             milestones
install.sh             installs the skill for Claude Code, Codex and opencode
.claude-plugin/        the Claude Code plugin and marketplace manifests
.github/workflows/     the tests on Python 3.10 to 3.13; the release zip on a v* tag
tools/build_zip.py     builds dist/sentl-monitor.zip, the zip claude.ai and ChatGPT upload
examples/              the sample report and its charts
skills/sentl-monitor/  the skill
  SKILL.md             router
  LICENSE              copy of LICENSE, shipped in the zip
  agents/openai.yaml   Codex's display fields and the Sentl MCP dependency
  adopt/ADOPT.md       route playbooks, one per route
  brief/BRIEF.md
  design/DESIGN.md     how a study is designed; design/catalogue.md is the dimension catalogue
  setup/SETUP.md       how the study's projects are created and saved in Sentl
  report/REPORT.md
  report/INSIGHTS.md   how a report states each insight
  scripts/monitor.py   the command line: adopt, detect, runs, pending, ingest, period, method, check, charts, demand, validate, review, revise, payload, bind, doctor, pack, unpack
  scripts/sentlmon/    its implementation, standard library only
tests/                 bash suites, Python unit tests, opt-in live tests
```

Study folders hold client data and live outside this repository.

## Licence

MIT, see [LICENSE](LICENSE).
