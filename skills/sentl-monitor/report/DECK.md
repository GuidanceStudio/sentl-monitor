# deck

Turns one period of monitoring into one short slide deck for the person who decides what a brand, an
organisation or a category does about it. The deck is the only thing the reader receives: no attachment and no
second file. Reads only: no Sentl write, no credit spent.

`<skill>` is this skill's directory, `$S` the study folder, `D` the period's date (`YYYY-MM-DD`). Run every command
with `--study "$S"`. Exit 5 or 6 from any command: stop as `report/REPORT.md` says.

## The reader

The marketing manager of the company the deck is about. They know their market, their products and their competitors.
They know the company monitors what AI assistants say about it, and that is all: they have never seen the questions,
the ratings or the project names. They have five minutes. The first four slides must be enough for them to tell their
boss what was done, what was found and what to do. If they cannot say what a slide is about, the deck has failed,
however true each sentence is.

So every sentence you write passes one test: read it to that manager out loud. If they would answer "what questions?",
"what do you mean?" or "so what?", rewrite it.

## What the code does and what you write

The code places each question in a block and draws the cover, the cards, the charts, the tables, the sources, the method
table, the list of questions and every label, from the period. You write only the text in `reports/D.deck.json`. You
never write HTML, and you never change a figure the code draws: a figure that looks wrong goes to the operator.

| Block | The manager's question | A question belongs here when | The block's figure |
|---|---|---|---|
| `reach` | Do people who ask without naming the subject find it? | it names no subject | named in x answers of y, beside the competitors the same answers name |
| `description` | What do people who ask about the subject hear? | every other question | favourable answers, x of y |
| `facts` | Are the subject's facts right? | it has recorded facts, and stays in its own block too | answers stating today's figure, x of y |

A question with recorded facts counts in its own block and shows in `facts` as well, so a topic's figure never leaves out
its hardest question. A question naming no subject shows in `facts` only when an answer states the fact. A category or a
method as subject has no presence to measure: `reach` is empty. A block appears only if it has questions.

The deck's slides, in order, for every client:

1. **Cover**: what was done, in one sentence, who prepared it, and whether this is the first reading.
2. **What this report shows**: the purpose, the two or three questions the report answers with real examples, and how to read a figure.
3. **What we found**: the same questions in the same order, each with its answer and its figure.
4. **What to do**: three to five actions, each with its reason.
5. **The evidence**, block by block: each slide carries the question it belongs to, and shows the real answers.
6. **Where the assistants read**, the sources.
7. **How the reading was made**, the method.
8. **The questions**, all of them.

A deck that follows a final deck has two more slides after **What we found**: **What changed** and **The actions proposed** (§The second edition, in step 5).

## 1. Preflight

**Keep your work on file.** A long session gets compacted, and what you read and did not write down is lost. Keep `history/deck/D.notes.md`: after each step write what you found, each page you read and what it holds, each action you decided and why. When the file exists as you start, you are resuming: read it and `reports/D.deck.json` first, read this playbook once, and go on from where the notes stop. Go back to the material only for what the notes do not hold. As soon as the actions stand, fill `reports/D.deck.json` with what you have, roughly if need be, and improve it there. `deck` prints how many texts are left.

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
very long, so never read it whole. Search it for the question or the term you need. A question whose fact a later project
replaces is listed there under its own heading: it counts by rating in `description`, and `check` refuses its term.

Two settings of `reports/D.deck.json` are yours:

- `same_audience`: `true` when the projects differ in what they measure and address the same people in the same
  market, as `narrative.audience` shows: the usual case, and the reader then sees one figure per block. `false` when
  the study splits its projects by audience or market, such as a project per country or per customer segment: each
  project keeps its figure, because audiences and markets are never added up.
- `moved`: `{"<question key>": "description"}` for a question that names no subject and scores a position in a debate
  rather than whether the subject is found. Move nothing else.

## 3. Find the results

