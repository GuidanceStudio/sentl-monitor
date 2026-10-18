# report

Reads the completed runs since the previous report, pools them into one period, compares the
period with the earlier ones and writes `reports/<date>.md`. Reads only: no Sentl write, no
credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` today's date (`YYYY-MM-DD`).
Run every command with `--study "$S"`.

## 1. Preflight

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

`list-runs-tool` with `P`; order the runs by `started_at`, never by their place in the
listing. The runs to read:

- **First report** (`$S/history/reports.json` missing, or no report in it dated before
  `D`): the completed runs started in the last five `report_every` intervals before `D`
  (35 days for `weekly`, five months for `monthly`). The last interval is the period; the
  four before it are rebuilt from their runs, so the report can compare with them.
- **Later reports:** the completed runs started after `period.to` of the latest report in
  `history/reports.json`.

Completed means `completed` or `completed_with_warnings`; any other status is not final:
skip the run and mention it to the operator. Runs listed in `history/unavailable.json` are
requested again.

For each of those runs not yet in `$S/history/runs/K/`: if `$S/inbox/run-<run>.json` exists
(`adopt` saved it), use it; else call `get-run-results-tool` and save it there (copy the
host's file when the response was large). Then:

```bash
python3 <skill>/scripts/monitor.py ingest --study "$S" --project K --results "$S/inbox/run-<run>.json"
```

- Exit 2, not complete JSON: save the response again from the host's file and rerun.
- Sentl returned an error instead of results:
  `monitor.py ingest --study "$S" --project K --unavailable <run> --reason "<the error>"`.
- The output lists unmatched responses or a run score that differs: keep it for step 11.

## 4. Models

`list-ai-models`, saved to `$S/inbox/models.json`. It gives each researcher model's public
name; the report never shows a model id.

## 5. Period

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
  one the material holds; a fact term named in the sentence is quoted in «» as listed.
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
refused (exit 2) when a half's file is missing: run `period` again. When it passes, the report is recorded in
`history/reports.json` as final, and the next report compares with it.

## 11. Tell the operator, in the chat

The report's path, the runs it covers, and anything the scripts flagged: edits detected in
Sentl and how each affects the comparison, the periods rebuilt from earlier runs, the two
halves compared on a first report and any project with runs in one half only, or that no
earlier period exists, runs left out or
unavailable, unmatched responses, a Sentl run score
that differs from the one computed, dimensions shown without a figure. None of this goes in
the report.
