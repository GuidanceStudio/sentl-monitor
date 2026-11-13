# quick deck

Turns one period of monitoring into a quick deck: the figures of the full deck, topic by topic, each with one sentence
on what lies behind it and one passage of a real answer. No actions. It is for a reader who wants to know what the
assistants say before deciding whether to act, or a first look while the full deck (`report/DECK.md`) waits. Reads
only: no Sentl write, no credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` the period's date (`YYYY-MM-DD`). Run every command
with `--study "$S"`. Exit 5 or 6 from any command: stop as `report/REPORT.md` says.

## The reader

The reader of the full deck (DECK.md, §The reader), with two minutes. They read a slide's title, then each row: the topic,
its figure, your sentence, the passage. A row works when the sentence tells them something the figure does not, and the
passage shows it in an assistant's own words.

## What the code does and what you write

The code draws every slide from the period: the cover; one slide per project, a second one when a project has more than
six topics; one row per topic with its figure; and a last slide with the sites the answers cite most and how the answers
were read. A topic whose questions name no subject shows the answers naming the subject, x of y, and the competitor named
most; any other shows the favourable answers, x of y, with a bar of favourable, neutral and unfavourable. You write only
the text in `reports/D.quick.json`, and you never change a figure the code draws.

| Field | What it holds |
|---|---|
| `slides[].question` | The question the project answers, in the reader's words, ending with "?": "People looking for an oat drink without naming Avenello: which names do they find?". At most 120 characters |
| `slides[].title` | What the slide's rows say together, in one declarative sentence: where the figures are high and where they are low, and the one thing behind it. At most two figures, 160 characters |
| `rows[].says` | The fact behind the row's figure, from the answers. One sentence, at most 170 characters |
| `rows[].excerpt` | `text`: one passage of one answer to a question of this topic, copied verbatim, at most 40 words; `question`: that question, as the figures file gives it; `assistant`: the assistant, as the figures file names it |

## 1. Preflight

As DECK.md step 1: `doctor`, and on a host without a lasting folder `unpack` first. No period for the runs: follow
`report/REPORT.md`, which builds it and comes back here in its step 6.

## 2. Write the file to fill

```bash
python3 <skill>/scripts/monitor.py deck --quick --study "$S" --date D
```

It writes `history/deck/D.figures.md` and, the first time, `reports/D.quick.json`, with the slides and rows already set
and every text to write marked `[[...]]`. Run again, it keeps what is written. Write one slide at a time into the file.

## 3. Read, one topic at a time

For each row, read in `history/deck/D.figures.md` the topic's figure, its questions' figures, the competitors the answers
name and the sites they cite. Then search `history/material/D.md` for the topic's answers; it is long, so never read it
whole. Look for what the figure alone hides:

- the question that pulls the topic's figure up or down, and what its answers say;
- the names the answers give instead of the subject, and where they give the subject;
- what the unfavourable answers are about, and whether they speak of the subject at all: an answer about a company with
  the same name, an old name, another city, a product the subject does not sell;
- a fact every answer repeats, such as a phone number, a price or a share, as the figures file states it.

## 4. Write

**`says`** gives the fact behind the figure, never the figure again: "The unfavourable answers are about the price of
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

Where the copy to send is, how many slides it has, and that it holds no actions. The full deck of the same period can
follow at any time with `deck` and DECK.md: it reads the same figures, and `reports/D.quick.json` stays as it is.
