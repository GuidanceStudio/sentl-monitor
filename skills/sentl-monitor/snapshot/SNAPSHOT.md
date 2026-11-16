# snapshot

A one-off check of a subject, in a folder of its own: a study designed by the rule of DESIGN.md
steps 2 to 9, run as snapshots in Sentl (they take none of the plan's project slots), one deck,
and nothing left running in Sentl. It writes to the
operator's Sentl account and spends credits: every write has its own go.

`<skill>` below is this skill's directory, `$S` the snapshot's folder, `D` today's date
(`YYYY-MM-DD`) and `K` a snapshot's key in `study.json`. Run every `monitor.py` command with
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
`internal` is called once more; if it fails again, stop and say which tool failed and that
`snapshot` can be run again in the same folder: it resumes. `not_found`: stop and name the id.
`invalid_argument`: stop, the skill needs an update. After a failed write, call `get-project-tool`
before anything else, since the write may have been applied.

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
   `$S/sentl.json`, or with a snapshot that holds no question, run it without `--runs`; otherwise
   call `list-runs-tool` with the project id of each snapshot of `sentl.json` not closed and save
   each response to `$S/inbox/runs-<project id>.json`:

   ```bash
   python3 <skill>/scripts/monitor.py resume --study "$S" \
     --runs "$S/inbox/runs-<project id>.json" "$S/inbox/runs-<project id>.json"
   ```

   It prints `Next step: design`, `project`, `cost`, `run`, `deck`, `end` or `done`, the
   snapshot and the runs it concerns, and the step of this playbook that follows. Go to that step
   and skip the ones before it. A new folder is at `design`.

## 2. Brief

Follow BRIEF.md in `$S` with what the prospect gives, with these differences:

- BRIEF.md step 2 is skipped when there is no client material.
- The themes come from the operator's remarks (origin `client_issue`), from the search
  suggestions (`search`) and from a probe (`probe`, BRIEF.md step 2).
- The personas are written as a list in `seeds.json`, as for a study, and the seeds are the
  brief's, per theme and per persona.
- Volumes are fetched only when a keyword-data tool is connected, and after the operator's yes
  (BRIEF.md step 4).

Ask the operator two more things: who will read the deck, their role and the decision the deck
feeds, and which language the deck is written in. BRIEF.md step 7 stops for the operator's
review of `brief.md`; then go on with step 3.

## 3. Design

Follow DESIGN.md steps 2 to 9 with `$S/brief.md` and `$S/search-demand.json`: the themes,
dimensions, projects, personas and models of a snapshot come out of the same rule as a study's.
Only these differ:

- `study.json` has `"kind": "snapshot"`, no `report_every`, and no `schedule` on its projects.
- Each project becomes one snapshot in Sentl. Its `rounds` is 3 by default, as for a project.
  Name it `Snapshot · <subject> · <project> · <D>`.
- `narrative.reader` names who will read the deck and the decision it feeds.

```json
{"schema": "sentl-monitor/study@1", "kind": "snapshot", "organization": "<Sentl organization slug>",
 "narrative": {"reader": "<role, and the decision the deck feeds>"},
 "projects": [{"key": "<key>", "name": "Snapshot · <subject> · <project> · <D>", "rounds": 3}]}
```

The fragment shows only what differs; every other field is the study's (ARCHITECTURE.md
§`study.json`).

## 4. Validate and review

```bash
python3 <skill>/scripts/monitor.py validate --study "$S" --models "$S/inbox/models.json"
python3 <skill>/scripts/monitor.py review --study "$S" --models "$S/inbox/models.json" \
  --credits-available <the credits available, from step 1>
```

`validate` runs the study's checks, plus the absence of a schedule and of a report cadence; exit
1 lists the problems: correct `study.json` and run it again. Tell the operator each warning, as
DESIGN.md step 10 says. `review` writes `$S/study-review.md`: the narrative, the themes, the
personas, each snapshot with its dimensions and its models, every question with its rubric and
judge instructions, and the credits from the tariffs: each snapshot's run at its rounds and
at 1 round, and the total, against the credits available (DESIGN.md step 11).