Start from the comparison. The figures file gives, for `reach`, the answers naming the subject beside the answers naming
each competitor, and the subject's position among the names monitored. **A figure alone says nothing: 72 of 120 is weak
or strong only against what the others get.** A subject second of ten is doing well, whatever the fraction looks like,
and you say so. A subject eighth of eleven is far behind, and you say that.

Then read in `material` every answer rated unfavourable on a question naming the subject, then the answers behind the
lowest and the most surprising figures. Look at what those answers describe and at the domains they cite: an answer about
a company with a similar name is `confused`, whatever its rating. Give each result one class:

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
grow", write that, not "they choose the competitor". A count of unfavourable answers means what the question's rubric
says for those scores: read the rubric before you name it.

A page on the subject's own domains is the subject's, whatever the answer calls it: an answer naming the subject's
API or help pages as "a different service" is describing the subject. `confused` is what the answer attributes to
someone else, and the costs, terms or features it reports as theirs.

## 4. Choose the actions

**Open every third-party page before you ask it for anything.** An action naming a third party carries `pages`, one record
per site, written after reading the page the answers cite with `monitor.py page`. Look at who writes it too, and write what the page says of itself: "puts affiliated
products first", never "sells its places". A listing there may be a commercial deal, a directory may rank who pays, and a site
from another country is not where this market reads: say it in the action, or choose another page. The slide prints what a page lists, so `what` names none of it. Search the site for the subject before you say it is missing: it may hold a sheet of its own. A sheet the site invites its
publisher to claim is the reader's to claim and correct, at no cost: say that, never "ask them to add it".

```json
"pages": [{"url": "guide.example/best-oat-drinks", "shows": ["Oatly", "Minor Figures", "Rude Health"]}]
```

`shows` holds what you read there: the providers the page lists, or, on a `wrong_fact`, the wrong figure as the page writes
it. Never fill it from the answers. The deck prints it beside the action, so the reader sees why that page. Many pages the
assistants cite are a seller's own catalogue or a guide promoting its own course: nobody else gets listed there, and asking
them earns a laugh. `check` refuses a page listing fewer than two others, a page the answers do not cite, and an action
asking to add the subject to a page that already lists it. A page that will not open has `"shows": []`, and its action starts
with what the reader checks there. When no third-party page holds up, write an action on the subject's own pages, or none.

A `wrong_fact` action carries the record for the subject's own pages too, and at least one page in it shows the wrong figure:
an answer citing a page does not mean the page holds the figure, and a page may hold no figure at all. Open the pages the
answers with the old figure cite, one after the other, until one shows it. When none does, leave the action out and say in
the facts slide's `read` that the old figure stays in the answers while the pages opened no longer show it.

