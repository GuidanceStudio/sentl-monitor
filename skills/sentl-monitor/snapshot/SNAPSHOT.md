# snapshot

A one-off check of a subject, in a folder of its own: a small study of four or five dimensions, one
snapshot in Sentl (it takes none of the plan's project slots), one run, one report, and nothing left
running in Sentl. It writes to the
operator's Sentl account and spends credits: every write has its own go.

`<skill>` below is this skill's directory, `$S` the snapshot's folder, `D` today's date
(`YYYY-MM-DD`) and `K` the project's key, `snapshot`. Run every `monitor.py` command with
`--study "$S"`. The fields are in ARCHITECTURE.md §`study.json`, §`sentl.json` and §`snapshot
<subject>`; the dimension catalogue is `<skill>/design/catalogue.md`.

**Every call to `create-snapshot-tool`, `save-project-questions-tool` (a dry run included),
`update-project-settings-tool`, `trigger-run-tool`, `delete-snapshot-tool` and `archive-project-tool` needs the operator's explicit go, each
time.** Show the call's arguments in full, in plain words next to the JSON, and wait. A go for one
call is not a go for the next, and a go given for another folder is not one. `monitor.py payload`
only prints the arguments; the assistant makes the call with exactly those arguments.

Every `monitor.py` command below can also end with exit 5 or 6. Exit 5: a saved response does
not have the shape the skill reads, and the message names the tool and the field; do not edit the
file, stop and tell the operator, since the skill needs an update. Exit 6: an unexpected error;
stop, give the operator the message, and run the command again with `--debug`.

**Sentl's errors.** Show the operator the error's code and message as Sentl gave them. Only
"An internal server error occurred." is called once more; if it fails again, stop and say which
tool failed and that `snapshot` can be run again in the same folder: it resumes. After a failed
write, call `get-project-tool` before anything else, since the write may have been applied.

## 1. Preflight and where to resume

```bash
python3 <skill>/scripts/monitor.py doctor --study "$S"
```

Exit 1: the folder cannot be written; choose another. On a web sandbox, unpack the pack first
(SKILL.md). Then:

1. `list-organizations`. No tool, or an authentication error: stop and give the operator the
   connection steps from https://app.sentl.ai/mcp/setup. The operator picks the organization;
   the role there must be Owner or Admin, otherwise stop and say so.
2. `get-organization-tool`: the credits available and the subscription. Note them for step 7;
   with an inactive subscription, go on to the design and tell the operator that no run can start
   until it is active.
3. `list-projects-tool`: tell the operator of any project already named after the subject. A
   snapshot creates its own project; it never takes over an existing one.
4. `list-ai-models`; save the response unchanged to `$S/inbox/models.json`. It holds each
   model's public name and its `credits`, the tariff per call.
5. Invoked again in a folder that already holds a snapshot, find the step to resume at. Without
   `$S/sentl.json`, or with a project that holds no question, run it without `--runs`; otherwise
   call `list-runs-tool` with the project id of `sentl.json` and save it to
   `$S/inbox/runs-<project id>.json`:

   ```bash
   python3 <skill>/scripts/monitor.py resume --study "$S" --runs "$S/inbox/runs-<project id>.json"
   ```

   It prints `Next step: design`, `project`, `cost`, `run`, `report`, `end` or `done`, and
   the step of this playbook that follows. Go to that step and skip the ones before it. A new
   folder is at `design`.

## 2. Subject and facts

Ask the operator what the reader of the report needs to decide, and the subject: its label,
kind (brand, product, category or organisation), aliases as people write it, the competitors
to name as foils, the sites the subject owns, and the market and language. Ask which language
the report is written in.

Collect 5 to 10 facts from primary sources: the subject's own pages, a regulator's or a
retailer's page. Each fact has its source and the date it was read. `catalogue.md` lists the
facts each dimension needs. A statement taken from an AI answer is not a fact.

## 3. Dimensions

Choose 4 or 5 entries of `catalogue.md` from what the reader needs to decide, by the
catalogue's rules (§Choosing for a snapshot): at least one dimension whose question names no
brand, unless the operator wants reputation only. A dimension whose facts cannot be found is
replaced by another entry. For each, write in `$S/study.json`:

- `catalogue`, the id of the entry; `axis`, `stance` or `fidelity`; `name`, as the reader would
  call it; `measures`, one sentence on what the dimension measures for this subject;
- an entry in `narrative.design_rationale` whose `choice` is the dimension's name and whose
  `reason` says why it was picked for this subject.

## 4. Questions and rubrics

One question per dimension, written as the person types it, in the market's language, from the
catalogue entry's pattern. A question that names no brand contains no alias of the subject or of
a foil, and has `branded: false`. Five anchors per question, adapted from the entry; the judge
instructions carry the dated facts. Write `study.json` with `"kind": "snapshot"`:

```json
{"schema": "sentl-monitor/study@1", "kind": "snapshot", "subject": {}, "foils": [],
 "market": {"country": "US", "language": "en"}, "report_language": "en",
 "organization": "<Sentl organization slug>", "themes": [],
 "narrative": {"research_question": "", "purpose": "", "criteria": {"by": "", "date": ""},
               "design_rationale": [{"choice": "<dimension name>", "reason": ""}]},
 "projects": [{"key": "snapshot", "name": "Snapshot · <subject> · <D>", "question": "", "decision": "",
               "models": ["<id from list-ai-models>"], "rounds": 1,
               "dimensions": [{"key": "", "catalogue": "", "name": "", "measures": "", "axis": "stance",
                               "questions": [{"key": "", "label": "", "text": "", "branded": true,
                                              "framing": "neutral", "rubric": {"1": "", "2": "", "3": "", "4": "", "5": ""},
                                              "instructions": "", "facts": []}]}]}]}
```

The project has no `schedule` and `rounds` is 1. `criteria.by` names who approved the rubrics,
the operator or their organisation. The operator chooses the researcher models from
`models.json`, with each model's tariff shown in Sentl credits.

## 5. Gate

```bash
python3 <skill>/scripts/monitor.py validate --study "$S" --models "$S/inbox/models.json"
python3 <skill>/scripts/monitor.py review --study "$S" --models "$S/inbox/models.json"
```

`validate` exit 1 lists the problems: correct `study.json` and run it again. It warns when every
dimension names the subject; tell the operator what that costs the report. `review` writes
`$S/study-review.md`: the narrative, the dimensions, every question with its rubric and judge
instructions, and the credits of one run from the tariffs, without judging. Show it and stop for
the operator's approval. Nothing is written to Sentl before it.

## 6. Project

Nothing here starts a run. First, the project:

```bash
python3 <skill>/scripts/monitor.py payload --study "$S" --project K --models "$S/inbox/models.json"
```

The output holds `create-snapshot-tool` with the snapshot's name and models. A snapshot has no
schedule, runs one round and takes none of the plan's project slots, so the plan's project limit
does not apply to it. Show it and ask for the go; on the go call it with exactly those arguments.
Call `get-project-tool` on the id it returns, save the response to `$S/inbox/created.json` and
bind it:

```bash
python3 <skill>/scripts/monitor.py bind --study "$S" --project K --saved "$S/inbox/created.json"
```

Call `get-project-tool` and an empty `list-runs-tool` again, saved to `$S/inbox/project.json`
and `$S/inbox/runs.json`, and run the payload for the questions:

```bash
python3 <skill>/scripts/monitor.py payload --study "$S" --project K --models "$S/inbox/models.json" \
  --saved "$S/inbox/project.json" --runs "$S/inbox/runs.json"
```

Its `save-project-questions-tool` holds the dimensions and questions; its notes are told to the
operator. Show the dimensions and ask for the go to call `save-project-questions-tool` with
`dry_run: true`; save the response to `$S/inbox/dry-run.json` and show what it lists. Every
question and dimension must appear as created. Ask for the go again, then call it without
`dry_run`, with no `delete_missing`. Then `get-project-tool`, saved to `$S/inbox/project.json`,
and bind again:

```bash
python3 <skill>/scripts/monitor.py bind --study "$S" --project K --saved "$S/inbox/project.json"
```

Exit 2 saying the save did not apply: save `get-project-tool` again and bind again; after a
second failure stop and show the operator what it lists.

## 7. Cost

Call `estimate-run-tool` for the project and save the response to `$S/inbox/estimate.json`. Show
the operator, in Sentl credits: the credits per researcher model, the
total, the credits available in the organization, and whether the run can start. This tool reads
only and starts nothing. Then stop and ask for the go to start the run. When the estimate says
the run cannot start, say why (credits, subscription) and stop: the folder resumes here.

## 8. Run

Call `list-runs-tool` first. A run already open: follow it, start nothing, and tell the
operator. Otherwise, only on the operator's explicit go after the estimate, call
`trigger-run-tool` once, with the project id.

If it is refused, tell the operator the code and message as Sentl gave them, and activate
nothing: a snapshot is not activated. A run that ends `stalled` (the queue did not pick it up) was
not charged: with the operator's go, call `trigger-run-tool` once more.

Follow the run with `list-runs-tool` until its status is `completed` or
`completed_with_warnings`, a few minutes apart. If the conversation ends first, the next
invocation resumes at this step and starts nothing. A status the skill has never seen is told to
the operator, who decides.

## 9. Report

Take the completed run's id from `resume`. Call `get-run-results-tool`, save the response to
`$S/inbox/run-<id>.json` (copy the host's file when the response was large) and ingest it:

```bash
python3 <skill>/scripts/monitor.py ingest --study "$S" --project K --results "$S/inbox/run-<id>.json"
python3 <skill>/scripts/monitor.py period --study "$S" --date D --models "$S/inbox/models.json"
python3 <skill>/scripts/monitor.py method --study "$S" --date D --models "$S/inbox/models.json"
```

If Sentl returns an error for the run twice, tell the operator and stop: a snapshot has one run
and no report without it; the folder resumes here. `period` reads the one run, with no
comparison and no floor on the judged share. A dimension with under 80% of its answers judged is
shown without a figure; tell the operator. `method` exit 2 listing fields: ask the operator and
run it again. It writes `reports/D.md` in this order: what we did, the dimensions, the
questions, how the answers are scored, the findings, and what a single run cannot show. Keep what
`period` printed for the chat; none of it goes in the report.

Write the findings as `report/REPORT.md` step 7 sets out, reading `history/material/D.md`, with
these differences: a dimension whose question names the subject is read by its score and its
figure; one whose question names no brand, by whether and where the subject appears (the share of
answers that name it and its position), and the answers of the assistants that do not name it
are described as such. Give no figure for the whole project, and write no summary and no changes
section. Every excerpt is copied verbatim. Never write a credit figure, an id, a key, a model id
or a file name.

```bash
python3 <skill>/scripts/monitor.py check --study "$S" "$S/reports/D.md"
```

Exit 1 lists each problem: fix the report and run it again until it passes. A passing report is
recorded in `history/reports.json` as final.

## 10. Keep it, delete it, or follow the subject

Ask the operator which of three. The run and its report stay in this folder whichever they choose.

**Keep it.** The snapshot stays in Sentl, readable, and costs nothing more. Call `get-project-tool`,
saved to `$S/inbox/project.json`, and:

```bash
python3 <skill>/scripts/monitor.py close --study "$S" --saved "$S/inbox/project.json"
```

**Delete it.** On the operator's go, call `delete-snapshot-tool`, then:

```bash
python3 <skill>/scripts/monitor.py close --study "$S" --deleted
```

**Follow the subject over time.** A snapshot takes no schedule, so following it means a project:
go on with `brief` and `design`, keeping this report as the first look. `promote` exists only for
a snapshot that was created as a project before Sentl had snapshots; for a snapshot it exits 2
and says so. When the project of such a snapshot is no longer needed, archive it with
`archive-project-tool` on the operator's go (`undo-project-archive-tool` reverts it in the first
ten minutes), then run `close` with `--saved` after reading it again.

On a host without a lasting folder, pack the snapshot before the conversation ends:
`monitor.py pack --study "$S" --out <the folder the host offers for download>`, and offer the
pack and the report for download (SKILL.md).

## 11. Tell the operator

In the chat: the report's path, the credits the estimate gave, the runs left out or unavailable,
the dimensions shown without a figure, unmatched responses, and what became of the snapshot
(kept, deleted, or followed by a study). Offer the report as a PDF: `monitor.py pdf --study "$S"`; what is sent is the file it names in `reports/share/`.
