# Changelog

Each release of sentl-monitor, newest first. The version is `metadata.version` in
`skills/sentl-monitor/SKILL.md`.

## 0.1.0 (unreleased)

The first release. It reports on Sentl projects that already exist; the routes that design a
study and create projects in Sentl are planned (README, "Planned").

- `adopt <project>` takes an existing Sentl project into a study folder and asks for what Sentl
  does not hold: the research question and purpose, who asks, the subject and its competitors
  with their websites, the facts to track with their current and outdated values, the market,
  the report's language, the report cadence and where each theme came from. It only reads from
  Sentl.
- `report` writes a dated report on the runs of the last week or month: how the study was built,
  a summary, what the assistants say per dimension with verbatim excerpts and the cited domains,
  and what changed since the previous period. It only reads from Sentl and spends no credits.
- The first report compares with up to four earlier periods rebuilt from the project's runs, or,
  on a project younger than one period whose runs span at least 14 days, the second half of its
  period with the first.
- Each figure comes with what explains it: whether the answers state a fact as it is now or as
  it was, the pages cited with each, how many of the answers are independent (the rounds of a run
  that cite the same pages count as one), movements inside a period and the day they started, the
  subject's presence run by run, answers that found no evidence, and whether the cited pages are
  the subject's own, a competitor's or a third party's.
- Questions edited in the Sentl web panel are detected; a reworded question keeps its
  comparison, and a question that now asks something else starts a new one.
- `monitor.py check` refuses a report whose quotes are not verbatim, whose figures are not the
  period's, whose sections are out of order, or which shows an internal id, a file name or a
  credit figure.
- `monitor.py charts` writes a report's figures as chart tables for a deck in
  [md2](https://github.com/GuidanceStudio/md2), which turns Markdown into HTML presentations.
- `monitor.py doctor` checks Python and the study folder; `monitor.py --version` prints the
  version.
- `monitor.py pack` and `unpack` carry a study between conversations on a host that deletes its
  files when the conversation ends.
- Reports in English or Italian; Linux, macOS and Windows through WSL.
- Install as a Claude Code plugin, with `install.sh` for Claude Code, Codex and opencode, or as a
  zip for claude.ai and ChatGPT. Tested in Claude Code only. On claude.ai, ChatGPT and Codex the
  skill installs, but a report needs Sentl's run export, which is not available yet.
- A sample report on a fictional brand, in `examples/`.