Write three to five actions, in `actions`. Rank them by how many answers and how much of the reader's stated purpose
(`narrative.purpose`, each project's `decision`) they touch. If `themes` or `search-demand.json` carry search volumes,
use them to break ties. A wrong fact or a confusion comes first, then the largest gaps, where the subject is absent or a
competitor is chosen, then what is missing on topics mostly favourable: "0 of 18" before "12 of 18 favourable". The deck
prints the actions on the subject's own pages first, since they depend on the reader alone, then those asking a third
party, and says so; within each group it keeps your rank. So never refer to an action by its number.

The reader controls the subject's own pages and can only ask everywhere else, so at least one action acts on them: `check`
refuses a deck whose actions all ask third parties. Look for it in what the answers about the subject lack: a price the answers
give in different versions, a doubt the site leaves open, a page that still carries an old figure. Read the neutral and
unfavourable answers of the description block for that, even when the block's figure looks good.

Each action has:

- `class`: the result it answers;
- `what`: what to write and on which page, naming the pages or domains the answers cite. "Strengthen", "optimise" and
  "make the page answer" name no work: `check` refuses them;
- `why`: one sentence the manager accepts: what the assistants do today, and why this action bears on it. It carries the figure the action starts from. An action on a third party also says why that site: "the site cited most on these questions, by 25 answers";
- `read_next`: the figure the next report reads, with its value today. This deck does not print it: the next edition prints it beside the same figure on its own period;
- `block`: the block whose slide holds the evidence. Set that slide's `action` to the action's number.

Every `wrong_fact` and `confused` result that qualifies takes a place among the actions, ahead of the last of the others:
an assistant stating a wrong fact or describing someone else is what the reader can correct first.

An action needs at least three answers behind it, from more than one assistant or more than one question. `wrong_fact`
and `confused` need two, from one assistant too: an error can be checked on a page and a view cannot. A result resting on
fewer goes in the notes to the operator. A question with fewer than three answers counts in its topic and in the list of questions, and nowhere
else: one answer of two is no finding, and `check` refuses a row or an excerpt of it.

**Look at the subject's site first.** The manager's first reaction to "publish a page on X" is "we already have one".
Read the subject's pages the answers cite and the page closest to the action with `monitor.py page --url <address>`: it prints
all the HTML holds, tooltips, closed answers, title and description included, which a web tool leaves out. When a site refuses
it, use your web tool, and what that does not show is not known. What exists is made clearer or completed, naming the page and
saying what is missing; only what is missing is published. Text that sits only in a tooltip or a calculator exists: say so, and
ask to bring it into the page's text, where assistants read it. Look for other versions of the page too: an old landing page
still online, or a stale title, is the subject's own to fix, and the first place an old price comes from. A fact recorded from the subject's own page is on that page already: never ask to publish it
there, and aim the action at what still carries the old term. If you cannot open the site, write the action as what the
page must say, without claiming it does not exist, and tell the operator.

Never ask to be listed on a site the answers already cite on questions about the subject: it probably lists the subject,
and `check` refuses it. Say what is missing there, or choose another. The same holds for a page you could not open: if you
cannot tell whether a listing exists, write what it must say, without claiming it is missing.

When open questions do not name the subject, the subject's own site is rarely the gap: it already says what the company does,
and "open a page on what we sell" earns "the whole site is about that". The assistants read other people's lists there.
Aim the action at the comparison articles and directories cited on those questions: which list, and what it should say
about the subject. Publish on the subject's own site only an answer it does not hold yet.

The places to act are the subject's own pages and the third parties that list or compare others: comparison sites,
directories, review sites, the press. The figures file lists every domain that is neither the subject's nor a listed
competitor's, so read what each one is before naming it. Start from the sites cited most on the action's questions: if
you pass over a top one, it is because it is another seller or an authority. A competitor's site is a place to read,
never one to act on, and `check` refuses those the study lists. The site or blog of any other seller in the field counts
as a competitor's, even with a comparison page on it. A public authority's site is no place to get listed: being on it
depends on rules the answers do not show, so it goes in the notes to the operator. An action says what to publish and
leaves the content to the subject: it states as fact only what `study.json` records, however many answers say it. Write the
question the page must answer, "say what happens to the funds if the company closes", never the answer: `check` refuses "the
funds are held by". Say what a page of the subject lacks, never that it "only says" something: its owner knows it better. Never
assign an action to a department of the client. Never promise an outcome. A page an answer cites did not necessarily
cause it: write "cited", never "caused".

An action on a third party says which page, from the addresses the answers cite on those questions: the figures file lists
the pages cited most, `material` the rest, and the action's slide prints the page cited most. What a page covers is what its
address or its title says: "its comparisons of software" is wrong when the pages cited are about business accounts.

Every action names at least one domain, and only domains the answers cite: `check` refuses any other, a site named
without its domain, and a third party cited by fewer than five answers, or one in twenty, on the action's slide, which prints that count. A site of another country lists that country's providers: for a subject sold in Italy choose an Italian
site, even one cited less.

A comparison page says where the subject fits and for whom. It never asks the subject to say when a competitor is the better
choice: no marketing manager publishes that.

An old figure has a source the deck can show. A site usually feeds both kinds of answer, so a site's count says nothing: 63 of
99 answers with the old figure citing a site means little when 30 of 46 with today's cite it too. The facts slide draws the
pages the answers with the old figure cite and those with today's hardly ever do, split by who wrote them, and the figures
file lists them. Rest the action on those pages: the subject's own first, then third parties', naming the page. Open them
first and say what they show. A page you could not open is one to check, not one to correct: "check the price on
g2.com/compare/a-vs-b, cited by 23 of the 99 answers with the old figure and hardly ever by those with today's". Competitors'
pages among them go in the slide's `read`, as where the old figure comes from, never in an action. Show the same reason on the
slide: an action's figures are on its own slide, and `check` refuses any other. A site that has changed since the period
explains itself in the `read`: say so when the answers still carry what it no longer shows.

A facts row can rest on other questions than a topic of the same name: its label says how many. When a slide on the topic and
the facts slide give different totals on one subject, say which questions each counts. In a title use the chart's word for a
row: "budget control", not "preventing overspending".

Ask a third party to correct a page only when the answers show that page saying something false about the subject. A
page about another company with a similar name is right as it stands, and its address usually carries that name: the
action then stays on the subject's own pages. Name a page by its domain, by an address the answers cite or by the source
a fact records: `check` refuses any other address.

A recorded fact can be old. Answers citing an official register or the subject's own page against it go in the notes to
the operator, with no action on that fact. When most answers citing the subject's own page carry an old figure, check
that page before asking anyone else to change theirs.

Name only third parties cited on the questions of the action's slide, and `check` refuses any other: `material` lists the
domains question by question. A site you could not open is one to check, and the reader does the checking: "check whether example.com lists
Avenello among the oat drinks, and ask to add it", never "the entry on example.com must say" and never "ask example.com to
check": `check` refuses that. A
reason given for an action comes from the figures or from `narrative.purpose`: what buyers do or think is not in the answers.
An amount in a sentence is a recorded fact or stands in an excerpt on the same slide: a range no slide shows has no proof.
An action rests on at least three answers: one answer can stand in a `read`, and `check` refuses a reason written on one.
The favourable figure counts the answers to the questions on the subject, so write "answers to questions on X", never
"answers naming X": other answers name it too.

## 5. Write the text

| Field | What it holds |
|---|---|
| `opening.who` | Who asks, as the cover's sentence needs it: "as {who} would ask them". Plain and short: "parents of small children and nutritionists" |
| `opening.questions.<block>` | The question this block answers, in the manager's words, about their own market. It ends with "?", has a subject of its own ("People looking for an oat drink without naming Avenello: which names do they find?") and never says "block", "presence" or "description". It holds no count: the card draws it |
| `opening.examples.<block>` | The keys of one or two real questions of the block, the ones the manager would recognise at once. Pick questions the deck then shows: not one with fewer than three answers, and not the same question on two cards when the block has another |
| `found.title` | The single most important finding, as a full sentence the manager could repeat to their boss: "Avenello is eighth of the eleven names monitored when people ask without naming it, and most answers about it by name are favourable". It says who asks in words: "without the name" means nothing yet |
| `found.answers.<block>` | One sentence answering that block's question. The `reach` one says the subject's position in words ("eighth of eleven") and names who stands ahead: the reader must be able to say whether it is good or bad. Names a few answers apart are level, and the chart says so: write "level with", never "ahead of". When one assistant alone answers the block, the chart says so: leave it out of the sentence |
| `actions_title` | What to do first and why, as a full sentence with a verb of doing. It starts from the first row the slide prints, the subject's own pages when an action is on them, and never announces the list. Shorter words keep the action's claim: a subject with an entry on a site and missing from one of its lists is never "got onto" that site |
| `blocks.<block>` | One to three slides. Give each finding its own slide, and one slide showing the topics of the block. Two slides never draw the same rows: `check` refuses it |
| `slide.title` | What this slide found, in the manager's words |
| `slide.read` | The one or two sentences the chart does not say. A slide with an action says, here or in the title, the result the action rests on |
| `slide.dimensions` | The topics this slide draws; empty draws them all. Across a block's slides every topic is drawn. Put together only what one title can say |
| `slide.questions` | The keys of the questions this slide draws, when it is about them. Use it whenever title or read cite a question's figure: a slide about one finding draws that finding, never the topics around it |
| `slide.rows` | `dimensions`, or `questions` to draw one row per question |
| `slide.excerpts` | At most two, each `{"text", "question", "assistant"}`. A slide with an action shows at least one: what the action rests on, in the assistant's words |
| `slide.action` | The number of the action this slide supports, or `null` |
| `sources.title`, `sources.read` | Which sites the assistants read for what, and what the actions do on them, in a full sentence. The slide draws the subject's pages cited most and every site an action names. When the site cited most has no action, say why: another seller, or questions where the subject does well. Say what a site publishes or leaves out only if you opened the pages the answers cite on it, each of them: one page says nothing of the others. On the questions without the name, the slide and the figures file say how many answers citing a site name the subject: when that share is high, that is the reason for no action, and a site with many answers and few naming the subject is where to look for one. Say among which sites a site is cited most, and give counts rather than saying one site overtakes another. The third party cited most on each group has an action, or `read` says why not |
| `method.limits` | Only a limit that changes what the reader may conclude, such as a question type not measured |
| `method.ask` | Two or three questions the reader can put to Claude or ChatGPT through Sentl's connector about these results |

**Voice.** The deck is written about the subject by whoever prepared it. Name the subject: never "we", "us" or "our" for it,
in the questions of slide 2 as everywhere, and `check` refuses them. In Italian keep one gender for the subject in every
sentence: "Avenello lo trova" and "la citano" in one deck read as two companies.

**Words.** The manager's words, never the study's. Each column shows what to write instead:

| Never | Instead |
|---|---|
| block, dimension, project, Discovery, category questions | who asks and what about: "people looking for an oat drink without naming a brand" |
| score, rating 4 or 5, band, mean | favourable, neutral, unfavourable |
| current fact, outdated fact | today's price, the old price, the fact itself: «2,10 €» |
| "the platform names it in 0 of 18" (a topic as subject) | "none of the 18 answers on platforms names it" |
| "the figure reaches 35 of 75" | what the answers do: "35 of the 75 answers on the app are favourable" |
| "the verdict of those asking about X" | "102 of the 127 answers to questions on X are favourable": people ask, the answers judge |
| "second of the ten names the assistants cite", "second of ten providers" | "second of the ten names monitored": the assistants cite others too |

A topic name ("Cash flow", "Pricing") is fine as a label in the chart. In a sentence, say what people ask about. The word
"answers" needs no explanation, because slide 2 gives it; "questions" means the questions a person would type.

**Titles.** Plain declarative sentences saying what was found, in words the manager would use with a colleague. Say the
content, not the statistic: "People looking for an oat drink find Avoria and Oatfield long before Avenello" says more
than "Avenello appears in 14 answers of 90". At most two figures: `check` refuses more. A title stays
true when read beside its own figure. A number in a title says what it counts. A title claims no more than its evidence:
"preferred" only for answers that choose. A title holds for every row its slide draws: when a row says otherwise, name the
rows the title speaks of, or give them a slide of their own. "Behind" or "ahead" holds only where the comparisons go that
way, each of them. A superlative ("the weakest", "the strongest") compares with every row of the block, on all its slides.
A comparison stays on one question or one topic: "A in 6 of 6 on the first question, B in 3 of 6 on the last" compares
nothing. The answers show what assistants reply: "convinces", "wins over" and the like say what people think, which no answer shows, and
`check` refuses them. A title has a subject and a verb: "On oat drinks for coffee, one answer in two" is a note, and "Half the answers on oat
drinks for coffee name Avenello" is a title. A title says what its chart shows: on a slide of some questions it speaks of
those questions, never of the block's total, and it does not repeat the title of slide 3. A title about sources never says
the answers "form on" or "are guided by" a page: say they cite it. No slogans, no
rhetorical questions, no metaphors, no contrast built for effect. Delete any sentence that loses no information when
removed. The reader calls this document a report: never write "deck".

The old-figure count holds the answers with an old figure alone, and those with both are among today's: write "only the old
£21", never "state the old £21", and say how many of today's stand beside an old figure: the figures file has the count.

**Figures.** Cite only the figures `history/deck/D.figures.md` holds, as they stand: `check` refuses any other, and sums
of your own. A figure in a title or read must be on that slide's chart: `check` refuses any other, so draw the question
with `slide.questions`, or leave the figure out. A figure belongs to what it counts: a topic's figure carries the topic, a
question's figure the question. Never give a topic's count to one of its questions. Write small figures as "x of y". Say
"none of the 18 answers" and "all 9 answers" where the count is 0 or y: it reads better than "0 of 18", and `check` holds
it to the figures. Elsewhere `check` refuses "none", "all", "never" and "always". The first slides may give a figure at
most twice: say it once, then say something else. A facts figure counts the answers stating the current term, and the same
answer can get the rest wrong, adding a price or a plan the facts do not hold: write that they state today's figure, as the
chart does, and `check` refuses "correct". A facts row also shows how many answers are favourable: when the fact is carried
and the answers are weak, say so. A figure per assistant only when the difference between assistants is itself the finding.
A price or term from `facts` goes in «», so it is read as a term and not as a figure.

A slide drawing some of a topic's questions and citing the topic's figure leaves the reader adding up rows that do not
add up: draw every question of the topic, or cite only the rows drawn. Never write that a question "is not here". Say
"neutre", as the chart does.

**Favourable answers show.** A reader told that 112 of 141 answers are favourable asks what a favourable answer says. Every
slide of `description` carries an excerpt, and `check` refuses one without: a slide saying the answers are favourable shows a
favourable answer. Across the deck the excerpts show what holds as well as what does not: five excerpts against the subject
beside a favourable headline read as bias. Where answers are unfavourable, one excerpt shows one: the reader looks for it, and
`check` refuses a deck without. The slide prints each excerpt's rating: for a doubt quote a neutral or unfavourable answer, since `check` refuses a doubt from a favourable one,
since a doubt quoted from a favourable answer reads as a contradiction.

**A fact keeps the name `study.json` gives it.** The reader knows their own company better than anyone: a word added to a
fact is the first thing they catch. An "issuer" does not become a "bank", a "plan" does not become a "subscription", and
what the subject is called stays what its site calls it.

**Excerpts.** Show more than one assistant wherever more than one answers: `check` refuses a set from one alone, which reads as a study of that assistant. Copied verbatim from `material`, at most 40 words, with `[…]` where you skip or cut. An excerpt keeps
the meaning of the sentence it comes from: a condition or a comparison stays whole, including its "if", "while" or
"but". Read the sentence before it and the sentence after it first. An excerpt that loses its condition says what
the answer does not say. Give the question as `figures` writes it and the assistant's name. Pick the excerpt that shows
the finding at a glance: on a `reach` slide, what the assistant recommends in place of the subject.

**Framing.** Neutral. State what holds as well as what does not. A sentence about a set holds for the whole set: if one
comparison of three goes well, write two of three and name the third. Read every answer of a question before you say what
they do, and count them. "The answers say" stands for most of them: when fewer say it, write "some answers". What the
answers say about the subject stays theirs unless `study.json` records it: "some answers say the price list is not
published", never "the price list is not published", in a title above all: the reader's claim is not disproved by what an
answer says of it. When answers say something serious about the subject, such as how
funds are protected, say what they say and whether the facts recorded settle it. Call a fact wrong only against the facts in
`study.json`; otherwise say the answers diverge. A competitor being preferred is a result, not an error of the answer.

**Never mention** the model that rates the answers, run or question ids, model ids, credits, readings, unstable pairs,
ratings with and without a given answer, comparisons of pages cited by high and low rated answers on fewer than 5
answers, or anything about how the deck was built.

Write the text in the study's `report_language`. An answer whose rating and fact disagree (favourable on an
answer stating an outdated term) counts by its fact in the deck, and goes in the notes to the operator.

