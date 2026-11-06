# Changelog

Each release of sentl-monitor, newest first. The version is `metadata.version` in
`skills/sentl-monitor/SKILL.md`.

## Unreleased

## 0.4.1 (2026-11-07)

- `check` on a deck reads every count in digits: "9 delle 12" and "9 of the 12" went unread, and so did any pair with no word
  for answers nearby, on three trial decks 40 of 73. Reports read the two new forms as well.
- A count beside a site, a page, an assistant or a competitor must be that name's. A count in the period's figures used to
  pass beside any name. A refusal prints the counts the name has.
- A site's count beside a page is refused, and a count beside a site needs its base. Where a grounding redirect hides the page,
  its count is a range.
- A site said to be cited most comes first, alone, among the sites the sentence speaks of, and a tie is refused. The title of
  the sources slide says it of any site it names as cited.
- A count of a site's or a page's stands in an action's reason and over a chart: no chart draws it.

## 0.4.0 (2026-11-06)

- The deck is rewritten for its reader, the client's marketing manager. It opens with what was done and a slide on what the
  report shows: the questions it answers, real questions as examples, how to read a figure. The next slide answers the same
  questions in the same order, and every evidence slide carries the question it belongs to. Every presence figure sits beside
  the competitors the same answers name, with the subject's position, and a competitor the question itself names does not
  count there. Labels are in the reader's words: favourable, neutral and unfavourable replace scores and means, a facts row
  states the fact with its source, one row per fact, and block, project and result-class names leave the slides. The actions
  table holds what to do and why. A slide can draw exactly the questions it speaks of, and a list of every question closes
  the deck. Schema `sentl-monitor/deck@2`: `opening`, `found.answers`, `actions[].why`, `slide.questions`.
- A question with recorded facts stays in its own block and shows in `facts` as well, so a topic's figure no longer leaves
  out its hardest question. Each count stands beside its bar, where a thin part cannot lose it. The opening says where the
  questions come from and how many answers a question gives, and the method says the assistants are asked with no account
  or history.
- `check` on a deck also refuses a figure in a read that its chart does not draw, the block's figure over a chart of part of
  the block, a title of more than two figures, a figure repeated on the first slides, a presence figure with no comparison, a
  subject among the first played down, words of the study, project names, a topic as the subject of a sentence, and an
  action that names no work. "None" and "all" pass beside the count that says so.
- Every count in the deck rests on one base: the answers the slide's block judges, the same on the cover, the cards, the
  charts and the method. The cover says how many questions went to which assistants, as whom, and how many answers were
  collected. The cards say what favourable means and that it is not measured on competitors.
- A name a few answers from the subject is said to be close on the chart: the next report can reverse the order.
- The facts slide shows the pages cited by the answers with an old figure and hardly ever by those with today's, by who wrote
  them: a site usually feeds both kinds of answer, so only a page says where an old figure comes from. An excerpt on a question
  about the subject says how its answer was rated. The sources slide shows every site an action names and the subject's most
  cited pages. An action on a third party prints how many answers on its slide cite that site, and its slide the page they cite
  most; the figures file lists the other pages cited most. The method table says the frequency is the planned one.
- `check` also refuses a description slide with no excerpt, a deck whose excerpts all come from one assistant on questions
  several answer, the first person for the subject, an action with no site or on a site no answer cites, a request to be
  listed on a site the answers already cite, an action's reason its own slide does not draw, an action telling the reader to
  edit a page they do not own or asking a third party to check, an action dictating a fact the study does not record, a site not
  cited on the questions of the action's slide or by fewer than five answers, or one in twenty, there, a deck whose actions all ask third
  parties, two slides of the same rows, a row or an excerpt of a question with fewer than three answers, a deck with unfavourable
  answers and no excerpt of one, a count in an opening question, and a title saying what people think. It also refuses an
  opening example with too few answers or standing on two cards, a doubt quoted from a favourable answer, an amount no excerpt
  of its slide shows and no fact records, a site said to overtake another, the third party cited most with no action and no
  reason, an action named by its number, and favourable answers described as those naming the subject.
- An action on a third party carries `pages`: the page the answers cite, opened, with what it shows. `check` refuses a page the
  answers do not cite and one listing fewer than two others, and the slide prints what the page lists or the wrong figure it
  shows. A page that does not open is one the reader checks. A correction carries the same record on the subject's own pages,
  and at least one page in it shows the wrong figure: an answer citing a page does not mean the page holds that figure. A site
  the answers already cite can be asked for a listing once its page has been read and leaves the subject out.
- The playbook ends with an audit: a fresh agent checks every sentence against the figures and the answers, and reports what is
  false, overstated or left out. It runs on its own on a deck that passes.
- `monitor.py page --url <address>` prints what a page's HTML holds, title, description, tooltips and closed answers included, with
  no script of the site running: a web tool leaves those out, and an action said a page lacked what it showed. The playbook reads
  pages with it, and looks for old versions of a page still online. `history/deck/D.audit.md` holds an audit run by another
  agent: the writer works from it instead of starting one. The facts slide says "only an old figure": the count leaves out
  the answers giving both.
