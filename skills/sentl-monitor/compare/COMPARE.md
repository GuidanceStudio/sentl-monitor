# Compare two snapshots

For a second snapshot of one subject, taken later with the same questions, when neither was promoted. A promoted study
compares its periods with `report`. Both folders need their report done. Nothing goes to Sentl and no credit is spent.

Exit codes: 0 done. 1 `check` found problems. 2 refused: the message says what to fix. 6 an unexpected error; stop, give the
operator the message, and run the command again with `--debug`.

## 1. Write the report

Run it from anywhere, the earlier folder first:

```bash
python3 <skill>/scripts/monitor.py compare <earlier folder> <later folder>
```

It matches the questions by Sentl's id when both folders bind one project and by text otherwise, and refuses (exit 2), naming
them, questions that are not on both sides. Only the assistants of both sides are compared. It writes
`reports/<date>.compare.md` in the later folder, with the later snapshot's date.

## 2. Check it

```bash
python3 <skill>/scripts/monitor.py check --study <later folder> "<later folder>/reports/<date>.compare.md"
```

## 3. Tell the operator

Give the report as it is: its rows come from the two snapshots, and it says that a difference between two single runs is not a
trend.