### The second edition

When a deck that passed `check` comes before this one, `deck` adds `earlier` to the text to fill and a section "Compared with the deck of ..." to the figures file. A deck started before that one became final gains the field the next time `deck` runs. The code draws the rest: each block's figure on both dates, on the questions asked of the same assistants in both, and each earlier action with its earlier `read_next`. A figure rose or fell when it moved by 20 points or more.

- `earlier.title` and `earlier.read`: what moved, or that the figures stayed where they were. With no question asked of the same assistants on both dates the slide is not drawn and the fields are not there;
- `earlier.actions_title`: what the figures of the earlier actions show, as a sentence;
- `earlier.now`: one text per earlier action, in their order: the same figure `read_next` named, on this period, at most 70 characters. Name what the figure counts, as `read_next` does.

The deck does not know whether the client acted. Write no cause: `check` refuses "grazie a", "per effetto", "thanks to", "as a result of" and their kin in these fields. These two slides come on top of the 12 the deck may hold.

## 6. Reread, check and render

Before running the commands, go through every sentence that says what the answers do. Open `material` on that question,
count the answers that do it, and keep the sentence only if the count supports it. For a sentence saying what the answers
choose or rank, find the sentence of each answer that says so: "there is no single best, it depends" is no choice, and
a name in a list of candidates is not a preference for it. Take out a sentence that tells the reader nothing about the
results, such as one on how the questions are built.

