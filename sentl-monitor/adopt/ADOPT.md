# adopt <project>

Takes a project that already exists in Sentl into a study folder, so `report` can report on
it. Reads only: no Sentl write, no credit spent.

`<skill>` below is this skill's directory; `$S` is the study folder.

## 1. Connection

Call `list-organizations`. No tool, or an authentication error: stop and give the operator
the connection steps from https://app.sentl.ai/mcp/setup. Note the operator's role in each
organization; the User role is enough for this route.

## 2. Study folder

Ask where the study folder is, or propose `./<subject>-study/` in the current directory. It
must not be inside this skill's directory. Create `$S/inbox/`. If `$S/study.json` exists, the
project joins that study; say so.

## 3. Find the project

Call `list-projects-tool`. Match `<project>` against the names and ids. More than one match,
or none: show the candidates with their organization and ask. Note the project id `P`.

## 4. Save the project and its latest run

1. `get-project-tool` with `P`; save the response to `$S/inbox/project-P.json`.
2. `list-runs-tool` with `P`; save it to `$S/inbox/runs-P.json`. Order the runs by
   `started_at`, newest first (the listing is not always in that order). The latest
   completed run is the newest with status `completed` or `completed_with_warnings`.
3. `get-run-results-tool` on that run; save it to `$S/inbox/run-R.json`, copying the file the
   host wrote when the response was large. If Sentl returns an error for that run, try the
   next completed run; if none can be read, go on without a run.

## 5. Adopt

```bash
python3 <skill>/scripts/monitor.py adopt --study "$S" --project "$S/inbox/project-P.json" \
  --run "$S/inbox/run-R.json" --key <short-key>
```

`--key` is a short local name for the project (for example `brand` or `category`); without it
the script uses a slug of the project's name. Leave `--run` out when no run could be read, and
tell the operator that the saved project could not be checked against a run.

Exit 2 saying the saved project lacks texts of the run: the project was not saved exactly.
Call `get-project-tool` again, save it again (copy the host's file if there is one), rerun.
After a second failure, stop and show the operator the texts listed.

## 6. Ask the operator what Sentl does not hold

The script prints the fields to fill and their shapes. Ask for them in one message, in the
operator's language, proposing a value wherever the project suggests one (rubrics and judge
instructions often name the subject's competitors and websites). The texts are printed in
the report as written, so they are written in the report's language:

- **Research question** (neutral: what is monitored, never one valence of it) and
  **purpose** (what the client will decide with the reports).
- **Who asks**: `generic_consumer`, `personas`, `stakeholders` or `mixed`, with the reason.
  For a business audience, `stakeholders` with the reason ("finance managers comparing
  providers") reads better than a generic consumer.
- **Who wrote the rubrics and when** (`narrative.criteria`: `by`, `date`).
- **The subject**: label, aliases as answers write them (brand name, product names), owned
  domains. **Foils**: competitors or alternatives, each `{"id", "label", "aliases",
  "domains"}`, if the reports should say who is named before the subject; `domains` are the
  sites the competitor owns, so the report can say which cited pages it wrote.
- **Facts that carry a figure or a name** (a price, a fee, the person in charge), for each
  question whose rubric or judge instructions state one: a `facts` list under that question in
  `study.json`, each `{"fact", "source", "date", "current": [...], "outdated": [...]}`, the
  terms written as answers write them ("2,10 €", "1,90 €"). Propose them from the judge
  instructions and ask the operator for last year's value. The report then counts the answers
  stating each, run by run (`report/INSIGHTS.md`).
- **Market**: `{"country": ISO 3166 code ("GB" for the United Kingdom), "language": ISO 639
  code}`. **Report language**: `it` or `en`.
- **Report cadence** (`report_every`: `weekly` or `monthly`). Propose `monthly` when the
  project runs weekly or daily, so a report pools several runs. The first report covers the
  last week or month and compares with up to four earlier weeks or months rebuilt from the
  project's runs. When the project has no run before that last interval, the first report
  compares the second half of its period with the first if its runs span at least 14 days,
  and is the first measurement otherwise. Say which applies, from the runs listed in step 4.
- **Where each dimension's theme came from**: one or more origins per theme, each a `kind`
  (`client_material`, `client_issue`, `client_analysis`, `search`, `probe`) and a `detail`
  (the document, the conversation, the analysis).

Optional, ask only when the operator has an answer: the score axis (`stance`: 1 against the
subject, 5 for it; `fidelity`: 1 wrong as fact, 5 accurate), and each project's question and
the decision it informs.

Write the answers into `$S/study.json`, changing only those fields; `facts` is added beside a
question's text and rubric. Do not edit the questions, rubrics or ids the script wrote: they
are Sentl's. `method` lists a foil's `domains` or a fact's terms that are not a list of
strings.

## 7. Close

Tell the operator: the study folder's path, the dimensions and questions adopted (archived
dimensions are kept and not reported), how many completed runs the project has, the dates of
the earliest and the latest, and that `report` writes the first report: it covers the last
`report_every` interval and compares with the earlier intervals that have runs, up to four,
or, when no run precedes that interval, the second half of the interval with the first once
its runs span at least 14 days.
Runs older than this adoption are read with no recorded configuration: an answer to a
question worded differently then is left out, and a run with too many of those is left out
of its period; `report` lists them.
