# report

Reads the latest completed run of each project in the study and writes
`reports/<date>.md`. Reads only: no Sentl write, no credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` today's date (`YYYY-MM-DD`).
Run every command with `--study "$S"`.

## 1. Preflight

`$S/study.json` and `$S/sentl.json` must exist; otherwise run `adopt` first. Call
`list-organizations` to confirm the connection (see SKILL.md when it fails).

## 2. Read the latest run of each project

For each project in `sentl.json` (key `K`, project id `P`):

1. `list-runs-tool` with `P`; order by `started_at`, newest first. Take the newest run with
   status `completed` or `completed_with_warnings`. A run with any other status is not final:
   skip it and mention it to the operator.
2. If `$S/history/runs/K/<run>.json.gz` exists, it is already ingested; go on.
3. Otherwise, if `$S/inbox/run-<run>.json` exists (`adopt` saved it), use it; else call
   `get-run-results-tool` and save it there (copy the host's file when the response was
   large). Then:

   ```bash
   python3 <skill>/scripts/monitor.py ingest --study "$S" --project K --results "$S/inbox/run-<run>.json"
   ```

   - Exit 2, not complete JSON: save the response again from the host's file and rerun.
   - Sentl returned an error instead of results:
     `monitor.py ingest --study "$S" --project K --unavailable <run> --reason "<the error>"`,
     then take the next completed run.
   - The output lists unmatched responses or a run score that differs: keep it for step 7.

## 3. Models

`list-ai-models`, saved to `$S/inbox/models.json`. It gives each researcher model's public
name; the report never shows a model id.

## 4. Period

```bash
python3 <skill>/scripts/monitor.py period --study "$S" --date D --models "$S/inbox/models.json"
```

Exit 4: the run has fewer than 90% of its answers judged, so there is no figure to report.
Tell the operator which run and the share judged, and stop.

## 5. Method sections

```bash
python3 <skill>/scripts/monitor.py method --study "$S" --date D --models "$S/inbox/models.json"
```

Exit 2 listing fields: the operator has not answered them yet; ask (see `adopt` step 6) and
rerun. The script writes `reports/D.md` with the method sections, the first-report changes
line, and one entry per dimension under the findings section, marked `[[...]]`.

## 6. Write the findings

Read `$S/history/material/D.md`: per dimension, the figures, the domains cited, and per
question whether it names the subject, then every answer with its assistant and score,
between `~~~~` lines exactly as Sentl returned it. Replace each `[[...]]` marker with:

- **The heading**: `### <Dimension name>: <what the person asking is told>`. The part after
  the colon is a plain statement of what the answers say, never a score.
- **One or two excerpts**, each a Markdown blockquote (`> ...`) copied verbatim from one
  answer in the material. Text can be skipped inside an excerpt with `[…]`, never joined from
  two answers. Markdown emphasis (`**`) and citation markers (`[1]`) may be left out; nothing
  else is changed. Copy the excerpt from the material by its lines rather than retyping it:
  assistants use typographic characters a retyped quote loses.
- **After each excerpt**, on a plain line: the question in «» and the assistant's public
  name.
- **The domains** those answers cite.
- **The figure**, when the material says `figure yes`: the dimension's mean with one decimal
  (a comma in Italian), and how many answers were judged out of how many expected, written
  as "N su M risposte" or "N of M answers". When it says `figure no`: no mean, only how many
  answers were judged. For a question whose material says `names the subject: no`, the
  presence: in what share of the answers the subject is named (whole percent).
- An entry cites the figures of its own dimension and the project's overall figure, never
  another dimension's.
- **One line on what it means for the client.**

Every figure must come from the material, rounded as above. Write plain declarative
sentences; no slogans, no rhetorical openers. Never write a run, project or question id, a
question key, a model id, a file name, a credit figure, or anything about the skill's own
steps.

## 7. Check

```bash
python3 <skill>/scripts/monitor.py check --study "$S" "$S/reports/D.md"
```

Exit 1 lists each problem: fix the report and run it again until it passes. A quote that
fails was not copied exactly; a figure that fails is not in the period's metrics, or belongs
to a dimension shown without a figure.

## 8. Tell the operator, in the chat

The report's path, the runs it covers, and anything the scripts flagged: runs left out or
unavailable, unmatched responses, a Sentl run score that differs from the one computed,
dimensions shown without a figure. None of this goes in the report.
