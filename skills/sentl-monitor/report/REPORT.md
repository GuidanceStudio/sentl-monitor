# report

Reads the completed runs since the previous period, pools them into one period, compares the
period with the earlier ones, and goes on into the deck (`report/DECK.md`), the only thing the
reader receives. One invocation gives the deck. Reads only: no Sentl write, no credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` today's date (`YYYY-MM-DD`).
Run every command with `--study "$S"`. When the invocation is unattended, a scheduler started it
and no operator can answer: read "Unattended mode", at the end, before step 1.

Every `monitor.py` command below can also end with exit 5 or 6. Exit 5: a saved response does
not have the shape the skill reads, and the message names the tool and the field. Sentl changed
what it returns, so no figure computed from it can be trusted: do not edit the file; stop and
tell the operator the tool and the field, since the skill needs an update before the next period.
Exit 6: an unexpected error; stop, give the operator the message, and run the same command with
`--debug` to show where it failed.

**Sentl's errors.** An error carries a code and a message: tell the operator both as Sentl gave
them. `internal` is called once more. If it fails again on `get-run-results-tool`, record the run
as unavailable (step 3) and go on. If it fails again on `get-project-tool`, `list-runs-tool` or
`list-ai-models`, stop: the period cannot be built without it. Tell the operator which tool
failed and that `report` can be run again later. `not_found`: stop and name the id.
`invalid_argument`: stop, the skill needs an update. A saved error is refused with exit 2, naming
its code and message.

## 1. Preflight

In every conversation, first:

```bash
python3 <skill>/scripts/monitor.py doctor --study "$S"
```

Exit 1: the folder cannot be written; choose another. When `doctor` reports a web sandbox, the
host has no lasting folder (SKILL.md), and the study arrives as a pack: the one the user
attached, or the one kept in the Project's files; with several packs, the one with the latest
date in its name. Unpack it before any other command:

```bash
python3 <skill>/scripts/monitor.py unpack --study "$S" <pack>
```

Exit 2: the pack was changed after it was written, is older than the folder's last period, or
belongs to another study; exit 5: a later version of the skill wrote it. Tell the operator why
and stop. When the user has no pack, ask for the one written after the last deck; without
it, the study starts again with `adopt`.

`$S/study.json` and `$S/sentl.json` must exist; otherwise run `adopt` first. Call
`list-organizations` to confirm the connection (see SKILL.md when it fails).

## 2. The project as it is in Sentl now

For each project in `sentl.json` (key `K`, project id `P`), call `get-project-tool` with `P`
and save it to `$S/inbox/project-P.json` (copy the host's file when the response was large).
Then:

```bash
python3 <skill>/scripts/monitor.py detect --study "$S" --project K --saved "$S/inbox/project-P.json" --dry-run
```

- **Unchanged:** run the same command without `--dry-run`, which records that the project
  was seen today.
- **Changes listed:** someone edited the project in the Sentl web panel. A reworded question
  keeps its key and is compared with its earlier wording. Ask the operator, for each
  reworded question, whether it still asks the same thing. Then run the command without
  `--dry-run`, adding `--new-intent <key>` for each question the operator says now asks
  something else. Unattended, run it without `--new-intent`.
- Exit 2: the saved file is not complete JSON or belongs to another project; save it again.

The detected version is in `history/versions/`. For an adopted project, `study.json` and
`sentl.json` now follow Sentl's project; a new dimension gets a theme without origins, which
`deck` asks the operator for (step 6). An edit made after the period's last run shows in the
next period, not in this one.

## 3. Read the runs of the period

For each project, ask for the arguments of the period's window:

```bash
python3 <skill>/scripts/monitor.py runs --study "$S" --project K --date D
```

Call `list-runs-tool` with them, save the response to `$S/inbox/runs-P.json`, then:

```bash
python3 <skill>/scripts/monitor.py runs --study "$S" --project K --saved "$S/inbox/runs-P.json" --date D
```

A host that cuts large responses reads the listing with `page` and `page_size`: save each page,
the later ones as `$S/inbox/runs-P.p2.json` and so on, and pass them all to `--saved`. A listing
whose `total` exceeds the runs read is refused, naming the page to read.

It prints the runs to fetch, ordered by start time (the listing is newest first with
exceptions), and ends with a `Fetch:` line holding their ids:

- **First period** (no entry in `history/reports.json` dated before `D`): the completed runs
  started in the study's `report_every` interval and the four before it (five weeks or five
  months). The last interval is the period; the four before it are rebuilt from their runs,
  so the period can be compared with them.
- **Later periods:** the completed runs started after the last run of the previous entry and
  up to the end of `D`. The entry is the one the deck's `check` writes (step 6); in a folder
  that holds reports written by versions before 0.8.0 (`reports/<date>.md`), their entries stay
  as they are and count the same way.

Completed means `completed` or `completed_with_warnings`. Runs already ingested are left out;
runs recorded as unavailable are listed again. The output also lists the runs not final yet
(`queued`, `pending`, `researching`, `running`, `judging`), which the next invocation reads, the
runs ended with no results (`failed`, `stalled`), left out of the period with Sentl's error, the
runs the listing already shows under the 90% floor, which cost no read, and any status the skill
has never seen; none of these is fetched. A listing with no `expected` or `judged` leaves the floor
to the results. A line starting `Warning` says a listing saved without its `total` may stop before
the window's start. Keep these for step 7.

When the host saves a large tool result to a file, take each run on the `Fetch:` line one at a
time: when its line says it is already saved in `inbox/` (`adopt` saved it), use that file; else
call `get-run-results-tool` and save it to `$S/inbox/run-<run>.json` (copy the host's file when
the response was large). When it does not (a web conversation), fetch all the runs of the line
at once: `export-runs-tool` with the project and those run ids, then
`monitor.py download --study "$S" --url <download.url> --sha256 <download.sha256>`, or, when the
host cannot reach the link, the user downloads it and attaches the file, and
`monitor.py import --study "$S" --sha256 <download.sha256> <file>` writes `inbox/run-<run>.json`
for each run. Exit 7 on `download`: ask for a new export. A single run too large for one
response can be read in pages with `get-run-results-tool` (`page`, `max_chars`), each page
saved to its own file, and `monitor.py ingest --pages <page files>` joins them. Then, for each
run:

```bash
python3 <skill>/scripts/monitor.py ingest --study "$S" --project K --results "$S/inbox/run-<run>.json"
```

- Exit 2, not complete JSON: save the response again from the host's file and rerun.
- Sentl returned the error `internal` instead of results: call
  `get-run-results-tool` once more; if the error repeats, record the run as unavailable and
  go on: `monitor.py ingest --study "$S" --project K --unavailable <run> --reason "<the error>"`.
  The next period requests it again.
- Exit 3: the run is not final yet; it is read at the next invocation.
- Exit 2 on a `failed` or `stalled` run: it holds no results and stays out of the period.
- The output lists unmatched responses or a run score that differs: keep it for step 7.

## 4. Models

`list-ai-models`, saved to `$S/inbox/models.json`. It gives each researcher model's public
name; the deck never shows a model id.

## 5. Period

Periods are counted in UTC: the date `D` covers the runs started up to the end of `D` in UTC,
and the default date is today's local date.

```bash
python3 <skill>/scripts/monitor.py period --study "$S" --date D --models "$S/inbox/models.json"
```

The output says which runs the period pools, which runs were left out and why, the
unavailable runs, and on a first period the periods rebuilt from earlier runs or, when there
is none, either the two halves of the period compared with each other (runs spanning at least
14 days) or that this is the first measurement. Keep all of it for step 7; none of it goes
in the deck.

- Exit 2 saying `report_every` is not set: ask the operator whether a period covers a week
  or a month, write it into `study.json`, rerun.
- Exit 4: no run of the period has 90% of its answers judged, or the period has no run.
  Tell the operator which runs and the share judged, and stop.

## 6. The deck

Go on into `report/DECK.md` with the same `D`, from its step 1, in this invocation. The deck is
the only document the route writes, and its PDF the only one printed. `deck` exit 2
listing fields: the operator has not answered them yet; ask (see `adopt` step 6) and rerun.

When the deck passes its `check`, `history/reports.json` records the period with the runs it
read: the next period starts after them and is compared with this one. The route ends with
DECK.md: `check` and `pdf` are its last commands, and on a host without a lasting folder the pack
comes after them (DECK.md step 9).

## 7. Tell the operator, in the chat

With what DECK.md step 9 lists: the runs the period covers, and anything the scripts flagged:
runs not final yet, runs ended with no results and their error, runs under the floor in the
listing, statuses never seen and a run listing that may be cut (step 3), edits detected in
Sentl and how each affects the comparison, the periods rebuilt from earlier runs, the two
halves compared on a first period and any project with runs in one half only, or that no
earlier period exists, runs left out or unavailable, unmatched responses, a Sentl run score
that differs from the one computed, dimensions shown without a figure. None of this goes in
the deck.

## Redo the latest period of its date

When the latest period must be built again for its own date `D` (a new version of the skill, a fact corrected in
`study.json`, a run ingested since), run step 5 with the same `D`, then `deck` with it:

```bash
python3 <skill>/scripts/monitor.py period --study "$S" --date D --models "$S/inbox/models.json"
python3 <skill>/scripts/monitor.py deck --study "$S" --date D
```

Then the deck's `check` and `pdf` (`report/DECK.md`, step 6): `monitor.py check` on `reports/D.deck.json` records the
period again.

- **Keeps:** the runs in `history/runs/`, the versions, the earlier periods and their entries, the deck's text
  `reports/D.deck.json` and its notes `history/deck/D.notes.md`. Only the entries before `D` set the period's window,
  so `period` pools the same runs as the first time and any run of that window ingested since.
- **Rewrites:** `history/periods/D.json` and `history/material/D.md` (on a first period, the rebuilt periods and the
  halves as well); `history/deck/D.figures.md`; and, when the deck's `check` passes, the entry of `D` in
  `history/reports.json`, with the runs the new period read.

Fix every text the deck's `check` refuses on the new figures; a figure the code draws is never changed by hand. Redo
only the latest period: a later one has been compared with it.

## Unattended mode

A scheduler starts the route with no operator to answer (README, "Scheduled reports"). Read this
section before step 1 when the invocation says it is unattended. Every step above holds except where
this section changes it. Ask nothing: where a step says to ask the operator, take the
choice written here or stop.

1. Run step 1, then for each project call `list-runs-tool` with the arguments of step 3 and save
   it to `$S/inbox/runs-P.json` (`P` is the project's Sentl id), later pages as
   `$S/inbox/runs-P.p2.json` and on, before anything else is read from Sentl. Then:

   ```bash
   python3 <skill>/scripts/monitor.py pending --study "$S" --date D
   ```

   When its output starts with `nothing_new`, no completed run is new: the script has recorded
   the outcome, so stop here, call no other tool and write nothing. A run not final yet is not new;
   the next invocation reads it. Otherwise go on with step 2.
2. Step 2 without `--new-intent`: a reworded question keeps its key.
3. Step 5: exit 4 means no run of the period has 90% of its answers judged, or the period has
   no run. `period` has recorded `below_floor`; stop and write nothing. A run under 90% judged
   is left out of the period, and a dimension under 80% judged shows its answers without a
   figure; the deck writes what the figures file prints.
4. Steps 5 and 6, exit 2 for a missing answer of the operator (`report_every`, or a field
   `deck` lists): stop. No outcome is recorded, since no invocation can answer it; the output
   names the field.
5. Step 6 runs DECK.md steps 1 to 6, with `--unattended` added to every `check` of the deck. A
   `check` that fails records the deck as a draft: `last-report.json` says `draft` with the
   problems found and, when the date has no entry yet, `history/reports.json` holds the period as
   a draft, so the next invocation does not write it again. Fix what `check` names and run it
   again: a `check` that passes makes the entry final and records `written`. The reader's test
   and the audit (DECK.md steps 7 and 8) are left to the operator, who runs them before sending
   the deck.
6. Step 7 is the invocation's last output, short and plain: the outcome, the deck's copy to send
   (or the path of the deck left as a draft), that the reader's test and the audit are left to
   the operator, and the items step 7 lists. Sentl's errors that stop a route (exit 5, exit 6, a
   tool that fails twice) end the invocation with the message; no outcome is recorded.
7. Never call a Sentl tool that writes. The invocation needs only `list-organizations`,
   `get-project-tool`, `list-runs-tool`, `get-run-results-tool` and `list-ai-models`.

`history/last-report.json` holds `{at, outcome, detail}` for the latest invocation:

| Outcome | Recorded by | Meaning |
|---|---|---|
| `written` | the deck's `check` | the deck passed `check` and records its period |
| `draft` | the deck's `check --unattended` | the deck failed `check`; its period is recorded as a draft |
| `nothing_new` | `pending` | no completed run is new since the previous period |
| `below_floor` | `period` | no run of the period has 90% of its answers judged |

Two invocations on the same runs write one deck: the second one ends at `pending` with
`nothing_new`.