- The sources slide and the figures file say, for each site cited on the questions without the name, how many of the answers citing
  it name the subject: a site with many answers and few naming the subject is where an action belongs. `check` also refuses an
  action whose reason rests on one answer and a judgement given to the people asking. The card of a block sharing questions with
  another says they are among those of the other columns.
- The actions on the subject's own pages come first and the slide says so: the order no longer rests on a weight the reader
  cannot see. The count beside an action says which slide's questions it covers.
- The facts slide and the figures file say how many of the answers with today's figure also give an old one. A finding of two
  cards is set in larger type. Slide 2 says what favourable, unfavourable and neutral mean: unfavourable also covers an answer
  that does not find what the question's criterion asks.
- The playbook keeps an action's claim in the shorter title, tells a site's count from a page's, and no longer lets a site's count
  clear a page that many answers cite and that leaves the subject out. A page putting affiliated products first stays an action,
  and the deck says so of it.
- A wrong figure's slide prints every figure a page shows, and a page's line names what it lists and then the subject it leaves out,
  which stays true when the subject is only a related link there.
- The playbook asks to look at the subject's site before an action, and ends with a reader's test: a fresh reader sees only
  the PDF and must understand the first four slides.

## 0.3.0 (2026-11-05)

- The `deck` route turns a period into one slide deck for whoever decides, the only thing a client needs to read:
  what was found, what to do, the evidence block by block, the sources, the method on the last slide. `monitor.py
  deck` places each question in a block by its type (reach, description, facts) and writes
  `history/deck/<date>.figures.md`, the figures with the answers taken out, and `reports/<date>.deck.json`, the text
  to fill. The code draws the cover, tiles, charts, tables, sources and method table from the period, so a figure
  or a layout cannot be written wrong. `monitor.py check` on `.deck.json` refuses a deck with no action, an action
  with no evidence slide, a figure missing from the period, an excerpt not verbatim, attributed to another question
  or assistant, or cut inside a sentence with no mark, and a text longer than its slide holds. `monitor.py pdf
  --deck` writes 16:9 pages and refuses a slide that runs over its page. `check` also refuses a claim of all or
  nothing in place of a count, a page address neither cited by an answer nor recorded as a fact's source, the word "correct" for answers carrying the current fact, a score band named in words, a slide with an action
  and no excerpt, and a title citing a figure its chart does not draw; a facts row shows how many answers scored 4
  or 5. A fact a later project records with other terms no longer counts as current: its question moves to the
  description block, the figures file names the later record, and `check` refuses its term.
- The material prints "Who wrote the sources" on every dimension whose answers cite a source, when the study lists
  its competitors' domains, and no longer only when a competitor's page is cited; and it counts the answers naming
  each competitor, by dimension and by question (`foils` in each cell of the period). A period built earlier is built
  again with `period`.

- The share copy of a report whose period is a single day is named with that day once, not `(day to day)`.

- The recap table of `setup` counts credits per 30-day cycle, as Sentl bills from 2026-10-29: one figure
  per project (daily 30 runs, weekly 4.3, monthly 1), no worst month. The playbooks no longer say judging
  adds credits: a run costs the researcher models' credits, as `estimate-run-tool` returns.

## 0.2.0 (2026-10-29)

- `monitor.py pdf` writes the report in Sentl's look by default (white page, orange #FF850D and #B85C00, text
  #2C2C31, Sentl's mark embedded, no network). A theme replaces it: `--theme <file>`, the `theme` key of
  `study.json`, `theme.json` or `theme.css` in the study folder or in `~/.config/sentl-monitor/`; a JSON
  theme sets `colors`, `font`, `font_url`, `logo` and `footer`, a CSS theme overrides the `--sl-*`
  variables. The copy in `reports/share/` is the themed page. README: "Make it yours", the connectors that
  move the files, and the MCP server named "Sentl MCP" at `https://app.sentl.ai/mcp`.
- `monitor.py pdf` also writes the copy to send, `reports/share/<Subject> + Sentl.ai - monitoring
  report (<start> to <end>).pdf` (the page as `.html` when no PDF engine is installed), and the
  `report` and `snapshot` routes and the pack step attach that file instead of `reports/<date>.pdf`.
  Characters a file system refuses in the subject become spaces.
- The skill follows Sentl's MCP of 2026-10-29. `SKILL.md` opens with a table of what the operator
  may want and the route for each, and no longer repeats the tools' parameters, roles or limits.
  `snapshot` creates a snapshot in Sentl (`create-snapshot-tool`: no project slot, no schedule, one
  round) and ends by keeping it, deleting it with `delete-snapshot-tool`, or following the subject
  with `brief` and `design`; `monitor.py close` records `closed_at` and `how` (`kept`, `archived`
  or `deleted`) and `--deleted` needs no saved project. `setup` stops on `project_limit_reached`,
  offers archiving a project the operator names, and gains a step to stop a project with
  `archive-project-tool`. Errors are shown with their code and message; only the internal server
  error is called once more. A run that ends `stalled` is not charged and is triggered once more
  on a go. `get-project-tool`'s `kind` and `archived` are read; `payload` refuses an archived
  project. `monitor.py pdf` writes a report as a print-ready page and as a PDF when an engine is
  installed.

