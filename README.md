# sentl-monitor

sentl-monitor is a skill for AI assistants such as Claude Code. It reads the runs of a
[Sentl](https://sentl.ai) project and writes, for each period, a short slide deck on what AI
assistants tell people about a brand, a product category or an organisation, compared with the
earlier periods. The deck says what was found and what to do about it, quotes the answers
verbatim and names the pages they cite; it is meant for a consultant or an analyst who reports
to a client or to management every week or month.

Sentl measures how AI models describe a subject: a Sentl project asks its questions to several
AI assistants, and a judge scores each answer from 1 to 5 against a rubric written for that
question. The skill reads Sentl through Sentl's MCP server and makes no model calls of its own.

## What works today

| Route | What it does |
|---|---|
| `adopt <project>` | Takes a project that already exists in Sentl into a study folder on your computer, and asks you for what Sentl does not hold: the research question, the competitors, the facts to track, the market, the deck's language and how long a period is |
| `report` | Reads the runs completed since the previous period, compares the period with up to four earlier ones and goes on into the deck: one short slide deck for the client's marketing manager, with what was found and three to five actions (fewer when the evidence slides allow fewer), printed as a PDF in Sentl's look or your own ([make it yours](#make-it-yours)); started by a scheduler it runs [unattended](#scheduled-reports). `report --quick` writes a quick deck in its place, each topic's figure with one sentence and one passage of an answer and no actions (`report/QUICK.md`); the `deck` route (`report/DECK.md`) writes the deck of a period already built: one a session left unfinished, or one written again after the period was rebuilt |
| `brief <subject>` | Lists the themes to monitor, each with its origin (the client's material, the issues the client raised, Google searches), and the personas who ask about the subject, each with its situation, its decision and the Google suggestions that show it searches; keeps regulators, consumer associations and the press apart as sources to watch; collects how people search and writes `brief.md` for your review |
| `design` | Turns the approved themes into dimensions, projects, questions as people type them and a 1–5 rubric for each, ties each question to a persona of the brief, checks them against Sentl's limits and the design rules, and writes `study.json` and `study-review.md`, with the credit estimate, for your review |
| `setup` | Creates the study's projects in Sentl, paused, and later saves changed questions without cutting the link between a question and its past results; records the ids in `sentl.json`, shows Sentl's credit estimate, and starts a run or activates a schedule only on your explicit go |
| `snapshot <subject>` | Runs a small study of a subject on Sentl once, in a folder of its own: four or five dimensions from the catalogue, each with one question that starts from Google's top suggestion and names the person who asks it, one snapshot in Sentl, which takes none of the plan's project slots, one run on your go after Sentl's credit estimate, and the deck of that run; then you keep the snapshot, delete it, or follow the subject with `brief` and `design`. Invoked again in the same folder, it resumes where it stopped |
| `compare <folder> <folder>` | Writes what changed between two snapshots of one subject with the same questions, neither promoted: each dimension's score and presence on both sides. It reads the two folders only and spends nothing. |

`adopt` and `report` only read from Sentl: they create and change nothing in your account and
spend no credits. `brief` does not call Sentl at all, and `design` reads only the list of models
and their tariffs. `setup` writes to your account, and each write (creating a project, a dry
run and a save of its questions, a change of settings, a run, a schedule) waits for your go;
it needs the Owner or Admin role, and only a run spends credits. `snapshot` writes in the same way and needs the same
role; its one run spends the credits Sentl's estimate showed before your go. You invoke a route by asking the
assistant, for example `sentl-monitor adopt Avenello` or `sentl-monitor report`.

The routes run `monitor.py`, the skill's command-line script. Besides the steps of the
routes, it has `demand` (Google suggestions, search volumes and their summary, for `brief`), `validate`,
`review` and `revise` (the checks, the review and the question lineage of `design`), `payload` and `bind` (the arguments `setup` sends to Sentl, printed and never sent, and the ids it records from Sentl's response), `resume` and `close` (the step a `snapshot` folder is at, and the record of whether the snapshot was kept, archived or deleted), `pdf` (the deck as a PDF, and the copy to send; `pdf --quick` and `deck --quick` for the quick deck), `page` (what a page the answers cite holds), `doctor` (checks Python and the study folder), `--version`, `runs` (lists the
runs a period needs), `pending` (says whether an unattended `report` has a new run) and `pack` and `unpack`, which carry a study between conversations on a
host that deletes its files when the conversation ends.

| Host | Install with | Status |
|---|---|---|
| Claude Code | the plugin, or `./install.sh --host claude` | Tested with `install.sh`: `adopt` and `report` work. The plugin installs from the marketplace and `report` works on it. |
| opencode | `./install.sh --host agents` | Tested with Sentl's MCP as a remote server: `snapshot`, `adopt`, `report` and `deck` work, also unattended with `opencode run`. |
| Codex | `./install.sh --host agents` | Tested with Sentl's MCP: `adopt` and `report` from Sentl's run export work. Unattended, `codex exec` needs `--approve-for-me`, or it refuses every call to Sentl, and network access in its sandbox to download the export. |
| claude.ai | the release zip, uploaded as a skill | Not yet tested: the zip is built to claude.ai's skill limits; a report reads Sentl's run export, which has not been run there. |
| ChatGPT | the release zip | Not yet tested; uploading the zip on chatgpt.com is not confirmed, and a report reads Sentl's run export, which has not been run there. |

`report` reads the complete results of every run in its period; one run of 39 answers is about
250,000 characters. Those results reach the study folder only on a host that saves a large tool
result to a file, and today that means Claude Code. On claude.ai, ChatGPT and Codex `report`
reads an export file of the runs from Sentl: the assistant calls Sentl's `export-runs-tool`, and
the skill's `download` or `import` command writes the runs into the study folder. These commands
are written and tested against the export's documented shape; they have not been run on those
hosts yet.
Whether opencode saves a large result to a file has not been measured.

## Prerequisites

- **Python 3.10 or later**, standard library only. `python3 --version` prints it. macOS ships
  Python 3.9: install 3.10 or newer, from python.org or Homebrew, before the first run.
- **A Sentl account** in an organization with a project that has completed runs. The User role
  is enough for `adopt` and `report`, which only read; `setup` and `snapshot` need Owner or Admin. The project's questions, rubrics and
  schedule are set in the Sentl web panel; `adopt` reads them.
- **The Sentl MCP server connected to your assistant.** Sentl's setup page,
  https://app.sentl.ai/mcp/setup, gives the configuration for each client and names the server
  "Sentl MCP" (`sentl-mcp` in the commands below); the steps for each host are under [Install](#install). The skill finds
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
`sentl-mcp` and sign in:

```bash
claude mcp add --scope user --transport http sentl-mcp https://app.sentl.ai/mcp
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
`sentl-mcp`, then sign in:

```bash
codex mcp add sentl-mcp --url https://app.sentl.ai/mcp
codex mcp login sentl-mcp
```

A report in Codex reads Sentl's run export; this has not been tested in Codex yet.

### claude.ai

1. Download `sentl-monitor.zip` from the latest release,
   https://github.com/GuidanceStudio/sentl-monitor/releases/latest/download/sentl-monitor.zip.
   Its sha256 is in `sentl-monitor.zip.sha256`, next to it. The link serves the latest
   release.
2. In Settings → Capabilities, turn on code execution.
3. In Customize → Skills, upload the zip.
4. In Settings → Connectors, add a custom connector with the URL
   `https://app.sentl.ai/mcp`, and sign in.

On Team and Enterprise plans, an owner can add the skill for the whole organization. A report on
claude.ai reads Sentl's run export, since a run's results do not fit in a conversation; this has
not been tested on claude.ai yet.

### ChatGPT

OpenAI documents standalone skills in the ChatGPT desktop app, the Codex CLI and the
IDE extension, and on the web only inside plugins. Whether the release zip uploads as a skill
on chatgpt.com is not confirmed. Sentl connects as a connector in developer mode, with the URL
`https://app.sentl.ai/mcp`. A report in ChatGPT reads Sentl's run export; this has not been tested
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

## A first deck, step by step

Avenello is a fictional oat-milk brand. Its marketing team has a Sentl project, *Avenello · US
market*, that asks three questions every day to two AI assistants, Acme Chat and Orbit Reason,
three times each:

- Nutrition: «How much sugar is in Avenello oat milk?»
- Choice: «What is the best oat milk to buy?», which names no brand, so it measures whether
  Avenello is named at all.
- Sustainability: «Is Avenello oat milk good for the environment?»

The project has run every day since 1 October 2026. On 14 October you write the deck of the
first week.

### 1. Adopt the project

In the assistant, opened in the folder where you keep client work, type:

```text
sentl-monitor adopt Avenello
```

The assistant lists your Sentl projects and picks the one whose name matches, asking you when
more than one does. It proposes the study folder `./avenello-study/`, checks it with
`monitor.py doctor`, and saves the project and its latest run into the folder's `inbox/`. Then it asks, in
one message, for what Sentl does not hold, proposing values from the project's rubrics where it
can. The answers appear in the deck as written, so you write them in the deck's language.
For Avenello:

| The assistant asks for | You answer |
|---|---|
| The research question, neutral: what is monitored, never one valence of it | What are people who ask an AI assistant about oat milk told about it and about Avenello? |
| The purpose: what the client will decide with the decks | Find the facts about Avenello that assistants state wrongly and the pages they take them from, to decide which pages to update. |
| Who asks the questions, and why | A generic consumer: the questions are the ones any shopper types; no persona changes them. |
| Who wrote the rubrics, and when | Avenello's marketing team, 15 September 2026 |
| The subject: its name as answers write it, and its own websites | Avenello; avenello.example |
| Foils: the competitors, as answers write them, and their websites | Avoria; avoria.example |
| Facts that carry a figure or a name, with the current and the outdated value as answers write them | On the sugar question: Avenello Original has 3 g of sugar per 100 ml since the March 2026 recipe, and had 5 g before; current «3 g», outdated «5 g»; source avenello.example/nutrition, read on 15 September 2026 |
| The market: country and language | United States, English |
| The deck's language: English or Italian | English |
| How long a period is: a week or a month | A week |
| Where each dimension's theme came from | Nutrition: customer-service questions about the new recipe. Choice: Google autocomplete, United States, September 2026. Sustainability: Avenello's 2025 sustainability report |

The assistant writes the answers into `avenello-study/study.json` and tells you the dimensions
and questions it adopted and how many completed runs the project has: 14, from 1 to 14 October.
The first period covers the last week, 8 to 14 October, and is compared with the week before,
rebuilt from the project's earlier runs. A first period is compared with up to four earlier weeks
or months. A first monthly period on a project younger than a month compares the second half of
the month with the first, once its runs span 14 days.

### 2. Build the period and write the deck

```text
sentl-monitor report
```

The assistant saves the project again, to find questions edited in the Sentl web panel since the
last period; when one was reworded, it asks you whether the question still asks the same thing.
It saves the results of the 14 runs into `inbox/` and runs the script on them, from the skill's
folder (here the one `install.sh --host claude` writes); `market` is the short name `adopt` gave
the project in the study folder:

```bash
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py runs --study avenello-study --project market --saved avenello-study/inbox/runs-701.json --date 2026-10-14
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py ingest --study avenello-study --project market --results avenello-study/inbox/run-9408.json
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py period --study avenello-study --date 2026-10-14 --models avenello-study/inbox/models.json
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py deck --study avenello-study --date 2026-10-14
# the assistant writes the findings and the actions in reports/2026-10-14.deck.json
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py check --study avenello-study avenello-study/reports/2026-10-14.deck.json
python3 ~/.claude/skills/sentl-monitor/scripts/monitor.py pdf --study avenello-study --date 2026-10-14
```

`runs` lists the runs to fetch, `ingest` stores each one, and `period` computes the figures of the
week and of the week before. `deck` places each question in a block and writes the figures file the
assistant reads; the assistant writes the text of the slides, from the answers and the figures, in
`reports/2026-10-14.deck.json`. `check` verifies it: every excerpt is verbatim, every figure is the
period's, every count beside a site or an assistant is that name's, every text fits its slide, and no
internal id appears. The assistant corrects the text until `check` passes, which records the period in
`history/reports.json`: the next period starts after its runs. `pdf` prints the deck; it needs
Chromium or Google Chrome with a working sandbox, and says what to install when none can start.

The first four slides are enough to decide: the cover says what was done and who prepared it, the second
what the deck shows, with real questions and how to read a figure, the third what was found, with the
subject beside the competitors the same answers name, and the fourth what to do and why. Then come the
evidence, each slide with the question it belongs to, the sources, the method and the list of every
question. The text is written for the client's marketing manager, in their words. Before an action names
a page, the assistant reads it with `monitor.py page --url <address>`, which prints what the page's HTML
holds, tooltips and closed answers included. Then a fresh reader who has seen nothing reads the deck, and
an audit checks every sentence against the answers; an audit run by another agent goes in
`history/deck/<date>.audit.md`, and the writer works from it.

What comes out:

```text
avenello-study/
  study.json              your answers, and the project's dimensions, questions and rubrics
  sentl.json              the Sentl project the study reads
  inbox/                  Sentl's responses, as the assistant saved them
  history/                the runs, the periods, the project's versions and the material each deck is written from
  reports/2026-10-14.deck.json   the deck's text
  reports/2026-10-14.deck.pdf    the deck
  reports/share/          the copy to send
```

The copy to send is `reports/share/Avenello + Sentl.ai - monitoring deck (2026-10-08 to 2026-10-14).pdf`:
the subject from `study.json`, the period from its entry in `history/reports.json`, in the study's `report_language`
(in Italian, `Avenello + Sentl.ai - deck di monitoraggio (dal 2026-10-08 al 2026-10-14).pdf`). In the chat, and never in the deck,
the assistant tells you the runs the period covers, the week rebuilt from earlier runs, and anything to check:
runs not final yet, runs left out, edits found in Sentl, and what the reader and the audit left open.

### 3. The next periods

A week later, `sentl-monitor report` again. It reads the runs started after the last run of the
previous period, compares the new week with up to four earlier ones, and the deck adds two slides
after what was found: each block's figure on both dates, and the earlier actions with their figure
then and now. The deck does not say an action moved a figure, because it does not know whether the
client acted.

## Make it yours

`monitor.py pdf` prints the deck white, with Sentl's orange, text colour and mark, and needs no
network. To use your own colours, font and logo, put a theme file where the skill looks for it; the
first hit wins:

1. `--theme <file>` on the command;
2. the `theme` key of the study's `study.json`, a path;
3. `theme.json` or `theme.css` in the study folder;
4. `theme.json` or `theme.css` in `~/.config/sentl-monitor/`;
5. Sentl's look.

A JSON theme names only what it changes; what it leaves out stays Sentl's. This one is for a fictional
brand:

```json
{
  "colors": {"primary": "#2255AA", "deep": "#112244", "text": "#1B1F2A"},
  "font": "Georgia, serif",
  "logo": "avenello-logo.png"
}
```

`colors` takes `primary` (the cover's band and the accents), `deep` (headings), `text`, `muted`, `line`
(borders) and `tint` (table headers). `logo` is a path (png, jpg, gif, webp or svg), relative
to the theme file, or the text of an SVG; a logo that cannot be read is replaced by Sentl's mark and
the command says so. `font_url` is optional: set it to a stylesheet address and the page links it,
which then needs the network when the deck is printed. A `.css` theme overrides the deck's variables
(`--sl-primary`, `--sl-deep`, `--sl-text`, `--sl-muted`, `--sl-line`, `--sl-tint`, `--sl-font`) and may
add rules; `.cover` and `.foot` are the cover and the footer of each slide. `check` lays the slides out
with the theme's rules, so a wider font can make a slide run over where Sentl's did not. The copy in
`reports/share/` is printed with the theme.

The skill writes its files (JSON, Markdown, PDF) in the study folder and sends none of them.
Putting a deck in a drive, a document library or a mailbox is done by the connectors your assistant
already has.

## Scheduled reports

Two clocks run independently. Sentl runs the measurement, on the project's schedule (daily,
weekly or monthly) once `setup` has activated it. A scheduler on your side starts the assistant
that builds the period and writes the deck. Started that way, `report` is unattended: it asks no
question and Sentl is only read.

- It lists each project's runs, and stops with `nothing_new` when no completed run is new since
  the previous period. A run still open is read at the next invocation.
- A run with under 90% of its answers judged is left out of the period; when no run is left it
  stops with `below_floor`. A dimension with under 80% of its answers judged is shown without a
  figure.
- The deck's text is written and checked as in an attended session. A deck that still fails
  `check` is recorded as a draft, with the problems found, and its period is recorded, so the next
  invocation does not write it again. Fix the text in `reports/<date>.deck.json` and run `check`
  on it to make it final.
- The fresh reader and the audit are left to you: run them before the deck is sent.
- `history/last-report.json` holds the time, the outcome (`written`, `draft`, `nothing_new` or
  `below_floor`) and a one-line detail of the latest invocation. Two invocations on the same
  runs write one deck, and the second records `nothing_new`.

Start it after the project's scheduled run has completed. The study folder must have been set
up by `adopt` or `setup`, with its `study.json` answered in full, because nobody can answer
a question at 07:00.

### A local scheduler

cron, launchd or a systemd timer starts a headless assistant in the study folder. The Sentl
connection uses an API token, because signing in through the browser needs a person, and a
sign-in unused for 30 days must be repeated. A token with the User role is enough, since
`report` only reads. Create it in Sentl under **Integrations → API Tokens**, then add the server to
Claude Code; the token is read from the terminal, stored in the assistant's own configuration and
never in the study folder:

```bash
read -rs SENTL_TOKEN
claude mcp add --scope user --transport http sentl-mcp https://app.sentl.ai/mcp --header "Authorization: Bearer $SENTL_TOKEN"
unset SENTL_TOKEN
```

The crontab line below starts `report` every Monday at 07:00. It allows the script, file edits
and the five Sentl tools `report` reads, so the unattended assistant cannot create a project,
change a setting or start a run:

```text
0 7 * * 1  cd <study folder> && claude -p "Run the sentl-monitor skill: report, unattended, for the study in this folder." --allowedTools "Bash(python3 *)" Read Write Edit mcp__sentl-mcp__list-organizations mcp__sentl-mcp__get-project-tool mcp__sentl-mcp__list-runs-tool mcp__sentl-mcp__get-run-results-tool mcp__sentl-mcp__list-ai-models >> <log file> 2>&1
```

The log file holds the assistant's closing message, which names the outcome. Read
`history/last-report.json` to see the outcome without the log. This recipe has not been run
on a schedule yet. Other assistants take the same prompt in their own headless mode; the skill needs the study folder as the working directory,
its Python and the Sentl tools.

### A cloud scheduled agent

An assistant's own scheduler, such as a scheduled cloud agent, starts every run in a fresh
environment, so the study folder must live somewhere that lasts: a **private** repository
holding the study folder. The decks and the saved answers are client data, so the repository
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
| 1 | `check` found problems in the deck, or `validate` in the study, listed one per line, `doctor` found that the study folder cannot be written, or `demand autocomplete` could not fetch some of Google's suggestions and lists the prefixes. | The assistant corrects the deck's text and runs `check` again until it passes. For `doctor`, choose another folder. For `demand autocomplete`, run it again: it fetches only the missing prefixes. |
| 2 | Input refused: a saved response is incomplete or belongs to another tool or project, a field of `study.json` is not filled in, a pack was changed, is older than the folder's last period or belongs to another study, or Python is older than 3.10. The message says why and what to do. | Follow the message: save the Sentl response again, answer the field it names, attach the latest pack, or install a newer Python. |
| 3 | A run is not final yet. | Nothing: the next period reads it. |
| 4 | No run of the period has 90% of its answers scored, or the period has no run. | Wait for the runs to complete, or check in the Sentl web panel why answers were not scored. |
| 5 | A Sentl response does not have the shape the skill reads, or a pack was written by a later version of the skill. The message names the tool and the field. | Do not edit the saved file. Update the skill; if the latest version still exits 5, open an issue naming the tool and the field. |
| 6 | Unexpected error. | Run the same command again with `--debug` and open an issue with its output. |
| 130 | Interrupted with Ctrl-C. | Run the command again. |

## Time zone, systems and languages

Periods are counted in UTC: a period dated D covers the runs started up to the end of D in UTC,
and its date is today's local date unless one is given.

Linux and macOS are supported, and Windows through WSL. On native Windows the script runs, but
the playbooks' commands assume a POSIX shell.

Decks are written in English or Italian. The questions can be in any language. Answers in
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

No route is planned. The routes above are all the skill has.

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

The repository is public: fixtures and docs use fictional subjects, and a change must
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
skills/sentl-monitor/  the skill
  SKILL.md             router
  LICENSE              copy of LICENSE, shipped in the zip
  agents/openai.yaml   Codex's display fields and the Sentl MCP dependency
  adopt/ADOPT.md       route playbooks, one per route
  brief/BRIEF.md
  design/DESIGN.md     how a study is designed; design/catalogue.md is the dimension catalogue
  setup/SETUP.md       how the study's projects are created and saved in Sentl
  report/REPORT.md     how the runs of a period are read and pooled
  report/DECK.md       how the deck of a period is written, checked and printed
  snapshot/SNAPSHOT.md how a one-off snapshot of a subject is designed and run, and its deck written
  compare/COMPARE.md   how two snapshots of one subject are set side by side
  scripts/monitor.py   the command line: adopt, detect, runs, pending, ingest, import, download, period, compare, check, demand, validate, review, revise, deck, pdf, page, payload, bind, resume, close, promote, doctor, pack, unpack
  scripts/sentlmon/    its implementation, standard library only
tests/                 bash suites, Python unit tests, opt-in live tests
```

Study folders hold client data and live outside this repository.

## Licence

MIT, see [LICENSE](LICENSE).
