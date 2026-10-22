# setup

Creates the Sentl projects of an approved study, or brings the projects it already has in line
with `study.json`, and records their ids in `sentl.json`. It writes to the operator's Sentl
account and can spend credits: every write has its own go.

`<skill>` below is this skill's directory; `$S` is the study folder, and `<key>` a project's key
in `study.json`. The fields are in ARCHITECTURE.md §`study.json`, §`sentl.json` and §`setup`.

**Every call to `create-project-tool`, `update-project-settings-tool`,
`save-project-questions-tool` (a dry run included) and `trigger-run-tool` needs the operator's
explicit go, each time.** Show the call's arguments in full, in plain words next to the JSON,
and wait. A go for one call is not a go for the next, and a go given earlier in the conversation
for another study or another project is not one. `monitor.py payload` only prints the arguments;
the assistant makes the call, with exactly those arguments.

Every `monitor.py` command below can also end with exit 5 or 6. Exit 5: a saved response does
not have the shape the skill reads, and the message names the tool and the field; do not edit
the file, stop and tell the operator, since the skill needs an update. Exit 6: an unexpected
error; stop, give the operator the message, and run the command again with `--debug`.

**Sentl's errors.** Every error from Sentl reads "An internal server error occurred.", whatever
its cause. Call the tool once more. If it fails again, on `get-run-results-tool` record the run
as unavailable (step 3); on any other tool stop, say which tool failed and that `setup` can be
run again later. After a failed write, call `get-project-tool` before anything else: the write
may have been applied.

## 1. Preflight

```bash
python3 <skill>/scripts/monitor.py doctor --study "$S"
```

Exit 1: the folder cannot be written. On a web sandbox, unpack the pack first (SKILL.md).
Without `$S/study.json`, run `design` first. Then:

1. `list-organizations`. No tool, or an authentication error: stop and give the operator the
   connection steps from https://app.sentl.ai/mcp/setup. Find the organization whose slug is
   `organization` in `study.json`. The role there must be Owner or Admin: with the User role,
   stop and say that `setup` needs Owner or Admin.
2. `get-organization-tool`: the credits available and the subscription. Note them for step 6;
   with an inactive subscription, go on with the projects and tell the operator that no run can
   start until it is active.
3. `list-ai-models`; save the response unchanged to `$S/inbox/models.json`.
4. Check the study against Sentl's limits and today's models:

   ```bash
   python3 <skill>/scripts/monitor.py validate --study "$S" --models "$S/inbox/models.json"
   ```

   Exit 1 lists the problems, among them a model Sentl no longer offers. Stop: the design is
   corrected and approved again (`design`). Show the operator `study-review.md` if they have not
   seen the version being set up.

## 2. Plan

For each project of `study.json`, say whether `sentl.json` binds it to a Sentl project. A project
that is not bound is created; a bound one is brought in line. Tell the operator the list, the
organization, and that nothing is written until each step has their go. Handle the projects one
at a time, in the order of `study.json`.

## 3. A project that exists: read it and ingest what is pending

Skip this step for a project that is not bound yet.

1. `get-project-tool` with the project id from `sentl.json`; save it to
   `$S/inbox/project-<key>.json`.
2. `list-runs-tool` with the same id; save it to `$S/inbox/runs-<key>.json`.
3. Ingest every completed run not yet in `$S/history/runs/<key>/`, before any save, because a
   run is matched to the questions in force when it started and a save changes them. Run the
   payload (step 5); when completed runs are pending it exits 2 and names them. For each, call
   `get-run-results-tool`, save the response to `$S/inbox/run-<id>.json` (copy the file the host
   wrote when the response was large; on a host that cannot, read the runs through the export,
   SKILL.md) and run:

   ```bash
   python3 <skill>/scripts/monitor.py ingest --study "$S" --project <key> --results "$S/inbox/run-<id>.json"
   ```

   If Sentl returns an error for that run twice, record it and go on; an unavailable run blocks
   no save:

   ```bash
   python3 <skill>/scripts/monitor.py ingest --study "$S" --project <key> --unavailable <id> --reason "server error"
   ```

   Exit 3: the run is not final yet; leave it. A run still open when the save would happen is
   named in the payload's notes: tell the operator, and ask whether to wait for it.
4. Record what changed in Sentl's web panel since the last version:

   ```bash
   python3 <skill>/scripts/monitor.py detect --study "$S" --project <key> --saved "$S/inbox/project-<key>.json"
   ```

   Tell the operator each change it lists. A save would overwrite those edits with
   `study.json`: ask whether the study or the panel holds, and correct `study.json` first when
   the panel does.

## 4. A project that does not exist: create it