```bash
python3 <skill>/scripts/monitor.py check --study "$S" reports/D.deck.json
python3 <skill>/scripts/monitor.py pdf --study "$S" --deck --date D
```

`check` refuses a deck with no action, an action with no evidence slide, a block with no question or answer for the first
slides, a figure missing from the period, a figure over a chart that does not draw it, a title of more than two figures, a
figure repeated on the first slides, a presence figure with no comparison, a subject among the first played down, a word of
the study, a project's name, a topic as the subject of a sentence, an excerpt not verbatim, attributed to another question or
assistant, or cut inside a sentence with no mark, a text longer than its slide holds, a claim of all or nothing the figures
do not bear out, an address no answer cites, a slide with an action and no excerpt, and a term a later record replaces. Fix
the text and run it again until it passes. Never fix a failure by changing a figure drawn by the code.

`check` reads a count in digits in any form: "9 of 12", "9 of the 12", "9 delle 12". A count beside a site, a page, an assistant
or a competitor must be that name's, on the period, a block, the questions of its slide, a topic or one question: the refusal
prints the counts the name has, so take the one that fits the sentence, and never reword the count to get past it. A site's
count is not its page's: "guide.example is cited by 9 of the 12, and its list by 3 of them". A count beside a site carries its
base: "(39)" and "cited by 25 answers" are refused. In a sentence naming an assistant the count and its base are that assistant's answers alone, and the refusal says so. Name what a base counts, because the reader cannot tell what "19 of 141" is: "19 of the 141 answers to the questions on prices". A grounding redirect hides the page an answer read, so a page's count may
run from the answers showing its address to those plus the answers the redirect hides. A site said to be cited most comes
first, alone, among the sites the sentence speaks of: write "among third parties" when the subject's own site leads. On the
sources slide that holds on a whole block, and its title says it of any site it says the answers cite.

