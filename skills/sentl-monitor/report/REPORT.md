# report

Reads the completed runs since the previous report, pools them into one period, compares the
period with the earlier ones and writes `reports/<date>.md`. Reads only: no Sentl write, no
credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` today's date (`YYYY-MM-DD`).
Run every command with `--study "$S"`.

Every `monitor.py` command below can also end with exit 5 or 6. Exit 5: a saved response does
not have the shape the skill reads, and the message names the tool and the field. Sentl changed
what it returns, so no figure computed from it can be trusted: do not edit the file; stop and
tell the operator the tool and the field, since the skill needs an update before the next report.
Exit 6: an unexpected error; stop, give the operator the message, and run the same command with
`--debug` to show where it failed.

**Sentl's errors.** Every error from Sentl reads "An internal server error occurred.", whatever
its cause. Call the tool once more. If it fails again on `get-run-results-tool`, record the run
as unavailable (step 3) and go on. If it fails again on `get-project-tool`, `list-runs-tool` or
`list-ai-models`, stop: the report cannot be written without it. Tell the operator which tool
failed and that `report` can be run again later.

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

Exit 2: the pack was changed after it was written, is older than the folder's last report, or
belongs to another study; exit 5: a later version of the skill wrote it. Tell the operator why
and stop. When the user has no pack, ask for the one written after the last report; without
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
step 6 asks the operator for. An edit made after the period's last run shows in the next
report, not in this one.

## 3. Read the runs of the period

For each project, `list-runs-tool` with `P`, saved to `$S/inbox/runs-P.json`, then:

```bash
python3 <skill>/scripts/monitor.py runs --study "$S" --project K --saved "$S/inbox/runs-P.json" --date D
```

It prints the runs to fetch, ordered by start time (the listing is newest first with
exceptions), and ends with a `Fetch:` line holding their ids:

- **First report** (no report in `history/reports.json` dated before `D`): the completed runs
  started in the report's `report_every` interval and the four before it (five weeks or five
  months). The last interval is the period; the four before it are rebuilt from their runs,
  so the report can compare with them.
- **Later reports:** the completed runs started after the last run of the previous report and
  up to the end of `D`.

Completed means `completed` or `completed_with_warnings`. Runs already ingested are left out;
runs recorded as unavailable are listed again. The output also lists the runs not final yet,
which the next invocation reads, and any status the skill has never seen; neither is fetched.
A line starting `Warning` says the oldest run in the listing started after the start of the
window: Sentl's listing has no paging, so either the project has no earlier run or the listing
stops there. Keep these for step 11.

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
- Sentl returned an error instead of results ("An internal server error occurred."): call
  `get-run-results-tool` once more; if the error repeats, record the run as unavailable and
  go on: `monitor.py ingest --study "$S" --project K --unavailable <run> --reason "<the error>"`.
  The next report requests it again.
- Exit 3: the run is not final yet; it is read at the next invocation.
- The output lists unmatched responses or a run score that differs: keep it for step 11.

## 4. Models

`list-ai-models`, saved to `$S/inbox/models.json`. It gives each researcher model's public
name; the report never shows a model id.

## 5. Period

Periods are counted in UTC: the report date `D` covers the runs started up to the end of `D`
in UTC, and the default date is today's local date.

```bash
python3 <skill>/scripts/monitor.py period --study "$S" --date D --models "$S/inbox/models.json"
```

The output says which runs the period pools, which runs were left out and why, the
unavailable runs, and on a first report the periods rebuilt from earlier runs or, when there
is none, either the two halves of the period compared with each other (runs spanning at least
14 days) or that this is the first measurement. Keep all of it for step 11; none of it goes
in the report.

- Exit 2 saying `report_every` is not set: ask the operator whether a report covers a week
  or a month, write it into `study.json`, rerun.
- Exit 4: no run of the period has 90% of its answers judged, or the period has no run.
  Tell the operator which runs and the share judged, and stop.

## 6. Method sections

```bash
python3 <skill>/scripts/monitor.py method --study "$S" --date D --models "$S/inbox/models.json"
```

Exit 2 listing fields: the operator has not answered them yet; ask (see `adopt` step 6) and
rerun. The script writes `reports/D.md`. A first report (no final report before `D` in
`history/reports.json`) opens with the method sections; a later report opens with what
changed and what the assistants say, and the method sections close it. The summary
section, after the method sections in a first report and first in a later one, holds the
`[[summary]]` marker. The findings section holds one entry per dimension, marked `[[...]]`. The changes section holds either the line
saying this is the first measurement, or the period compared with (on a first report with no
earlier period, the line naming the two halves of the period, their dates and each project's
runs and answers in each), a `[[...]]`
marker for the changes in the answers, and one line per change in the design.

## 7. Write the findings

Read `$S/history/material/D.md`: per dimension, the figures, the domains cited, and per
question whether it names the subject, then every answer with its assistant and score,
between `~~~~` lines exactly as Sentl returned it. Replace each `[[...]]` marker of the
findings with:

- **The heading**: `### <Dimension name>: <what the person asking is told>`. The part after
  the colon is a plain statement of what the answers say, never a score.
- **One or two excerpts**, each a Markdown blockquote (`> ...`) copied verbatim from one
  answer in the material. Text can be skipped inside an excerpt with `[…]`, never joined from
  two answers. Markdown emphasis (`**`) and citation markers (`[1]`) may be left out; nothing
  else is changed. Copy the excerpt from the material by its lines rather than retyping it:
  assistants use typographic characters a retyped quote loses.
- **After each excerpt**, on a plain line: the question in «» and the assistant's public
  name.
- **The domains** those answers cite:
  the subject's own first, then the most cited, five in all.
