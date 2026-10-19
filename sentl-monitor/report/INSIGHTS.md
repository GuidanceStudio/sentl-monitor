# Insights

A dimension's mean says how favourable the answers are. The insights below say why a figure
is what it is and what the client can correct. `monitor.py period` computes each one, and the
material prints it under its own heading only when the period has it. Every insight the
material holds goes in the findings entry of its dimension; every dimension still gets its
entry. Presence changes compare two periods and are written in the changes section, where an
episode or a fact share may also be cited to explain a change called.

Each insight is stated in one plain declarative sentence that carries the figure, copied as the
material prints it ("N of M answers", whole percentages, means with one decimal in the report's
language). `check` verifies these figures like any other. The examples use Avenello, a
fictional oat-drink brand, and Avoria, a fictional competitor; they are in English, and a
report states them in its own language.

## Fact currency

**What it shows.** Whether the answers state a fact as it is now or as it was: a price, a fee,
the person in charge. The study lists, under a question's `facts`, the `current` and the
`outdated` terms as answers write them ("2,10 €", "1,90 €").

**Figures.** Material heading "Fact currency": the answers stating a term out of the answers
given; then, out of those stating a term, the answers with a current term only, an outdated term
only, both, and a current term at all; for all assistants, for each assistant and for each run.

**How a finding states it.** "In 33 of 42 answers that quote a price, the price is last year's
(79%)." "Orbit Reason gives the current price in 9 of 21 answers (43%); Acme Chat in 0 of 21."
A term named in the report is quoted in «», as it is listed: "the current price, «2,10 €»,
appears in none of the answers". `check` reads a listed term inside «» as text, so a price no
answer gives can be named; outside «» it is a figure and must be one of the period's.

**Limit.** Only the listed terms count, matched as text: an answer that gives the price in
another form (per 100 ml, rounded) states neither term. A term never matches inside a longer
number ("10 €" in "12,10 €"), and a space between a number and its currency sign is optional.

## Sources behind a fact or a score

**What it shows.** The pages that travel with an outdated fact or a low score, and those that
carry the current fact or a high score. Four groups of a question's answers: those stating only
an outdated term, those stating a current term, those scored 1–2 and those scored 4–5. For
each group, the five domains cited by most answers of the group, each with its share in the
opposite group (outdated against current, 1–2 against 4–5), so a page that one group cites and
the other does not stands out.

**Figures.** Material headings "Sources behind the fact" and "Sources behind the score": per
group, one line per domain, "N of M (P%)" in the group and in the opposite group, where M is
the group's answers that cite at least one source; answers citing nothing are in no share. A
pair of groups is listed only when both groups have an answer citing a source, so a question
whose answers all score 4–5 has no score lists, and every domain carries a share in the
opposite group.

**How a finding states it.** It states the top domains of the group that matters: "The pages
cited most by the answers that give last year's price are prezzi.example and
recensioni.example, each in 33 of 33 answers (100%); among the answers that give the current
price, 0 of 9 cite them (0%)."

**Limit.** A citation is not a cause: an assistant can cite a page and state something else.
The lists rank by how many answers cite a domain, so a site that one assistant retrieves often
can lead a list; its share in the opposite group shows whether it belongs to the fact or the
score at all.

## Readings

**What it shows.** How many independent readings the answers rest on. The rounds of one run
that cite the same ordered list of pages (query strings left out; a grounding redirect counts as
the domain its title names) are one reading, not several.

**Figures.** In each figure line of the material, "resting on R readings of G answers", shown
only when the readings are fewer than the answers.

**How a finding states it.** "Avenello is named in 12 of 42 answers (29%); the figure rests on
14 readings of 42 answers, since the three rounds of each run cite the same pages."

**Limit.** One list of pages can still produce answers that differ; the count says how
independent the answers are, not that they are identical.

## Episodes

**What it shows.** A movement inside a period that its mean averages away: a question's mean,
or the share of its answers stating a current term, that lies outside the range of the runs
before it for three runs or more in a row, on the same side. The range is that of the earlier
runs of this period and of the previous one, at least five of them, on the assistants every
one of those runs has and leaving out the runs judged under other criteria for the question; a
first report reads its own earlier runs. The episode closes at the first value back inside the
range; a value that jumps to the other side ends it as a switch. The close date is the first run
back inside the range; it says nothing about the runs after it. What those runs show is read from
the by-run figures, and a later run may lie outside the range again without making a new episode.