`pdf --deck` refuses a deck that fails `check` and a slide that runs over its page, and names the slide: shorten its
text. It writes `reports/D.deck.pdf` and the copy to send, in `reports/share/`. On a host without a lasting folder,
end as SKILL.md says, with the deck's PDF in place of the report.

## 7. The reader's test

`check` knows whether a sentence is allowed, never whether it is understood, and you cannot judge what you wrote. Give the
deck to a reader who has seen nothing: a fresh agent if the host can start one, with only the text of the PDF
(`pdftotext -layout reports/D.deck.pdf -`) and this brief.

> You are the marketing manager of the company named in this document. You know your market and your competitors. You know
> your company monitors what AI assistants say about it, and nothing else. You have five minutes. Reading only slides 1 to
> 4, answer in your own words: What was done, and by whom? What do the numbers count? What is the main result, and is it good
> or bad, compared with whom? What should you do first, and why? Then read the rest and quote every sentence you had to read
> twice, every number or label you cannot explain, and every chart that does not show what its title says. Do not be polite.

The deck passes when the four answers are right and nothing is quoted on slides 1 to 4. Rewrite what fails, render again, and
give the new text to a new reader. Two readers are enough: a label the code draws is no reason for a third, so tell the
operator what the second one still quotes. With no way to start a fresh agent, answer the brief yourself slide by slide, and tell the
operator the test was not independent.

