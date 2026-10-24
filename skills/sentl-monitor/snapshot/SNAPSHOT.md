# snapshot

A one-off check of a subject, in a folder of its own: a small study of four or five dimensions, one
Sentl project, one run, one report, and no project left running in Sentl. It writes to the
operator's Sentl account and spends credits: every write has its own go.

`<skill>` below is this skill's directory, `$S` the snapshot's folder, `D` today's date
(`YYYY-MM-DD`) and `K` the project's key, `snapshot`. Run every `monitor.py` command with
`--study "$S"`. The fields are in ARCHITECTURE.md §`study.json`, §`sentl.json` and §`snapshot
<subject>`; the dimension catalogue is `<skill>/design/catalogue.md`.

**Every call to `create-project-tool`, `save-project-questions-tool` (a dry run included),
`update-project-settings-tool` and `trigger-run-tool` needs the operator's explicit go, each
time.** Show the call's arguments in full, in plain words next to the JSON, and wait. A go for one
call is not a go for the next, and a go given for another folder is not one. `monitor.py payload`
only prints the arguments; the assistant makes the call with exactly those arguments.

Every `monitor.py` command below can also end with exit 5 or 6. Exit 5: a saved response does
not have the shape the skill reads, and the message names the tool and the field; do not edit the
file, stop and tell the operator, since the skill needs an update. Exit 6: an unexpected error;
stop, give the operator the message, and run the command again with `--debug`.

**Sentl's errors.** Every error from Sentl reads "An internal server error occurred.", whatever
its cause. Call the tool once more. If it fails again, stop and say which tool failed and that
`snapshot` can be run again in the same folder: it resumes. After a failed write, call
`get-project-tool` before anything else, since the write may have been applied.

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

   It prints `Next step: design`, `project`, `cost`, `run`, `report`, `archive` or `done`, and
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

The output holds `create-project-tool` with the project's name, models and rounds, and neither
`is_active` nor a schedule, so the project is created paused. Show it and ask for the go; on the
go call it with exactly those arguments. Call `get-project-tool` on the id it returns, save the
response to `$S/inbox/created.json` and bind it:

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
the operator, in Sentl credits: the credits per researcher model, the credits for judging, the
total, the credits available in the organization, and whether the run can start. This tool reads
only and starts nothing. Then stop and ask for the go to start the run. When the estimate says
the run cannot start, say why (credits, subscription) and stop: the folder resumes here.

## 8. Run

Call `list-runs-tool` first. A run already open: follow it, start nothing, and tell the
operator. Otherwise, only on the operator's explicit go after the estimate, call
`trigger-run-tool` once, with the project id.

If it is refused because the project is paused, tell the operator, and ask for a new go to set
`is_active: true` with `update-project-settings-tool` for the length of the run. On that go,
activate the project, call `trigger-run-tool` once, pause the project with `is_active: false`
as soon as the run is open, and record in the chat that a paused project did not start a run.

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

## 10. Follow it, or archive it

Ask the operator: **follow this subject over time?** The run and its report are the baseline of
a study when the answer is yes, and then the project is kept, not archived. A no goes to the
archive below.

**Yes: promote.** Ask for what a monitored study needs and the snapshot did not: how often the
project runs (`daily`, `weekly` or `monthly`), how often a report covers (`weekly` or `monthly`),
the audience (`generic_consumer`, `personas`, `stakeholders` or `mixed`, with the reason), and
the question and the decision of the project. Save them as `$S/inbox/promote.json`:

```json
{"schedule": "weekly", "report_every": "monthly",
 "audience": {"choice": "generic_consumer", "reason": "..."},
 "project": {"question": "...", "decision": "..."}}
```

```bash
python3 <skill>/scripts/monitor.py promote --study "$S" --answers "$S/inbox/promote.json" --models "$S/inbox/models.json"
```

It writes `study.json` as a study (questions, rubrics and rounds unchanged, one theme per
dimension with the snapshot as its origin) and sends nothing. Then follow `setup/SETUP.md` from
the `payload` step: it saves the schedule, and activates the project only on the operator's go
after `estimate-run-tool`. The snapshot's report becomes the baseline: the next `report` compares
the first period with it. `promote` on a snapshot folder is also the answer when the operator
comes back later and asks to follow the subject, as long as the project is not closed.

**No: archive.** The Sentl MCP has no tool that archives or deletes a project. Pause it so that no scheduled run
can start and no further credits are spent. Call `get-project-tool`, saved to
`$S/inbox/project.json`. When it shows `is_active: true`, run the payload of step 6 with `--saved` and `--runs` and, on the
operator's go, call `update-project-settings-tool` with exactly the arguments it prints under
that name (`is_active: false`); call nothing else from its output. Then `get-project-tool`
again, saved, and:

```bash
python3 <skill>/scripts/monitor.py close --study "$S" --saved "$S/inbox/project.json"
```

Exit 2 saying the project is still active: pause it and save it again. It records `closed` with
`archive: operator` in `sentl.json`. Call `project-edit-link-tool` and give the operator the
project's page in the Sentl web panel, where they archive or delete it by hand. Deleting loses
nothing the report needs, because the run is saved in this folder.

On a host without a lasting folder, pack the snapshot before the conversation ends:
`monitor.py pack --study "$S" --out <the folder the host offers for download>`, and offer the
pack and the report for download (SKILL.md).

## 11. Tell the operator

In the chat: the report's path, the credits the estimate gave, the runs left out or unavailable,
the dimensions shown without a figure, unmatched responses, whether a paused project started the
run, and that the project is paused and waits for the operator to archive it.
