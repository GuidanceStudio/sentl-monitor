# quick deck

Turns one period of monitoring into a quick deck: a summary, the figures of the full deck topic by topic, each with one
sentence on what lies behind it and one passage of a real answer, and one to three suggested actions the reader can take
alone. It is for a reader who wants to know what the assistants say, topic by topic, or a first look while the full
deck (`report/DECK.md`) waits. Reads only: no Sentl write, no credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` the period's date (`YYYY-MM-DD`). Run every command
with `--study "$S"`. Exit 5 or 6 from any command: stop as `report/REPORT.md` says.

## The reader

The reader of the full deck (DECK.md, §The reader), with two minutes. Slide 2 is often all they read: the main finding,
then each project's figure and what lies behind it. Then a slide's title and each row: the topic, its figure, your
sentence, the passage. A row works when the sentence tells them something the figure does not, and the passage shows it
in an assistant's own words. The actions come last, after the evidence they rest on.

## What the code does and what you write

The code draws every slide from the period: the cover; slide 2, "In sintesi" ("In short"), with each project's name and
figure, its rows added up (with several projects, the caption of the favourable answers leaves out the subject, since the
figure is the project's; the answers naming the subject keep it); one slide per project, a second one when a project has more than six topics; one row per topic
with its figure; the slide "Azioni suggerite" ("Suggested actions"), which marks each action as work on the subject's own
pages or a check; and a last slide with the sites the answers cite most and how the answers were read. A topic whose questions name no subject shows the answers naming the subject, x of y, and the competitor named
most; any other shows the favourable answers, x of y, with a bar of favourable, neutral and unfavourable. You write only
the text in `reports/D.quick.json`, and you never change a figure the code draws.

| Field | What it holds |
|---|---|
| `summary.title` | The period's main finding, as a sentence the reader could repeat to their boss. At most 20 words and two figures |
| `summary.projects.<project>` | What the project's slides add up to, in one sentence of at most 25 words: never the figure the summary draws beside it (`check` refuses it and what it leaves of its total), nor the title of the project's slide again |
| `slides[].question` | The question the project answers, in the reader's words, ending with "?": "People looking for an oat drink without naming Avenello: which names do they find?". At most 120 characters |
| `slides[].title` | What the slide's rows say together, in one declarative sentence: where the figures are high and where they are low, and the one thing behind it. At most two figures, 160 characters |
| `rows[].says` | The fact behind the row's figure, from the answers. One sentence, at most 25 words and 170 characters |
| `rows[].excerpt` | `text`: one passage of one answer to a question of this topic, copied verbatim, at most 30 words; `question`: that question, as the figures file gives it; `assistant`: the assistant, as the figures file names it |
| `actions[].what` | One to three actions, in the order the reader should take them. Work on a page of the subject's own site, named by its domain, or a check the reader makes, starting with "Verificare" ("Check") and naming a site the answers cite. At most 20 words |
| `actions[].why` | The count of a row of this deck the action rests on, as the row draws it (x su y), and what the answers do there. At most 20 words |

## 1. Preflight

As DECK.md step 1: `doctor`, and on a host without a lasting folder `unpack` first. No period for the runs: follow
`report/REPORT.md`, which builds it and comes back here in its step 6.

## 2. Write the file to fill

```bash
python3 <skill>/scripts/monitor.py deck --quick --study "$S" --date D
```

It writes `history/deck/D.figures.md` and, the first time, `reports/D.quick.json`, with the slides and rows already set
and every text to write marked `[[...]]`. Run again, it keeps what is written; a quick deck written before the summary
and the actions existed (schema `quick@1`) gains them, marked `[[...]]`, and keeps its slides. Write one slide at a time
into the file, the summary and the actions last.

## 3. Read, one topic at a time

For each row, read in `history/deck/D.figures.md` the topic's figure, its questions' figures, the competitors the answers
name and the sites they cite. Then search `history/material/D.md` for the topic's answers; it is long, so never read it
whole. Look for what the figure alone hides:

- the question that pulls the topic's figure up or down, and what its answers say;
- the names the answers give instead of the subject, and where they give the subject;
- what the unfavourable answers are about, and whether they speak of the subject at all: an answer about a company with
  the same name, an old name, another city, a product the subject does not sell. With namesakes recorded in
  `study.json`, the bar already draws the answers about one as a part of its own, with its count: give that count where
  it explains the row, and never write that the measure is unreliable;
- a fact every answer repeats, such as a phone number, a price or a share, as the figures file states it.

## 4. Write

**`says`** gives one fact behind the figure, never the figure again (`check` refuses a count its row draws): "The unfavourable answers are about the price of
the 1-litre carton; on the barista version all 9 answers are favourable." Cite only the figures the figures file holds,
as they stand: the topic's, a question's, a competitor's count. `check` refuses any other count, and sums of your own. A
count you read in the answers yourself has no place in the deck: say what the answers do without it. A figure an
answer states, such as a price, a share or a phone number, goes in «» as the answer writes it: `check` finds it in the
answers and reads it as their words, not as a count. Write "all 9
answers" or "none of the 18" only where the figures file gives 9 of 9 or 0 of 18; `check` refuses "all", "none",
"never" and "always" anywhere else.

**`excerpt`** shows what `says` claims, in an assistant's words. Choose a passage that makes sense alone; mark a cut
inside a sentence with […], at the start, at the end or both, and keep whole any condition or comparison its meaning
rests on. Copy `question` and
`assistant` from the figures file. When the answers allow it, take the passages of one slide from more than one
assistant; when one assistant gives the only quotable answers on a topic, use them.

**`title`** reads the slide as a whole, as a plain sentence. **`question`** is the one the reader would ask, about their
own market: it names the subject, or says that the people asking do not name it.

**`summary`**, once the slides are written. The figures file gives each project's figure under "Slide 2: summary". The
title says the one finding the reader should keep, across projects. Each project's sentence says what its slides add up
to: where the answers fall short and why, or which names they give instead of the subject. It gives a fact the figure
does not: a part of it a row draws, a competitor, a topic. On slide 2 the title and the projects' sentences hold at most
70 words together; the names and figures the code draws are not counted. Over that, `check` names the longest texts.

**`actions`**. The quick deck reads no page, so each action is one the reader can take from what the answers show, without
asking anyone. Find them in the rows you wrote, in this order:

- an unfavourable row on the subject: what the answers miss or get wrong, which a page of the subject's own site can
  say (the figures file lists its domains): a price, a condition, where it sells, what happens in a case the answers
  cannot find described;
- a row where the answers describe a namesake or an old name: a page of the subject's own site that says who it is;
- a row of questions that name no subject where it is missing: a page of its own site on what people ask there, beside
  the names the answers give; or a check of the site those answers cite most, starting with "Verificare" ("Check"),
  such as whether a list the answers cite names the subject.

Each `why` gives that row's count, as the row draws it: "Fuori dal Veneto 5 risposte su 28 sono sfavorevoli". `check`
refuses a request to a third party ("chiedere a", "contattare", "segnalare a", "ask", "contact the owners"), work on a
site the subject does not own unless the action is a check, a check of a site no answer cites, a competitor's site, an
action naming no site, and a `why` with no count of a row. Requests to third parties belong in the full deck, which
reads their pages first.

The full deck's rules on words hold here (DECK.md step 5): no word about how the deck was made (ratings, scores, blocks,
dimensions, the code), no first person, no slogan, nothing the answers do not say, and never the model that rates the
answers. A competitor is named as the answers name it.

## 5. Check and print

```bash
python3 <skill>/scripts/monitor.py check --study "$S" reports/D.quick.json
python3 <skill>/scripts/monitor.py pdf --study "$S" --date D --quick
```

`check` names every text it refuses and why: fix it and run `check` again. A row runs over its slide when its sentence
and passage together are too long: shorten the passage first. A quick deck that passes is the record of its period in
`history/reports.json`, as a full deck is: the next period starts after its runs. `pdf` writes `reports/D.quick.html`
and `.pdf` and the copy to send in `reports/share/`; on a host without a lasting folder, then `pack` as DECK.md step 9
says.

Open the PDF and read it once as the reader: each title against its rows, each sentence against its passage.

## 6. Tell the operator

Where the copy to send is, how many slides it has, and its suggested actions in one line each. The full deck of the same
period can follow at any time with `deck` and DECK.md: it reads the same figures and the pages the answers cite, and
`reports/D.quick.json` stays as it is. The quick deck's actions are no earlier edition of the full deck's.