## 8. The audit

The reader tells you what is not understood, never what is false. Give the deck to a second fresh agent, or, with no way to
start one, audit it yourself and tell the operator the audit was not independent. Its brief:

> You audit a client deck against its data, and change nothing. Read `reports/D.deck.json`, the figures file and `study.json`
> in full, and search the answers in `history/material/D.md` with grep. For every title and sentence, check the figure, the
> name and the claim. `check` has held every count in digits beside a site, a page, an assistant or a competitor to that name:
> spend your time on what the sentence claims from its count, on a count written in words, and on a count of a word or a fact
> in the answers, which it cannot read. A sentence that generalises must hold on every row and question it covers: go through them one by one,
> and name any it leaves out. A comparison between two names must hold on their counts. "Chosen" needs answers that choose.
> An excerpt must say what the sentence beside it claims. An action must rest on at least three answers, and must not ask for
> what the page already has: open the subject's pages it names. The actions must answer the deck's main result: when it is
> an absence and no action touches the pages the assistants read on those questions, report it, with the sites that list
> providers and the answers citing them. Open any third party an action names: a paid directory, a site foreign to the market
> or one no answer drew on is no place to send the reader. A page that puts affiliated products first stays an action when many
> answers cite it: say so of it. A sentence
> on what a site holds or leaves out: read every page the answers cite on it with `monitor.py page`, the subject's pages first.
> A term from an old document: say its date. Two totals under one word read as a contradiction: name what each counts. A count
> beside a name says which question, and whether it counts a site or one page. A site's count clears no page: a page many
> answers cite that leaves the subject out gets an action, however many answers citing the site name the subject. Before
> saying a subject is absent from a site, look for its entry there, and report a list you could read only in part. A tie is no "most". An excerpt stops nowhere that changes what it says. An action's reason
> is the result that action changes: report two problems joined as if one caused the other. Then search the answers for what the deck leaves out: a wrong fact, a confusion with
> another company, a doubt several assistants repeat. Report only what is false, overstated or left out, with the field, the
> exact words and the real count. No praise and no rewrites.

`history/deck/D.audit.md`, when it exists, is this report from an agent the operator ran, a stronger model or a reader: skip the
brief and work from it. Check each point against the answers and the pages, and rewrite every sentence that does not hold.

Rewrite every sentence it reports. A wrong fact or a confusion left out becomes an action when it rests on the answers. A
biggest gap with no action gets one, or the `read` of its slide says why none holds: the reader goes there first. Then
run `check` and `pdf --deck` again. When the deck already exists and passes, this step is a pass of its own: keep what the
audit does not report and start nothing over.

## 9. Tell the operator

In the chat, never in the deck: where the copy to send is, the choices open to doubt, anything in the data that looks
wrong, what you could not check on the subject's site, what the reader's test found, and the results left out for resting on
too few answers. The operator sends the deck: never send it yourself.
