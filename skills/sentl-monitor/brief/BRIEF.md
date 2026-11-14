# brief <subject>

Builds the inventory of themes a study will monitor, each with where it came from, and
collects how people search for them. It writes `brief.md` and stops for the operator's review.
Sentl is not called: no write, no credit spent. A keyword-data server, if the operator has
one, may spend that server's quota (step 4).

`<skill>` below is this skill's directory; `$S` is the study folder.

Every `monitor.py` command below can also end with exit 6: an unexpected error. Stop, give the
operator the message, and run the same command with `--debug` to show where it failed.

## 1. Study folder

Ask where the study folder is, or propose `./<subject>-study/` in the current directory. It
must not be inside this skill's directory. Then, in every conversation:

```bash
python3 <skill>/scripts/monitor.py doctor --study "$S"
```

Exit 1: the folder cannot be written; choose another. On a web sandbox the folder is deleted
when the conversation ends: unpack the pack the user attached first (SKILL.md), and pack the
study again after step 7.

## 2. Read what the client gave

Positioning decks, product sheets, complaint summaries, brand-health studies, social-listening
reports. List every theme each document raises, with the document's name as the origin's
`detail`. The origins are `client_material` (a document), `client_issue` (a concern the client
raised in conversation) and `client_analysis` (another analysis the client ran). Summarise the
themes back in three lines, then ask only about the gaps.

## 3. Define the subject and write the seeds

Ask for, and write to `$S/seeds.json`:

- the subject's label, kind (brand, category, method, organisation) and aliases, as people
  type them, marking any that is a former name of the subject;
- the foils it is measured against, each with its aliases;
- where the subject is (its towns, regions, sites) and any other organisation that shares its
  name (step 5 proposes candidates);
- the components (an ingredient, a material, a technology), each with the terms people use for
  it;
- the market: country and language;
- for each theme, the seed queries: how a person would type the theme into a search box;
- the personas: the kinds of people who ask the assistants about the subject, each in a
  situation that leads to a decision;
- the sources to watch: bodies the assistants cite and nobody asks as.

```json
{
  "schema": "sentl-monitor/seeds@1",
  "market": {"country": "US", "language": "en"},
  "subject": {"aliases": ["Avenello"]},
  "foils": [{"aliases": ["Avoria"]}],
  "components": [{"terms": ["oat milk", "oat drink"]}],
  "themes": {"health": ["oat milk bad for you", "avenello sugar"]},
  "personas": [
    {"id": "parent", "label": "A parent choosing for a child", "group": "chooses",
     "situation": "buys a plant drink for a child with a lactose intolerance",
     "decision": "which oat drink to put in the cart",
     "asks": ["Is oat milk safe for toddlers?"],
     "seeds": ["oat milk for toddlers"]}
  ],
  "sources_to_watch": [{"label": "A consumer association", "domains": ["consumers.example"]}]
}
```

The theme ids are the keys of `themes`; they stay the same in the study.

Each persona has:

- `id`: a short key the study's questions use;
- `label`: who the persona is, as the report names them;
- `group`: `chooses` (picks the product for themselves or their family), `customer` (already
  buys or uses it), `buys_for_others` (buys for a business, an office, a school), `works_there`
  (works for the subject or wants to), or a group the operator names;
- `situation`: what is happening when the persona asks;
- `decision`: what the answer helps the persona decide;
- `asks`: one or two questions as the persona types them;
- `seeds`: the searches the persona would type, or an empty list when the operator knows of none.

Look for personas in the client's documents first: who the complaints come from, who the sales
team sells to, who applies for jobs. Each group above holds at least one persona of most
subjects; ask the operator about a group with none.

Bodies such as regulators, consumer associations, the press and review sites go in
`sources_to_watch`, with the domains they publish on. The assistants cite them; they do not ask the assistants about
the subject, so they are never personas. `demand` refuses a label that is both a persona and a
source to watch.

## 4. Collect search demand

**Google suggestions, always, with no key.** Each seed is sent as typed and followed by each
question stem of the language (Italian: è, fa, come, perché, quanto, quale, si può; English: is,
does, how, why, can, which, vs). For another language, pass the stems with `--stems`.

```bash
python3 <skill>/scripts/monitor.py demand autocomplete --study "$S" --hl en --gl US
```

Each persona's seeds are sent the same way, and their suggestions are recorded under the
persona in `search-demand.json`. Sources to watch are never sent.