**Figures.** Material heading "Episodes": the measure, how many runs, the first and last date,
each value, the range and the number of runs it rests on, and the date it closed or switched.
Under a closed episode, "still above (or below) that range after the close" lists the later runs
of the period on the episode's side of that range, with their values. For a question shown
without a figure the mean episode carries no values.

**How a finding states it.** "From 6 to 8 October the answers giving the current price were
50% each day, against 0% in the eight runs before; on 12 October they were back inside that
range." The close is stated as that one date. When the material lists later runs on the
episode's side, the finding states them as well ("on 11 October the current price was in 50% of the answers again, and on 15 October in all of them") and never says the measure was outside the
range only during the episode. `check` refuses a word for "only" (only, solely, exclusively,
just; solo, soltanto, solamente, unicamente, esclusivamente) that comes before a closed episode's
span, first, last or close date in the same clause, while later runs lie on its side and the
sentence does not name all of them.

In the changes section, an episode that explains a change called is given beside it
with its first date, when it lies on the side the change moves to and runs in the later period
or half: "The current price is given in 42% of the answers that quote a price,
against 0% in the first half of the month; the rise starts on 21 October."

**Limit.** It needs at least five earlier runs, so it shows with daily or frequent runs; an
episode says when the answers moved, not why.

## Presence by run

**What it shows.** For a question that does not name the subject, in which runs the subject was
named and in which it was not.

**Figures.** Material heading "Presence by run": per run, "subject named in N of M answers
(P%)".

**How a finding states it.** "Avenello is named in 0 of 6 answers each day until 12 October and
in 6 of 6 answers on 13 and 14 October."

**Limit.** A run holds few answers; one run alone shows little.

## Missing evidence

**What it shows.** Answers in which the assistant says it found no source of the kind the
question asks for (lab tests, a price list), and the assistant's mean with and without
them, so a drop they account for is reported as missing evidence, not as a change in what is
said.

**Figures.** Material heading "Missing evidence": per assistant, "N of M answers (P%) say no
source of the kind asked for was found; mean X with them, Y without". The means are left out
for a question shown without a figure.

**How a finding states it.** "In 12 of 21 answers Acme Chat says it found no lab tests;
its mean is 3.4 with these answers and 4.0 without."

**Limit.** A phrase list per market language finds them, anchored on the assistant's own
search ("I could not find", "in the provided results", "no lab tests were found"); an
assistant that says so in other words is not counted. A sentence whose subject is a third
party ("customers say they could not find…") reports that party's experience and is not
counted. The answer never says why the evidence was missing.

## Who wrote the sources

**What it shows.** Whether the cited pages are the subject's own, a competitor's or a third
party's, and which competitor pages are cited most. The study lists, under each foil, the
`domains` it owns; subdomains count as the same author.

**Figures.** Material heading "Who wrote the sources", per dimension, shown when a competitor's
pages are cited: the answers citing owned, a competitor's and third-party pages, each out of the
answers citing any source; then the competitor pages most cited, with how many answers cite
each.

**How a finding states it.** "On which oat drink to buy, Avoria's own pages are cited in 42 of
42 answers that cite a source (100%), most of all its comparison page."

**Limit.** Only the listed domains count as a competitor's: a page it commissioned on another
site counts as third party.

## Presence changes

**What it shows.** For a question whose presence changed since the previous period, the domains
cited by the answers naming the subject now and by no answer to the question before, and the
reverse: the pages that brought the subject into the answers, or whose disappearance went with
it leaving them.

**Figures.** In the material's changes part, heading "Presence changes": the five domains cited
by most answers in each list, ties broken by name, each with the answers citing it.

**How a finding states it**, in the changes section: "Avenello is named in 29% of the answers on
which oat drink to buy, against 0% in the previous period; the answers that name it cite
classifica.example, which no answer cited before."

**Limit.** It shows which pages arrived with the subject, not that they brought it.
