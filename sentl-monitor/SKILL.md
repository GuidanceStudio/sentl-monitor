---
name: sentl-monitor
description: >-
  Monitor what AI assistants tell people about a subject — a brand, a product category, a
  production method or an organisation — with Sentl, through Sentl's MCP server. Routes:
  `adopt <project>` (take a project that already exists in Sentl into a study folder) and
  `report` (pool the runs since the previous report and write a dated Markdown report that
  compares them with the earlier periods: what the assistants say, dimension by dimension,
  with verbatim answers and cited sources; the first report opens with the method, later
  ones with what changed).
  Use for AI visibility, GEO or AEO monitoring, LLM reputation reports, or any report on a
  Sentl project's runs.
compatibility: >-
  Requires python3 3.10+ (standard library only) and the Sentl MCP server connected to the
  assistant (https://app.sentl.ai/mcp/setup). The skill makes no model calls and stores no
  token. Writes to Sentl need the Owner or Admin role and the operator's approval each time;
  the adopt and report routes only read. Assistant-neutral.
---

# sentl-monitor

A Sentl project asks its questions to several researcher models; a judge scores each answer
from 1 to 5 against a rubric written for that question. This skill keeps a **study folder**
per monitored subject, reads the project's runs into it, and writes reports a client can
read without having seen an earlier one.

## Routes

| Invocation | Playbook | What it does |
|---|---|---|
| `adopt <project>` | `adopt/ADOPT.md` | takes an existing Sentl project into a study folder and asks the operator what Sentl does not hold |
| `report` | `report/REPORT.md` | pools the completed runs since the previous report, compares them with the earlier periods, and writes `reports/<date>.md` |

Read the playbook of the route invoked and follow it step by step. `brief`, `design`, `setup`
and `snapshot` are planned and not available yet: say so if one is invoked.

## Rules for every route

- **Sentl's tools.** Their names depend on the name the server was given in the host (for
  example `mcp__sentinel-reputation__get-project-tool`). Find them by their suffix:
  `list-organizations`, `list-projects-tool`, `get-project-tool`, `list-runs-tool`,
  `get-run-results-tool`, `list-ai-models`. When none is available, stop and give the
  operator the connection steps from https://app.sentl.ai/mcp/setup.
- **Writes need the operator's approval, each time.** `create-project-tool`,
  `save-project-questions-tool`, `update-project-settings-tool` and `trigger-run-tool` change
  the account or spend credits; `adopt` and `report` never call them.
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
  (`--help` lists the commands). Exit codes: 0 done; 1 `check` found problems; 2 input refused
  (the message says why and what to do); 3 run not final yet; 4 no run left in the period;
  5 a Sentl response does not have the shape the skill reads (the message names the tool and the
  field): Sentl changed what it returns, so stop, do not edit the saved file, and tell the
  operator the tool and the field, since the skill needs an update; 6 unexpected error: stop, give
  the operator the one-line message, and run the same command again with `--debug` to show where
  it failed. A file holding another tool's response, or no readable file, is exit 2: save the
  right response to it.
- **Sentl's errors.** Every error from Sentl reads "An internal server error occurred.", whatever
  its cause. Call the tool once more. If it fails again, `get-run-results-tool` records the run as
  unavailable and the route goes on without it (the playbooks say how); any other tool stops the
  route: tell the operator which tool failed and that the route can be run again later.
- **What the operator is told goes in the chat, never in the report:** runs covered and left
  out, unmatched responses, unavailable runs, a run score that differs from the one computed,
  dimensions shown without a figure, edits detected in Sentl, the periods rebuilt from a
  project's earlier runs, the two halves of a first period compared with each other, or that
  no earlier period exists.
- Talk to the operator in their language. The report is written in the study's
  `report_language`.
