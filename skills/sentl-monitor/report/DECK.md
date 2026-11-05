# deck

Turns one period of monitoring into one short slide deck for the person who decides what a brand, an
organisation or a category does about it. The deck is the only thing the reader receives: no attachment and no
second file. Reads only: no Sentl write, no credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` the period's date (`YYYY-MM-DD`). Run every command
with `--study "$S"`. Exit 5 or 6 from any command: stop as `report/REPORT.md` says.

## The reader

A marketing or communication lead with little time. They read the first slides and decide whether to go on. They
want simple insights and a list of suggested actions first, then the means to go deeper. They stop reading at
repeated statistics or at scores with no meaning. They will forward slides 2 and 3 to their boss.

## What the code does and what you write

The code places each question in a block and draws the cover, the tiles, the charts, the tables, the sources, the
method table and every label, from the period. You write only the text in `reports/D.deck.json`. You never write
HTML, and you never change a figure the code draws: a figure that looks wrong goes to the operator.

| Block | The reader's question | A question belongs here when | The block's figure |
|---|---|---|---|
| `reach` | Do they find it? | it names no subject | named in x answers of y |
| `facts` | Are the facts right? | it names the subject and has recorded facts | answers carrying the current fact, x of y |
| `description` | What do they say? | every other question | answers scored 4 or 5, x of y, and the mean out of 5 |

A question naming no subject stays in `reach` even with recorded facts, and its fact also shows in `facts` when an
answer states it. A category or a method as subject has no presence to measure: `reach` is empty. A block appears
only if it has questions. The deck's slides, in order: cover, what we found, what to do, the blocks, sources, method.

## 1. Preflight

```bash
python3 <skill>/scripts/monitor.py doctor --study "$S"
```

No file in `history/periods/` for the runs to report: follow `report/REPORT.md` up to the step that builds the
period, then come back here. A period built by an earlier version of the skill: `deck` says so; run `period` again
with the same date and `--models inbox/models.json`.

## 2. Place the questions

```bash
python3 <skill>/scripts/monitor.py deck --study "$S" --date D
```

It writes `history/deck/D.figures.md` and, the first time, `reports/D.deck.json`, the text you fill. Run it again
after changing `moved` or `same_audience`: it keeps what is written.

Read `history/deck/D.figures.md` whole. `history/material/D.md` holds the same figures with every answer: it is
very long, so never read it whole. Search it for the question or the term you need.

Two settings of `reports/D.deck.json` are yours:

- `same_audience`: `true` when the projects differ in what they measure and address the same people in the same
  market, as `narrative.audience` shows: the usual case, and the reader then sees one figure per block. `false` when
  the study splits its projects by audience or market, such as a project per country or per customer segment: each
  project keeps its figure, because audiences and markets are never added up.
- `moved`: `{"<question key>": "description"}` for a question that names no subject and scores a position in a debate
  rather than whether the subject is found. Move nothing else.

## 3. Find the results

Read in `material` every answer scored 1 or 2 on a question naming the subject, then the answers behind the lowest
and the most surprising figures. Look at what those answers describe and at the domains they cite: an answer about
a company with a similar name is `confused`, whatever its score. Give each result one class:

| `class` | What the answers do | What to do, in general |
|---|---|---|
| `not_named` | The subject is absent from a question about its field | Get listed on the comparison pages the models use, or publish a page that answers the question |
| `named_by_name_only` | Described well by name, absent from the matching open question | Put the case on the category pages the models use |
| `passed_over` | Named, and a competitor is chosen over it | State the grounds of the comparison in public, with facts |
| `no_information` | The answer says it found no details on the subject | Publish the missing details where they can be read |
| `named_with_warning` | The answer raises a doubt or advises against | Correct the subject's own pages, ask the owners of the others to update theirs |
| `wrong_fact` | The answer contradicts a fact recorded in `study.json` | Put the current figure and its date on the subject's page, ask the publishers the models use to update theirs |
| `confused` | The answer describes someone else | Make the identity clear on the subject's own pages; ask for a correction only on a page that mixes the two |
| `holds` | The answers are favourable and correct | Keep it: one line in the block, no action |

`passed_over` needs answers that actually choose. An answer saying the choice depends on the need or the stage does
not pass the subject over: say that it splits the choice, and on what. A verb like "prefer", "choose" or "send to" comes
from reading the answers, condition included. If the answers say "a competitor at first, the subject once volumes
grow", write that, not "they choose the competitor". A count from a score band means what the question's rubric says
for those scores: read the rubric before you name it.

A page on the subject's own domains is the subject's, whatever the answer calls it: an answer naming the subject's
API or help pages as "a different service" is describing the subject. `confused` is what the answer attributes to
someone else, and the costs, terms or features it reports as theirs.

## 4. Choose the actions

Write three to five actions, in `actions`. Rank them by how many answers and how much of the reader's stated purpose
(`narrative.purpose`, each project's `decision`) they touch. If `themes` or `search-demand.json` carry search volumes,
use them to break ties.

Each action has:

- `class`: the result it answers;
- `what`: what to do and where, naming the pages or domains the answers cite;
- `rests_on`: the figure it rests on;
- `read_next`: the figure to read in the next report, with its value today;
- `block`: the block whose slide holds the evidence. Set that slide's `action` to the action's number.

Every `wrong_fact` and `confused` result that qualifies takes a place among the actions, ahead of the last of the others:
an assistant stating a wrong fact or describing someone else is what the reader can correct first.

An action needs at least three answers behind it, from more than one assistant or more than one question; `wrong_fact`
and `confused` need two, since an error can be checked and a view cannot. A result resting on fewer goes in the notes
to the operator.

The places to act are the subject's own pages and third parties' pages: the figures file lists the third parties the
answers cite. A competitor's site is a place to read, never one to act on, and `check` refuses it. An action says what
to publish and leaves the content to the subject: it states as fact only what `study.json` records, however many
answers say it. Never assign an action to a department of the client. Never promise an outcome. A page an answer cites
did not necessarily cause it: write "cited", never "caused".

Ask a third party to correct a page only when the answers show that page saying something false about the subject. A
page about another company with a similar name is right as it stands, and its address usually carries that name: the
action then stays on the subject's own pages. Name a page by its domain, or by an address the answers cite: `check`
refuses an address no answer cites.

## 5. Write the text

| Field | What it holds |
|---|---|
| `found.title` | The single most important finding, as a full sentence |
| `found.points` | One to four sentences with what matters, at least one saying what holds |
| `actions_title` | Which action comes first and why, as a full sentence. It never announces the list |
| `blocks.<block>` | One slide, or two when the block supports two or more actions |
| `slide.title` | What the block found. `slide.read`: the one or two sentences the chart does not say |
| `slide.dimensions` | The dimensions this slide draws; empty draws them all. Across a block's slides every dimension is drawn. Put together only what one title can say |
| `slide.rows` | `dimensions`, or `questions` to draw one row per question. A slide on one or two dimensions draws their questions anyway |
| `slide.excerpts` | At most two, each `{"text", "question", "assistant"}` |
| `slide.action` | The number of the action this slide supports, or `null` |
| `sources.title`, `sources.read` | Which pages form the answers and which of them matter for the actions |
| `method.limits` | Only a limit that changes what the reader may conclude, such as a question type not measured |
| `method.ask` | Two or three questions the reader can put to Claude or ChatGPT through Sentl's connector about these results |

In a large study, group what the slides show and give excerpts only to what supports an action.

**Titles.** Plain declarative sentences that say the finding. A title stays true when read beside its own figure: never
"not found: 14 of 90", which says the opposite of its number. A number in a title says what it counts ("named in 14
answers of 90"). A title claims no more than its evidence: "preferred" only for answers that choose. A title holds for
every row its slide draws: when a row says otherwise, name the rows the title speaks of, or give them a slide of their
own. "Behind" or "ahead" holds only where the comparisons go that way, each of them. No slogans, no
rhetorical questions, no metaphors, no contrast built for effect. Delete any sentence that loses no information when
removed. The reader calls this document a report: never write "deck".

**Figures.** Cite only the figures `history/deck/D.figures.md` holds, as they stand: `check` refuses any other, and sums
of your own. A figure belongs to what it counts: a dimension's figure carries the dimension's name as the chart shows
it, a question's figure the question. Never give a dimension's count to one of its questions, and never call a
dimension a question: it is a theme, as the chart says. Write small figures as "x of y". A score band reads as the chart
writes it, "score 4 or 5", and `check` refuses any other name for it. A facts row carries the question's scores as well:
when the fact is right and the answers are weak, say how many scored 4 or 5. A figure per assistant only when the difference between assistants is
itself the finding. For `reach`, lead with presence and leave the mean out. A price or term from `facts` goes in «»,
so it is read as a term and not as a figure.

**Excerpts.** Copied verbatim from `material`, at most 40 words, with `[…]` where you skip or cut. An excerpt keeps
the meaning of the sentence it comes from: a condition or a comparison stays whole, including its "if", "while" or
"but". Read the sentence before it and the sentence after it first. An excerpt that loses its condition says what
the answer does not say. Give the question as `figures` writes it and the assistant's name.

**Framing.** Neutral. State what holds as well as what does not. A sentence about a set holds for the whole set: if one
comparison of three goes well, write two of three and name the third. Say how many, in words the figures hold: `check`
refuses "none", "all", "never", "absent" and their like in titles, points and reads, since what the answers say is a
count. Read every answer of a question before you say what they do, and count them. Call a fact wrong only against the facts in
`study.json`; otherwise say the answers diverge. A competitor being preferred is a result, not an error of the answer.

**Never mention** the model that scores the answers, run or question ids, model ids, credits, readings, unstable pairs,
scores with and without a given answer, comparisons of pages cited by high and low scored answers on fewer than 5
answers, or anything about how the deck was built.

Write the text in the study's `report_language`. An answer whose score and fact disagree (a score of 4 or 5 on an
answer stating an outdated term) counts by its fact in the deck, and goes in the notes to the operator.

## 6. Check and render

```bash
python3 <skill>/scripts/monitor.py check --study "$S" reports/D.deck.json
python3 <skill>/scripts/monitor.py pdf --study "$S" --deck --date D
```

`check` refuses a deck with no action, an action with no evidence slide, a figure missing from the period, an excerpt
not verbatim, attributed to another question or assistant, or cut inside a sentence with no mark, a text longer than
its slide holds, a claim of all or nothing, an address no answer cites, and the words the deck must not carry. Fix the
text and run it again until it passes. Never fix a failure by changing a figure drawn by the code.

`pdf --deck` refuses a deck that fails `check` and a slide that runs over its page, and names the slide: shorten its
text. It writes `reports/D.deck.pdf` and the copy to send, in `reports/share/`. On a host without a lasting folder,
end as SKILL.md says, with the deck's PDF in place of the report.

## 7. Tell the operator

In the chat, never in the deck: where the copy to send is, the choices open to doubt, anything in the data that looks
wrong, and the results left out for resting on too few answers. The operator sends the deck: never send it yourself.