```bash
python3 <skill>/scripts/monitor.py payload --study "$S" --project <key> --models "$S/inbox/models.json"
```

The output holds `create-project-tool` with its arguments. Show them and ask for the go. On the
go, call `create-project-tool` with exactly those arguments: the project is created paused, with
no question and no run. Then `get-project-tool` on the id it returns; save the response to
`$S/inbox/created-<key>.json` and bind it:

```bash
python3 <skill>/scripts/monitor.py bind --study "$S" --project <key> --saved "$S/inbox/created-<key>.json"
```

Then save `get-project-tool` and an empty `list-runs-tool` as in step 3, items 1 and 2, and go
on with step 5.

## 5. Settings and questions

```bash
python3 <skill>/scripts/monitor.py payload --study "$S" --project <key> --models "$S/inbox/models.json" \
  --saved "$S/inbox/project-<key>.json" --runs "$S/inbox/runs-<key>.json"
```

- Exit 2 naming completed runs: ingest them (step 3, item 3) and run the payload again.
- Exit 2 saying the project differs from its latest version: run `detect` (step 3, item 4).

The output holds `update-project-settings-tool` when the name, models, rounds or schedule differ
from Sentl, `save-project-questions-tool` with every dimension and question and every id from
`sentl.json`, and `notes`. Tell the operator each note.

1. **Settings.** When `update-project-settings-tool` is there, show what it changes and ask for
   the go; then call it with exactly its arguments. It never sets `is_active`.
2. **Dry run.** Show the questions to be created, changed and archived, then ask for the go to
   call `save-project-questions-tool` with its arguments and `dry_run: true`. Save the response
   to `$S/inbox/dry-run-<key>.json` and show the operator what it lists as created, updated,
   archived, restored and deleted. A reworded question must appear as updated, not as created and
   deleted: if it does not, stop and tell the operator.
3. **Deletions.** The payload never carries `delete_missing`. When the dry run lists something
   to delete (a question left out of `study.json`, since a question cannot be archived), the real
   save is refused by Sentl and saves nothing. Past results lose their link to a deleted
   question. Read the list to the operator. Only when they approve those deletions, add
   `delete_missing: true` to the real call. Otherwise put the question back into `study.json`
   (`design`, then `revise`) and run the payload again. A dimension to drop is archived by the
   payload, not deleted.
4. **Save.** Ask for the go again, then call `save-project-questions-tool` with the payload's
   arguments (and `delete_missing: true` only as step 3 says), without `dry_run`.
5. **Bind.** `get-project-tool`; save the response to `$S/inbox/project-<key>.json`, then:

   ```bash
   python3 <skill>/scripts/monitor.py bind --study "$S" --project <key> --saved "$S/inbox/project-<key>.json" \
     --run "$S/inbox/run-<latest id>.json"
   ```

   Leave `--run` out when the project has no run. It writes the ids to `$S/sentl.json` and a
   `setup` version to `$S/history/versions/`, and refuses a saved project that lacks a text the
   latest run asked. Exit 2 saying the save did not apply, or a text is missing: save
   `get-project-tool` again (copy the host's file if there is one) and run `bind` again; after a
   second failure stop and show the operator what it lists. Tell the operator each note.

## 6. Estimate

When every project is set up, call `estimate-run-tool` for each: credits per model, judging
credits, credits available, and whether the run can start. Show them in credits. This tool
reads only and starts nothing.

## 7. First run and schedule, only on a go

Ask separately, for each project, whether to start a first run and whether to activate its
schedule, naming the estimate and the schedule (`daily`, `weekly` or `monthly`). A project
stays paused until the operator says otherwise, and a run spends credits.

- **First run.** Call `list-runs-tool` first. A run already open: follow it, start nothing, and
  tell the operator. Otherwise, on an explicit go after the estimate, call `trigger-run-tool`.
  If the estimate says the run cannot start, do not call it; tell the operator why.
- **Schedule.** On an explicit go, call `update-project-settings-tool` with `project_id` and
  `is_active: true`. Then save `get-project-tool` and run `bind` again so that the version
  records the activation.

A run takes some time to complete. `report` reads it once it has.

## 8. Close

Call `project-edit-link-tool` for each project and give the operator the links. Tell them, in
the chat: the projects created and changed, the dimensions and questions saved, the questions
deleted (if any), the runs ingested before the save and the ones recorded as unavailable, the
estimate, whether a run was started or a schedule activated, and that the next step is `report`
once a run has completed.

On a host without a lasting folder, pack the study before the conversation ends: `monitor.py
pack --study "$S" --out <the folder the host offers for download>`, offer the pack for download
and tell the operator to keep it (SKILL.md).