## 5. Budget and approval

When the operator sets a budget below the design's cost, propose which snapshots or dimensions
to leave out to fit it; the operator chooses. Tell what is left out in the chat, record it in
`narrative.design_rationale` with its reason, and run step 4 again. Show the review and stop for
the operator's approval. Nothing is written to Sentl before it.

## 6. Snapshots

Steps 6 to 8 are done for each snapshot of `study.json`, in its order: create and bind every
snapshot first, then run them one after the other, each after its own estimate and go. Nothing
here starts a run. First, the snapshot:

```bash
python3 <skill>/scripts/monitor.py payload --study "$S" --project K --models "$S/inbox/models.json"
```

The output holds `create-snapshot-tool` with the snapshot's name, its models and, above one round,
its `rounds`. A snapshot has no schedule and takes none of the plan's project slots, so the plan's
project limit does not apply to it. Show it and ask for the go; on the go call it with exactly those
arguments. A Sentl that does not take rounds on a snapshot yet refuses them, at creation or in the
`update-project-settings-tool` call the next payload holds: stop, and give the operator Sentl's
code and message. There is no fallback to several runs.
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

`resume` names the snapshot whose run comes next. Before each snapshot's run, call `estimate-run-tool` for that snapshot and save the response to
`$S/inbox/estimate-<key>.json`. Show the operator, in Sentl credits: the credits per researcher
model, the total, the credits available in the organization, and whether the run can start. This tool reads
only and starts nothing. Then stop and ask for the go to start the run. When the estimate says
the run cannot start, say why (credits, subscription) and stop: the folder resumes here.

## 8. Run

Call `list-runs-tool` first. A run already open, of this snapshot or another: follow it, start
nothing, and tell the operator. Otherwise, only on the operator's explicit go after the estimate,
call `trigger-run-tool` once, with the snapshot's project id.
Every start of a snapshot run sends `confirm: true`, which Sentl requires on a snapshot, and only
after the operator's yes on that run's estimate. This holds for a run started again after a stall
or by hand. Once its run is final, `resume` moves to the next snapshot's step 7. The operator may run a snapshot again by hand, for instance
one of 1 round three times: every completed run of every snapshot goes in the period.

If it is refused, tell the operator the code and message as Sentl gave them, and activate
nothing: a snapshot is not activated. A run that ends `stalled` (the queue did not pick it up) was
not charged: with the operator's go, call `trigger-run-tool` once more. A run that ends `failed`
holds no results: tell the operator Sentl's error, and start another only on a new go.

Follow the run with `list-runs-tool`, a few minutes apart, through `queued`, `pending`,
`researching`, `running` and `judging`, until its status is `completed` or
`completed_with_warnings`. If the conversation ends first, the next invocation resumes at this
step and starts nothing. A status the skill has never seen is told to the operator, who decides.

## 9. Period and deck

Take the completed runs not yet ingested, and their snapshots, from `resume`. For each, call
`get-run-results-tool`, save the response to `$S/inbox/run-<id>.json` (copy the host's file when
the response was large) and ingest it with its snapshot's key; then build the period:

```bash
python3 <skill>/scripts/monitor.py ingest --study "$S" --project K --results "$S/inbox/run-<id>.json"
python3 <skill>/scripts/monitor.py period --study "$S" --date D --models "$S/inbox/models.json"
```

If Sentl returns an error for a run twice, tell the operator and stop: the deck waits for it, and
the folder resumes here. `period` pools every ingested run of every snapshot into one period, with
no comparison and no floor on the judged share, and one deck is drawn from it. A dimension with under 80% of its answers judged is shown
without a figure; tell the operator. A snapshot of `study.json` never created or never run is left out
of the period and the deck, and `period` names it; tell the operator. A run ingested after the deck passed, such as a snapshot run again by
hand, brings `resume` back to this step: build the period again with today's `D` and write its deck,
which replaces the earlier one. Until then `promote` refuses that run. Keep what `period` printed for the chat; none of it goes in
the deck.

