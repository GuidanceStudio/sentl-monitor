---
name: sentl-monitor
description: >-
  Reports what AI assistants say about a brand or topic from a Sentl project's runs, compared
  with earlier periods. Use for AI visibility, GEO/AEO monitoring and LLM reputation reports.
license: MIT
compatibility: >-
  Python 3.10+ (standard library only) and Sentl's MCP server connected to the assistant
  (https://app.sentl.ai/mcp/setup). Tested in Claude Code, which keeps the study folder on
  disk. opencode and Codex install it; not tested there yet. claude.ai and ChatGPT need code
  execution; there a study travels between conversations as a pack file the user keeps, and
  reports on those hosts read Sentl's run export. Makes no model calls and stores no token.
metadata:
  version: "0.1.0"
  homepage: https://github.com/GuidanceStudio/sentl-monitor
---

# sentl-monitor

A Sentl project asks its questions to several researcher models; a judge scores each answer
from 1 to 5 against a rubric written for that question. This skill keeps a **study folder**
per monitored subject, reads the project's runs into it, and writes reports a client can
read without having seen an earlier one.

## When to use

Use it when someone asks what AI assistants tell people about a brand, a product category, a
production method or an organisation, and the answers are measured in Sentl.

| You want | Route |
|---|---|
| A first look at a brand or topic, once, leaving nothing running | `snapshot <subject>` |
| To follow a subject over time and receive a report each period | `brief`, `design`, then `setup`; the report is `report` |
| A report on a Sentl project that already exists | `adopt <project>`, then `report` |
| This period's report, or what changed since the last | `report` in the study's folder |
| A report as a PDF | `pdf` after the report passes `check` |
| To change the questions, models or schedule of a monitored study | edit `study.json` through `design`, then `setup` |
| To stop a project | `setup` step 8: archive it, on your go |

The assistant reads the Sentl tools' own descriptions for their parameters, roles and limits; this
skill does not repeat them. It tells you which route to take, in which order, what needs your go,
and how the figures in the report are built.

Choose the route by the state of the study:

- No study folder holds the Sentl project yet: `sentl-monitor adopt <project>`.
- The study folder exists and runs have completed after its last report: `sentl-monitor report`.
- A scheduler starts the assistant and nobody can answer a question: `sentl-monitor report`
  unattended, which follows the last section of `report/REPORT.md`.
- The operator is starting a study and has no Sentl project yet: `sentl-monitor brief <subject>`, then `sentl-monitor design` once `brief.md` is approved.
- The study is designed and approved and its projects are not in Sentl yet, or `study.json` changed since they were saved: `sentl-monitor setup`.
- Someone wants a first look at a subject, with no study to keep: `sentl-monitor snapshot <subject>`, in a folder of its own. To follow the subject afterwards, `brief` and `design` start from the snapshot's report as the first look.
- Someone asks what changed between two moments: `sentl-monitor report` in the study's folder; it compares each period with the one before.

## Routes

| Invocation | Playbook | What it does |
|---|---|---|
| `adopt <project>` | `adopt/ADOPT.md` | takes an existing Sentl project into a study folder and asks the operator what Sentl does not hold |
| `report` | `report/REPORT.md` | pools the completed runs since the previous report, compares them with the earlier periods, and writes `reports/<date>.md`; started by a scheduler, it records its outcome in `history/last-report.json` |
| `brief <subject>` | `brief/BRIEF.md` | lists the themes to monitor with the origin of each, collects Google suggestions and search volumes, and writes `brief.md` and `search-demand.json` |
| `design` | `design/DESIGN.md` | turns the approved themes into dimensions, projects, questions with rubrics and a narrative, validates them against Sentl's limits and writes `study.json` and `study-review.md` for the operator's approval |
| `setup` | `setup/SETUP.md` | creates the study's projects in Sentl, or saves their changed questions without losing the results linked to them, records the ids in `sentl.json`, shows Sentl's credit estimate, and starts a run or a schedule only on the operator's go |
| `snapshot <subject>` | `snapshot/SNAPSHOT.md` | runs a small study of the subject on Sentl once, as a snapshot in Sentl that takes no project slot: 4 or 5 dimensions from the catalogue, one run on the operator's go after the credit estimate, a short report, then the operator chooses to keep the snapshot, delete it, or follow the subject; invoked again in the same folder, it resumes |

Read the playbook of the route invoked and follow it step by step.

## Rules for every route

- **Sentl's tools.** Their names depend on the name the server was given in the host; find them
  by their suffix and read each tool's description from the server when you call it. When none
  is available, stop and give the operator the connection steps from
  https://app.sentl.ai/mcp/setup.
- **A keyword-data server's tools.** `brief` looks in the connected servers for a tool that returns
  monthly search volume and related searches. Read the tool's name and parameters from the server
  when the step runs; never assume them. A call counts against the server's quota: name the tool
  to the operator and call it only after a yes.
- **Writes to Sentl need the operator's approval, each time.** Creating, changing, archiving,
  restoring or deleting a project or snapshot, saving questions and starting a run change the
  account or spend credits. `adopt` and `report` never do any of them; `setup` and `snapshot` do,
  each call after its own explicit go (a dry run included), and a run or the activation of a
  schedule only after `estimate-run-tool` has been shown. `monitor.py payload` builds a write's
  arguments and calls nothing.
- **Saving a response into `inbox/`.** The script reads Sentl's responses from files and never
  calls Sentl. When the host saved a large response to a file and says where, copy that file
  with `cp`; a host may word this as an error ("result exceeds maximum allowed tokens. Output
  has been saved to ..."): it is not one, and the call is not repeated. When the response
  arrived in the conversation, write it to the file exactly as returned: every character, no
  reformatting, no translation, no summary. `monitor.py` refuses a file that is not complete
  JSON and a project that does not hold the texts its latest run asked.
- **Never write** a token, an organization name or any account data into the skill's own
  directory. Study folders live where the operator keeps client work.
- **The script.** `python3 <skill dir>/scripts/monitor.py <command> --study <folder> ...`
  (`--help` lists the commands, `--version` prints the skill's version). Run
  `monitor.py doctor --study <folder>` first in every conversation: it reports the Python
  version, whether the folder is writable, and whether it lies in a web sandbox whose files are
  deleted when the conversation ends. Exit codes: 0 done; 1 `check`, `validate` or `doctor` found
  problems, or `demand autocomplete` could not fetch every prefix (run it again); 2 input refused
  (the message says why and what to do); 3 run not final yet; 4 no run left in the period;
  5 a Sentl response or an export does not have the shape the skill reads (the message names the tool and the
  field): Sentl changed what it returns, so stop, do not edit the saved file, and tell the
  operator the tool and the field, since the skill needs an update; a pack's manifest written by
  a later version of the skill is exit 5 too; 7 a download link that does not answer or has
  expired (export again for a new link, or ask the user to download the file and attach it);
  6 unexpected error: stop, give
  the operator the one-line message, and run the same command again with `--debug` to show where
  it failed. A file holding another tool's response, or no readable file, is exit 2: save the
  right response to it.
- **Hosts without a lasting folder.** When `monitor.py doctor` reports a web sandbox (claude.ai,
  ChatGPT), the study folder is deleted when the conversation ends, so the study travels as a
  pack, one zip file. Before any other command, run `monitor.py unpack --study <folder> <pack>`
  on the pack the user attached or the one kept in the Project's files; with several packs,
  unpack the one with the latest date in its name. When the route ends (after `check` in
  `report`, after the operator's answers in `adopt`, after `close` in `snapshot`), run `monitor.py pack --study <folder>
  --out <folder the host offers for download>`, copy the report and the PDF in `reports/share/`, if one was made, to
  the same folder, and offer them for download. Tell the user to keep the report and the new
  pack and, when the host has Projects, to put the pack in the Project's files in place of the
  previous one: the next conversation reads it from there. The playbooks say where.
- **Runs too large for the conversation.** When the host does not save a large tool result to a
  file, read the runs through Sentl's export: `export-runs-tool` for the project and the runs to
  fetch, then `monitor.py download --url <download.url> --sha256 <download.sha256>` when the
  host can reach the link, or ask the user to download the link in the browser and attach the
  file, then `monitor.py import --sha256 <download.sha256> <file>`. `import` writes the project,
  the run listing and every run into `inbox/`; `ingest` then reads them as usual. The link lasts
  60 minutes and `download` sends no credential and fetches only from Sentl's own hosts.
- **Sentl's errors.** An error carries a code and a message. Tell the operator both as Sentl gave
  them. Only "An internal server error occurred." is called once more; if it fails again,
  `get-run-results-tool` records the run as unavailable and the route goes on without it (the
  playbooks say how); any other tool stops the route: say which tool failed and that the route can
  be run again later.
- **What the operator is told goes in the chat, never in the report:** runs covered and left
  out, unmatched responses, unavailable runs, a run score that differs from the one computed,
  dimensions shown without a figure, edits detected in Sentl, the periods rebuilt from a
  project's earlier runs, the two halves of a first period compared with each other, or that
  no earlier period exists.
- Talk to the operator in their language. The report is written in the study's
  `report_language`.
