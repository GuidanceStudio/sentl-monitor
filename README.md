# sentl-monitor

A skill for coding assistants that runs a monitoring study on [Sentl](https://app.sentl.ai):
it helps a consultant design the study, sets it up in Sentl through Sentl's MCP server, and
writes a dated report after each period of runs, comparing it with the previous ones.

Sentl measures how AI models describe a subject. A Sentl project asks its questions to
several researcher models, a judge scores each answer from 1 to 5 against a rubric written
for that question, and each run produces a score. This skill decides what to ask and why,
puts it in Sentl, and turns the runs into reports. It makes no model calls of its own.

**Status: design.** This repository holds the design ([ARCHITECTURE.md](ARCHITECTURE.md))
and the development plan ([DEVPLAN.md](DEVPLAN.md)). There is no code yet.

## Who it is for

A consultant or an in-house analyst who monitors what AI assistants tell people about a
brand, a product category, a production method or an organisation, and who reports on it
to a client or to management every week or month.

## Routes

| Route | What it does |
|---|---|
| `brief <subject>` | Lists the themes to monitor with their origin (the client's material, the issues the client raised, the client's other analyses, Google searches) and collects search demand → `brief.md`, `search-demand.json` |
| `design` | Derives the dimensions from the themes, groups them into projects, decides who asks, writes the questions as people type them and a 1–5 rubric for each → `study.json`, `study-review.md` |
| `setup` | Creates or updates the Sentl projects, shows the credit estimate, and starts a run or activates the schedule only on your explicit go |
| `adopt <project>` | Takes a project that already exists in Sentl into a study folder, so it can be reported on |
| `report` | Reads the new runs, compares them with the previous period, and writes `reports/<date>.md`; meant to run on a schedule |

Each route writes files that the next one reads. Nothing is written to Sentl without your
approval.

## Requirements

**A Sentl account.** Creating projects and starting runs needs the Owner or Admin role in the
organization; the User role can only run `adopt` and `report`. Organizations and
subscriptions are managed in the Sentl web panel.

**The Sentl MCP server connected to your assistant.** In Claude Code:

```bash
claude mcp add --transport http sentinel-reputation https://app.sentl.ai/mcp/reputation
```

then run `/mcp`, select `sentinel-reputation` and sign in through the browser (OAuth). Codex
CLI, Gemini CLI, VS Code, Cursor and other clients are covered on the setup page,
https://app.sentl.ai/mcp/setup. For a client without OAuth, or for scheduled reports run by a
headless assistant, create a token in Sentl under **Integrations → API Tokens** and pass it as
an `Authorization: Bearer` header; the setup page shows the configuration. The skill never
asks for the token and never stores it.

**Python 3.10 or later**, standard library only (the scripts arrive with the first milestone).

**Optional: a keyword-data source.** Sentl gives no search data. Without a key, the skill
collects Google autocomplete suggestions in the market's language and country. When a
keyword-data MCP server is connected (Mangools is one; any server that returns monthly volume
and related searches for a location and a language works), or when you supply an export file
from such a tool, the skill adds monthly volumes and related searches. Without one, the skill
tells you, and the report says that suggestion counts measure how many ways a theme is
phrased, not how many people search it.

## What it costs

Sentl credits, and nothing else. A run costs, for each researcher model, its credits per call
times the questions times the rounds, plus the credits for judging the answers. `setup` shows
Sentl's estimate (`estimate-run-tool`) and the credits available before any run starts. A
schedule repeats that cost at every run: a weekly project runs about 52 times a year.

The `report` route only reads and spends no credits. Google autocomplete is free. A
keyword-data server uses its own quota.

## Walk-through on a fictional subject

Avenello is a fictional Italian brand of oat drink. Its marketing team wants to know what AI
assistants tell people in Italy who ask about oat drinks and about Avenello, and to follow it
every month.

1. **`brief Avenello`.** You give the skill the brand's positioning deck, a summary of
   customer-service questions and a social-listening report. It lists the themes each one
   raises, with the document it came from: sugar content (customer service), gluten (customer
   service), environmental footprint (positioning deck), price against cow's milk
   (social-listening report). It then sends seed queries to Google autocomplete in Italian for
   Italy, each also followed by question stems (*è, fa, come, perché, quanto, quale*), and
   finds two themes the client never raised: whether oat drink is bad for your health, and
   whether it suits children. With a
   keyword-data server connected it adds monthly volumes, and keeps two sums apart: queries
   that name Avenello, and queries about oat drink alone (*latte d'avena fa male*). It shows
   you `brief.md` and stops.

2. **`design`.** From the themes it proposes two projects. *Avenello by name* has six
   dimensions (Health, Sugar, Gluten, Environment, Price, Children) whose questions name the
   brand and are read by their mean score. *Oat drinks without a brand* asks about five of the
   same themes without naming any brand, and is read by how often Avenello appears and
   where. Who asks: personas, because a parent, a coeliac and a runner ask different
   questions. The health searches lean one way (*fa male*), so the Health dimension also gets
   the opposite question (*fa bene*). Each
   question gets five anchors; on the unbranded questions, 2 means Avenello is not mentioned
   and 1 means it is advised against. The research question is neutral: what are people who
   ask an AI assistant about oat drinks told about them and about Avenello. You read
   `study-review.md`, change two questions, and approve.

3. **`setup`.** The skill creates the two projects in Sentl, paused, saves the dimensions and
   questions (a dry run first), and shows the estimate for four researcher models, one round,
   a run every week. A monthly report then pools four runs, so every question has four
   answers from each assistant. You say go: it activates the weekly schedule and starts the
   first run.

4. **`report`, first time.** After the first month of runs, the report opens with what was
   done and to what end, where the themes came from, the dimensions and how they were
   reached, the questions, and how the answers are scored. Then, dimension by dimension, what the person asking is
   told, with verbatim answers (question and assistant) and the sites those answers cite. The
   last section says this is the first measurement and the next report compares against it.

5. **`report`, every month after.** The same report, with the last section filled: the
   dimensions whose score moved outside the range of the previous months, the answers that
   changed verdict, the sites that started or stopped being cited, and any change to the
   questions, the criteria or the assistants in the period, with how it affects the
   comparison.

## How it relates to sentl-snapshot and llm-rep

**sentl-snapshot** is a one-off brand snapshot: 4–5 dimensions, one question each, two
low-cost models called through OpenRouter, a short PDF in a few minutes, and a batch mode for
lists of brands. It needs an OpenRouter key and no Sentl account. sentl-monitor needs a Sentl
account, runs on Sentl's credits, and keeps a history across runs. This design keeps them
separate: the snapshot serves prospects and outreach, the monitor serves clients under
contract. sentl-monitor reuses the snapshot's dimension catalogue as its library of rubric
anchors and its idea of a rubric per question.

**llm-rep** runs a full study itself: it calls the models through OpenRouter with replicates,
judges the answers with its own judge, analyses them and hands off to a deck. sentl-monitor
reuses its method: the theme inventory with origins, the choice of who asks (generic
consumer, personas, stakeholders or a mix) with a reason, questions paired in positive and
negative, rubric anchors, and the order in which a study is presented. Sentl replaces its
run, judge and analysis stages.

Neither skill is required to use this one.

## Repository layout (planned)

```
README.md              this file
ARCHITECTURE.md        stages, files, schemas, MCP mapping, history model, gaps
DEVPLAN.md             milestones
install.sh             installs the skill for Claude Code and opencode
sentl-monitor/         the skill payload
  SKILL.md             router
  brief/BRIEF.md       route playbooks, one per route
  design/DESIGN.md
  design/anchors.md    rubric anchor library
  setup/SETUP.md
  adopt/ADOPT.md
  report/REPORT.md
  scripts/monitor.py   search demand, validation, Sentl payloads, ingestion, comparison, checks
tests/                 bash contract tests, Python unit tests, opt-in live tests
```

Study folders hold client data and live outside this repository.