Exit 1: some prefixes could not be fetched, and the command lists them. Run it again; it
fetches only the prefixes still missing. Exit 2: the seeds file or the stems are not usable;
the message says which.

**Volumes, when the operator has a keyword-data server connected.** Look in the connected
servers for a tool that returns monthly search volume and related searches for a keyword, a
location and a language. Read its name and its parameters from the server now; never assume
them. Tell the operator which server and tool you will use and that it counts against that
server's quota, and call it only after a yes. Call it for the seeds and for the most frequent
suggestions of each theme. Write what it returned to `$S/volumes.json`:

```json
{"provider": "<server name>", "tool": "<tool name>", "collected": "2026-10-16",
 "keywords": [{"theme": "health", "keyword": "oat milk bad for you", "monthly_volume": 1900,
               "related": [{"keyword": "oat milk bad for gut", "monthly_volume": 320}]}]}
```

`collected` is today's date. Write every number as the tool returned it. Then:

```bash
python3 <skill>/scripts/monitor.py demand volumes --study "$S" "$S/volumes.json"
```

The command keeps a related search only when it concerns the subject (it holds an alias of the
subject or of a foil, a component term, or a word of the keyword it came from) and records how
many it dropped for each keyword. Show the operator the dropped count and the kept list, and
change the seeds if a theme lost searches that matter. Exit 2: the file is refused whole, and
the message names the field.

**An export file instead.** When the operator has a CSV export from a keyword tool (a keyword
column and a volume column; a column `related to` marks a related search of the keyword in it),
for one theme:

```bash
python3 <skill>/scripts/monitor.py demand import --study "$S" --provider "<name>" --tool "<export name>" --theme health <file>
```

**No volume source.** Say so to the operator. The counts are then Google suggestions only, and
`brief.md` carries the line the summary prints.

## 5. Add what search showed

```bash
python3 <skill>/scripts/monitor.py demand summary --study "$S"
```

It prints, for each theme, the distinct suggestions, the volume for each class (`subject`,
`foil`, `component`, `generic`) or none, and the top queries. A class is never added to
another: searches that name the subject stay apart from searches about a component alone. A
theme that only search surfaced joins the inventory with the origin `search`, and the detail
names the source and the month, such as `Google autocomplete, United States, October 2026`.

After the themes it prints each persona's distinct suggestions and top suggestions, or marks
the persona as without search evidence, and then the sources to watch on a line of their own.
A persona without search evidence stays in the inventory: some people ask an assistant what
they never type into a search box. Tell the operator which personas have none.

Then look for namesakes, other organisations with the subject's name, whose answers would be
counted as answers about the subject:

```bash
python3 <skill>/scripts/monitor.py demand namesakes --study "$S"
```

It writes nothing. It lists the words that suggestions naming the subject add and the study never
uses ("sofas", "shares" for a dairy brand), and, once runs are ingested, the cited sites named like
the subject that it does not own, the pages of other sites carrying its name and the places the
answers say it is based in. Show the list to the operator and ask which are another organisation.
For each one they confirm, record a label and at least one marker: its `places`, `domains`,
`products` and `listings` (address fragments of the pages listing it, such as a job site's company
page). `design` writes them to `subject.namesakes` and the subject's places to `subject.places`.

## 6. Write `$S/brief.md`

In the operator's language, with these sections:

1. The subject: label, kind, aliases (former names marked), foils, components, owned domains,
   places, market and language, and the namesakes with their markers, or the line that none was found.
2. The theme inventory: one row for each theme, with its origin, the detail of the origin and
   its search demand.
3. Search demand: a table of each theme's distinct suggestions and volume for each class, with
   the source and the date. Without a volume source, the table has the suggestions only, and
   this line follows it: *The counts are Google suggestions: they measure how many ways a theme
   is phrased, not how many people search it.*
4. Who asks: `generic_consumer`, `personas`, `stakeholders` or `mixed`, with the reason.
5. Personas: one row for each persona of `seeds.json`.

   | id | label | group | situation | decision | asks | search evidence |
   |----|-------|-------|-----------|----------|------|-----------------|

   The search evidence is the persona's count of distinct suggestions and its top suggestion,
   or the words *without search evidence* when Google gave none.
6. Sources to watch: each body with its domains, under its own heading, apart from the personas.
7. The documents read.

## 7. Stop

Tell the operator which themes came from documents, which from what they said, and which from
search. Wait for their review; the next route, `design`, reads `brief.md` and
`search-demand.json`.