- **The figure**, when the material says `figure yes`: the dimension's mean as the material
  prints it (one decimal, a comma in Italian; never round it again), and how many answers
  were judged out of how many expected, written as "N su M risposte" or "N of M answers". When it says `figure no`: no mean, only how many
  answers were judged. For a question whose material says `names the subject: no`, the
  presence: in what share of the answers the subject is named (whole percent).
- An entry cites the figures of its own dimension and the project's overall figure, never
  another dimension's.
- **The insights the material prints for the dimension** (fact currency, sources behind a fact
  or a score, readings, episodes, presence by run, missing evidence, who wrote the sources),
  each in one plain sentence with its figure, as `report/INSIGHTS.md` describes. State every
  one the material holds; a fact term named in the sentence is quoted in «» as listed. For an
  episode, the close date is the first run back inside the range; it says nothing about the runs
  after it. Write the close as that date, state the later runs the material lists under it as
  still on its side, and never write that the measure was outside the range "only" during the
  episode (`check` refuses a word for "only" before the episode's dates in the same clause unless
  the sentence names every later run).
- **One line on what it means for the client**, last.

## 8. Write the changes in the answers

Skip this step when the changes section says this is the first measurement. Otherwise read
the material's part "Changes since the previous period", or "Changes between the two halves
of the period" on a first report with no earlier period, and replace the `[[...]]` marker of
the changes section with:

- **Each change called**, project, dimension or question: one sentence saying what moved, with
  the value before and now as the material prints them (a mean with one decimal, a presence
  or a share in whole percent). Between the halves, "before" is the first half and "now" the
  second. A dimension the material marks as not compared, or new, gets no figure here.
- **The facts whose current share changed**: the share of the answers stating a current term,
  before and now.
- **An episode beside a change**: where the material lists an episode under a change called,
  state the episode's first date in the same sentence ("from 9 October"). The material lists
  only the episodes on the side the change moves to that run in the later period or half.
- **Each verdict change**: one sentence naming the assistant and the question, then the two
  answers the material gives, as excerpts copied by their lines, each followed by the question
  in «», the assistant's public name and which period, or which half, it comes from.
- **The domains** new or lost: the material lists the five cited by most answers in each list.
- **Presence changes**: for each question in the material's "Presence changes", the domains
  that came or went with the subject, and an episode or a fact share that explains a change
  called (`report/INSIGHTS.md`).
- **One line** saying the other dimensions are unchanged.

Keep the line above the marker and the design-change lines below it as `method` wrote them;
`check` refuses a report on the two halves whose changes section no longer names them.

## 9. Write the summary

The summary is written last, from the findings and changes already written. Replace the
`[[summary]]` marker with a bulleted list of three to five plain declarative sentences, each
stating one point the reader needs, with its figure as the material prints it. Any figure of
the period may be cited here, whichever dimension it belongs to, and in a later report the
figures of the comparison. The summary quotes no answer: an excerpt belongs in findings.

Every figure in steps 7 to 9 must come from the material, rounded as above. Write plain
declarative sentences; no slogans, no rhetorical openers. Never write a run, project or
question id, a question key, a model id, a file name, a credit figure, or anything about the
skill's own steps.

## 10. Check

```bash
python3 <skill>/scripts/monitor.py check --study "$S" "$S/reports/D.md"
```

Exit 1 lists each problem: fix the report and run it again until it passes. A quote that
fails was not copied exactly; a figure that fails is not in the period's metrics or its
comparison, or belongs to a dimension shown without a figure; a section out of order means
the report was rearranged; a summary that quotes an answer fails; a first report on the two
halves of its period fails when the line naming the halves was changed or removed, and is
refused (exit 2) when a half's file is missing: run `period` again. A period built before
episodes recorded the runs after their close is refused (exit 2) too: run `period` again for that
date, then `check`. When it passes, the report is recorded in `history/reports.json` as final,
and the next report compares with it.

On a host without a lasting folder, `check` ends by saying so. Pack the study, then copy the
report, and its PDF if one was made, to the same folder:

```bash
python3 <skill>/scripts/monitor.py pack --study "$S" --out <folder>
cp "$S/reports/D.md" <folder>/
```

`<folder>` is one the host offers files for download from. The pack holds what the next report
needs: the versions, the report index, the latest four periods and the runs from this report
on. Offer the report and the pack for download. Tell the user to keep both and, when the host
has Projects, to put the pack in the Project's files in place of the previous one: the next
report reads it from there.

## 11. Tell the operator, in the chat

The report's path, the runs it covers, and anything the scripts flagged: runs not final yet,
statuses never seen and a run listing that may be cut (step 3), edits detected in
Sentl and how each affects the comparison, the periods rebuilt from earlier runs, the two
halves compared on a first report and any project with runs in one half only, or that no
earlier period exists, runs left out or
unavailable, unmatched responses, a Sentl run score
that differs from the one computed, dimensions shown without a figure. None of this goes in
the report.

## 12. Charts for a deck (optional)

When the operator presents the report as a deck, after `check` has passed:

```bash
python3 <skill>/scripts/monitor.py charts --study "$S" --date D
```

It writes `reports/D.charts.md`: the report's figures as md2 `:::chart` tables, each under a
heading that says what it shows and the period or halves it covers. Per project, the dimension
means as a radar and a bar (the previous period and this one, the two halves, or this period
alone) and, with more than one assistant, by assistant; per question, the share stating the
current fact run by run, the share naming the subject run by run, and the domains behind a fact
or a score. Give the operator the file's path and the charts the output lists as left out; the
report itself does not change. On a host without a lasting folder, also offer
`reports/D.charts.md` for download, copied to the folder of step 10.
