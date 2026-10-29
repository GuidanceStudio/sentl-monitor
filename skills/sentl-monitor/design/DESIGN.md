# design

Turns the themes of `brief.md` into a study: dimensions, projects, who asks, questions, rubrics
and the narrative, written to `$S/study.json` and printed as `$S/study-review.md` for the
operator's approval. Sentl is read once (`list-ai-models`); no write, no credit spent.

`<skill>` below is this skill's directory; `$S` is the study folder. The fields of `study.json`
are in ARCHITECTURE.md §`study.json`; the dimension catalogue is `<skill>/design/catalogue.md`.
Read both before step 2.

Every `monitor.py` command below can also end with exit 6: an unexpected error. Stop, give the
operator the message, and run the same command with `--debug` to show where it failed.

## 1. Inputs

```bash
python3 <skill>/scripts/monitor.py doctor --study "$S"
```

Exit 1: the folder cannot be written. On a web sandbox, unpack the pack first (SKILL.md).
Read `$S/brief.md` and `$S/search-demand.json`. Without `brief.md`, run `brief` first. Call
`list-ai-models` and save the response unchanged to `$S/inbox/models.json`; it holds each
model's id, public name and `credits`, the tariff per call.

## 2. Themes

Copy the brief's themes into `themes`, each with `id`, `label` and `origins`. Merge duplicates.
A theme with no origin is traced to a document, a remark of the operator or a search, or it is
dropped. Origin kinds: `client_material`, `client_issue`, `client_analysis`, `search`, `probe`.

## 3. Dimensions

A dimension comes from one or more themes and is named the way the client names it. Each
theme's `dimension` holds the key of the dimension it feeds. Use `catalogue.md` for dimensions
that recur (reputation, recommendation, comparison, price, health-safety and the others) and adapt their wording to the
subject. A project has five to seven dimensions of at least two questions each. A theme left
out says why in `narrative.design_rationale`. Set each dimension's `search_lean` from its
theme's searches: `negative` when the top queries doubt or accuse (`... bad for you`), `positive`
when they praise, `none` when they do not lean.

## 4. Projects

One study project is one Sentl project, because Sentl computes one score for each run of a
project. Questions that name the subject are read by their mean score; questions that name no
brand are read by whether and where the subject appears. A project that holds both gives a score
nobody can read, so they go in two projects. Projects also differ in models, rounds and
schedule. Each project carries `question` (what it answers) and `decision` (what the client
decides with it).

## 5. Who asks

Choose `generic_consumer`, `personas`, `stakeholders` or `mixed` and write the reason in
`narrative.audience`. With `personas` or `stakeholders`, every question carries a `persona` in
plain words: who types it and in what situation. Ask the operator when the choice is not clear
from the brief.

## 6. Questions

Write each question as the person types it, in the market's language, starting from the top
queries of its theme in `search-demand.json`. Take a pattern from the catalogue entry and adapt
it; never copy it unchanged.

- `branded` is true when the text names the subject, false when it names no brand. A question
  with `branded: false` contains no alias of the subject and no alias of a foil.
- `framing` is `positive`, `negative` or `neutral`. Where a dimension's `search_lean` is
  `negative`, add a question of positive framing; where it is `positive`, add a negative one.
  Give the two the same `pair` id. A pair holds exactly two questions of one dimension.
- Name the market in the text when the answer depends on it, because Sentl sets no location
  for the researcher models.
- Two questions in a dimension never share a text, and two dimensions in a project never share
  a name: Sentl's results identify questions by dimension name and text.
- Keys are `<dimension>-<n>`. A key is never reused, not even after the question is retired.

Limits Sentl enforces: dimension name 100 characters, label 100, question 500, each rubric
anchor 300, judge instructions with their facts 500.

## 7. Rubrics

Choose the axis of the dimension first: `stance` (1 against the subject, 5 for it with grounds)
or `fidelity` (1 wrong as fact, 5 accurate with the conditions the evidence sets). Then write
five anchors, each an observable property of the answer, adapted from the catalogue entry. On a
question that names no brand, 2 is *not mentioned* and 1 is *named negatively or advised
against*.

Judge instructions say how to apply the anchors. Put the dated facts in `facts`, not in the
instructions: `{"fact", "source", "date", "current", "outdated"}`, where `current` and
`outdated` are the terms as answers write them (`period` counts the answers that state each).
A fact is read from a primary source and dated the day it was read; a statement from an AI
answer is not a fact. `monitor.py` composes Sentl's `additional_instructions` from the
instructions and the facts.

## 8. Narrative

Write `narrative`: the research question (neutral: what is monitored, never one valence of it),
the purpose, the audience, `criteria` (who wrote the rubrics and when), the score axis, and a
`design_rationale` entry for each design choice with its reason (why two projects, why these
personas, which themes were left out).

## 9. Models, rounds, schedule, cadence

Offer the models of `models.json` with their public names and tariffs. Each project lists its
`models` by id, its `rounds` and its `schedule` (`daily`, `weekly` or `monthly`); the study has
`report_every` (`weekly` or `monthly`). Rounds times the runs in a report period should reach
three answers for each question and model.

## 10. Validate

```bash
python3 <skill>/scripts/monitor.py validate --study "$S" --models "$S/inbox/models.json"
```

Exit 1 lists the problems, one per line, and writes nothing. Correct `study.json` and run it
again until it passes. Warnings are printed under a passing result: tell the operator each one
and either fix it or note why it stays in `narrative.design_rationale`. Exit 2: `study.json` is
missing or not a study. Exit 5: the saved `list-ai-models` is not the response the skill reads.

## 11. Review and stop

```bash
python3 <skill>/scripts/monitor.py review --study "$S" --models "$S/inbox/models.json"
```

It writes `$S/study-review.md` and prints it: the narrative, the theme inventory with origins
and search demand, projects and dimensions, every question with its persona, framing, rubric and
the judge instructions Sentl will receive, and the credit estimate from the tariffs. Judging
costs no credits; `setup` shows Sentl's own figure before any run. Show the
operator the review and stop. Nothing is created in Sentl until they approve it.

## Revising a study

Keep a copy of the approved `study.json` (for example `$S/inbox/previous-study.json`), edit
`study.json`, and classify each change with the operator:

- **reworded**: the same intent in other words. The question keeps its key, so its results stay
  comparable.
- **new_intent**: the question now asks something else. It gets a new key and the old key is
  retired.
- **criteria**: the rubric, the judge instructions or the facts changed; the key stays.

```bash
python3 <skill>/scripts/monitor.py revise --study "$S" --previous "$S/inbox/previous-study.json" --dry-run
python3 <skill>/scripts/monitor.py revise --study "$S" --previous "$S/inbox/previous-study.json" --new-intent price-1
```

`revise` lists the changes, appends them to each question's `lineage`, replaces a `new_intent`
question under its new key and records the old one in the dimension's `retired`. Run
`validate` and `review` again afterwards.
