# Dimension catalogue

The dimensions that recur across subjects, with the question patterns, rubric anchors and facts
each one needs. The designer adapts an entry to the subject, the market and the theme's top
queries; the patterns and anchors are starting points, never final text. `design` reads this file
at steps 3, 6 and 7. `snapshot` picks its four or five dimensions from it and records the entry's
id in the dimension's `catalogue` field.

Placeholders: `[subject]` is an alias of the subject as people type it, `[category]` the
component or product category, `[foil]` an alias of a foil, `[market]` the country or city, and
`[attribute]` the property the theme is about.

## The two axes

The axis is chosen for a dimension before its anchors are written, and the report explains the
score by it.

**stance.** The score tells how the answer treats the subject.

| Score | Anchor |
|---|---|
| 1 | Advises against the subject, or states a harm or a fault about it |
| 2 | Raises doubts or risks without grounds, or mentions the subject only as a caution |
| 3 | Describes the subject without a verdict |
| 4 | Favourable, with no grounds given |
| 5 | Favourable, with grounds from a named source |

**fidelity.** The score tells how closely the answer matches the facts the study holds.

| Score | Anchor |
|---|---|
| 1 | States as fact something the dated facts show to be wrong or outdated |
| 2 | Mostly wrong or outdated, with one correct element |
| 3 | Correct in outline, vague or missing the figure or name that matters |
| 4 | Accurate, without the conditions that apply |
| 5 | Accurate, with the conditions the evidence sets (scope, date, market) |

On a question that names no brand, replace anchor 2 with *the subject is not mentioned* and
anchor 1 with *the subject is named negatively or advised against*; the other anchors describe
the subject as the answer presents it.

## Entries

Each entry lists its id, the axis it usually takes, whether its questions name the subject, its
question patterns, the anchors that differ from the axis tables, and the facts it needs.

### `reputation`

- Axis: stance. Names the subject: yes.
- Patterns: "What do people say about [subject]?"; "Is [subject] any good?"; "Is [subject] worth
  it in [market]?"
- Anchors: the stance table.
- Facts: none. Take the strongest claims the subject's pages make as the grounds the judge looks for.
- Search lean: usually mixed. When the top queries doubt the subject ("is [subject] a scam",
  "[subject] reviews bad"), add the question in positive framing: "Is [subject] reliable?".

### `recommendation`

- Axis: stance. Names the subject: no.
- Patterns: "What is the best [category] to buy in [market]?"; "Which [category] would you
  recommend for [persona's situation]?"; "Which [category] brands are worth trying?"
- Anchors: 1 names the subject negatively or advises against it; 2 does not mention it; 3 lists
  it among several without ranking; 4 recommends it among the first; 5 recommends it first or
  singly, with grounds.
- Facts: none. The report reads this dimension by presence and rank.

### `comparison`

- Axis: stance. Names the subject: yes, with one foil.
- Patterns: "Is [subject] better than [foil]?"; "[subject] or [foil] for [use]?"; "What is the
  difference between [subject] and [foil]?"
- Anchors: 1 prefers the foil and states a fault of the subject; 2 prefers the foil without
  naming the subject's strengths; 3 compares without a verdict; 4 prefers the subject without
  grounds; 5 prefers the subject with grounds.
- Facts: the figures the comparison turns on (price, size, rating), dated, for both.
- Pair a question that puts the subject first with one that puts the foil first.

### `price`

- Axis: fidelity. Names the subject: yes.
- Patterns: "How much does [subject] cost?"; "Is [subject] expensive in [market]?"; "How much is
  [subject] per [unit]?"
- Anchors: the fidelity table, with 5 requiring the current figure and its unit.
- Facts: the current price and the outdated one, each with the page it was read on and the date;
  record both as `current` and `outdated` terms as answers write them ("2.10", "$2.10").

### `product-facts`

- Axis: fidelity. Names the subject: yes.
- Patterns: "What is in [subject]?"; "How much [attribute] does [subject] have?"; "Does [subject]
  contain [ingredient or feature]?"
- Anchors: the fidelity table.
- Facts: the specification as the subject's page states it, with the date of the last change.
  Without a page to read it from, drop the dimension.

### `health-safety`

- Axis: stance. Names the subject: yes, or no for the category.
- Patterns: "Is [subject] bad for you?"; "Is [category] safe for [persona]?"; "Does [subject]
  have side effects?"
- Anchors: 1 states a harm without grounds or advises against; 2 raises unverified risks; 3
  neutral; 4 says it is safe, no grounds; 5 says it is safe with grounds from a named source.
- Facts: the claims the subject makes and the authority they cite.
- Search lean: usually negative. Add the pair: "Is [subject] good for [persona's goal]?".

### `sustainability`

- Axis: stance, or fidelity when the subject publishes figures. Names the subject: yes.
- Patterns: "Is [subject] good for the environment?"; "How sustainable is [category]?"; "Does
  [subject] use recycled [material]?"
- Anchors: the stance table; for fidelity, the fidelity table with the published figure as the
  reference.
- Facts: the published figures (emissions, recycled share, certification) with their report and year.

### `availability`

- Axis: fidelity. Names the subject: yes.
- Patterns: "Where can I buy [subject] in [market]?"; "Is [subject] sold at [retailer]?"; "Does
  [subject] deliver to [market]?"
- Anchors: the fidelity table, with 5 naming channels that exist today and none that do not.
- Facts: the current channels and the ones withdrawn, dated.

### `service-trust`

- Axis: stance. Names the subject: yes.
- Patterns: "Can I trust [subject]?"; "How good is [subject]'s customer service?"; "Is [subject]
  legitimate?"
- Anchors: the stance table.
- Facts: the policies the subject publishes (returns, guarantees) with their date.
- Search lean: usually negative. Add the pair: "Is [subject] reliable?".

### `employer`

- Axis: stance. Names the subject: yes.
- Patterns: "What is it like to work at [subject]?"; "Is [subject] a good employer in [market]?";
  "How does [subject] pay?"
- Anchors: the stance table, with grounds meaning named reviews or surveys.
- Facts: none usually; a published figure (headcount, pay band) with its date if the question uses it.

## Choosing for a snapshot

Pick four or five entries from what the reader needs to decide. Include at least one entry that
names no brand (`recommendation`) unless the operator wants reputation only. A dimension whose
facts cannot be found is replaced by another entry. Record the entry's id and the reason in
`design_rationale`.