Ask the operator which deck the reader of step 2 receives: the deck, with what was found and
three to five actions (`report/DECK.md`), or the quick deck, with each topic's figure, one
sentence and one passage of an answer, and no actions (`report/QUICK.md`). Then follow the one
chosen from its step 1 with the same `D`: the deck is what the reader of
step 2 receives. `deck` exit 2 listing fields: ask the operator and run it again. The deck's
`check` records the period in `history/reports.json` as final; `pdf` writes the copy to
send in `reports/share/`. Never write a credit figure, an id, a key, a model id or a file name in
the deck. On a host without a lasting folder, the pack waits for step 10, after the operator's choice.

## 10. Keep it, delete it, or follow the subject

Ask the operator which of three, for each snapshot. The runs, the period and the deck stay in this
folder whichever they choose. `--project K` names the snapshot; it may be left out when the folder
holds one.

**Keep it.** The snapshot stays in Sentl, readable, and costs nothing more. Call `get-project-tool`,
saved to `$S/inbox/project.json`, and:

```bash
python3 <skill>/scripts/monitor.py close --study "$S" --project K --saved "$S/inbox/project.json"
```

**Delete it.** On the operator's go, call `delete-snapshot-tool`, then:

```bash
python3 <skill>/scripts/monitor.py close --study "$S" --project K --deleted
```

**Follow the subject over time.** The snapshot's `study.json` becomes the study, with a schedule,
rounds and a report cadence added; nothing else changes. A snapshot takes no schedule, so each one
is followed by a project of the same design, and the period and deck of this folder are the first
look the first report compares with. Keep or delete each snapshot first, as above. Then ask the
operator for the schedule (`daily`, `weekly` or `monthly`, one for every project or one per project
key), the rounds when they differ from the snapshot's, and the report cadence (`weekly` or
`monthly`); save them to `$S/inbox/follow.json`, as
`{"schedule": "weekly", "rounds": 3, "report_every": "monthly"}`, and run:

```bash
python3 <skill>/scripts/monitor.py promote --study "$S" --answers "$S/inbox/follow.json" \
  --models "$S/inbox/models.json"
```

It writes `study.json` as a study, drops `Snapshot` and the date from each project's name, and
keeps each snapshot's binding under `snapshots` in `sentl.json`; it sends nothing. Exit 2 names
what is missing. Then follow `setup/SETUP.md` from its step 4 for each project, on the operator's
go for each write: `payload` creates the project, and each question kept as it was stays
comparable with the snapshot's answers.

A snapshot of the earlier shape, with no themes in `study.json`, is not followed this way: design a
study for the subject (`brief`, `design`) and keep this folder's deck as the first look. Such a
snapshot created as a project before Sentl had snapshots keeps its project instead: `promote` with
the answers ARCHITECTURE.md §`snapshot <subject>` lists schedules it. When the project of such a snapshot is no
longer needed, archive it with `archive-project-tool` on the operator's go
(`undo-project-archive-tool` reverts it in the first ten minutes), then run `close` with `--saved`
after reading it again.

On a host without a lasting folder, pack the snapshot before the conversation ends:
`monitor.py pack --study "$S" --out <the folder the host offers for download>`, and offer the
pack and the deck's copy to send, in `reports/share/`, for download (SKILL.md).

## 11. Tell the operator

In the chat: where the deck's copy to send is (the file `pdf` names in `reports/share/`),
the credits the estimate gave, the runs left out or unavailable, the dimensions shown without a
figure, unmatched responses, what DECK.md step 9 lists, and what became of the snapshot (kept,
deleted, or followed by a study).