- `setup` ends its estimate step with a recap table: a row per project with its dimensions and
  question counts, the models with their credits per answer, the rounds with their frequency, and the credits per month as a median month
  with the worst month in parentheses (daily 30 and 31 runs, weekly 4 and 5, monthly 1 and 1).
- `snapshot <subject>` runs a small study of a subject on Sentl once, in a folder of its own, and
  leaves no project running. The playbook designs four or five dimensions from the catalogue
  with one question each, creates one project paused with no schedule, shows `estimate-run-tool`
  in credits, starts one run only on the operator's go, writes a report in its own order (what
  was done, the dimensions, the questions, the scoring, the findings, and what a single run
  cannot show), then pauses the project and gives the operator the panel link to archive it,
  since Sentl's MCP cannot archive a project. `validate`, `review`, `payload`, `bind`, `period`,
  `method` and `check` have a snapshot mode: `validate` refuses other than four or five
  dimensions, a dimension with other than one question, an unknown catalogue id, rounds above
  one and a schedule; `check` refuses a changes section and a figure for the whole project.
  `monitor.py resume` names the step a folder is at, from its files and the run listing, and
  `monitor.py close` records `closed` with `archive: operator` in `sentl.json`.
- `report` runs unattended when a scheduler starts it. `monitor.py pending` reads the run
  listings the assistant saved and records `nothing_new` when no completed run is new, so two
  invocations on the same runs write one report. `period` records `below_floor` when no run
  has 90% of its answers judged. `check --unattended` keeps a report that fails as
  `reports/<date>.draft.md`, counted as the previous report. `history/last-report.json` holds
  the outcome of the latest invocation: `written`, `draft`, `nothing_new` or `below_floor`. The
  README gives two recipes: a local scheduler starting a headless assistant with an API token,
  and a cloud scheduled agent whose study folder is a private repository.
- `setup` creates the study's projects in Sentl, paused, and saves their questions without
  cutting the link between a question and its past results. `monitor.py payload` prints the
  arguments of `create-project-tool`, `update-project-settings-tool` and
  `save-project-questions-tool` from `study.json`, every id taken from `sentl.json`; a new
  question or dimension is sent without an id, a dropped dimension is sent archived, a text that
  differs from Sentl's only by quotes or spacing is sent as Sentl has it, and `delete_missing`
  is never set. It refuses while a completed run has not been ingested (a run recorded as
  unavailable does not block) and when the project in Sentl differs from its latest recorded
  version. `bind` records the ids and a `setup` version from a saved `get-project-tool`
  response, and refuses a saved project that lacks a text of the latest run or does not hold
  `study.json`. The playbook asks for the operator's go before every write, dry run included,
  and starts a run or a schedule only after `estimate-run-tool`.
- `design` turns the approved themes into a study: dimensions taken from a catalogue
  (`design/catalogue.md`, with question patterns, rubric anchors, the facts each dimension needs
  and the stance and fidelity axes), projects, who asks, questions with 1-5 rubrics and a
  narrative. `monitor.py validate` refuses a study that breaks Sentl's field limits or the design
  rules (a dimension fed by no theme, an alias in a question marked as naming no brand, a
  dimension leaning one way in search without a question of the opposite framing, a malformed
  pair, duplicate keys or texts, a model Sentl no longer offers) and warns about the rest.
  `review` writes `study-review.md` with the narrative, the theme inventory, every question and
  rubric and a credit estimate from the models' tariffs. `revise` records each changed
  question as reworded (same key), new intent (new key, old key retired) or criteria.
- `brief <subject>` lists the themes to monitor with the origin of each, collects how people
  search for them and writes `brief.md`. `monitor.py demand` sends each seed query, as typed and
  with each question stem, to Google's suggestions (the skill's only network call; exit 1 lists
  the prefixes that failed), merges search volumes that a keyword-data server returned or that an
  export file holds, classes every keyword as subject, foil, component or generic, and prints
  each theme's summary. Volumes are stated for each class and never added across classes.
- The report's themes section gives each theme's distinct Google suggestions and, when a volume
  source was used, its monthly searches for each class; without one it says what the counts measure.
- `import` writes the project, the run listing and the runs of Sentl's run export into the
  study folder; `download` fetches the export's link first. The link is fetched with no
  credential, only over https from Sentl's own hosts, and a file over 64 MB is refused. Exit 7
  means the link does not answer.
- `ingest --pages` joins the pages of one run, each checked by its `content_sha256` (RFC 8785).
- A response that carries `question_id` is matched to its question by id; one without it, by text.

## 0.1.0 (2026-10-19)

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
