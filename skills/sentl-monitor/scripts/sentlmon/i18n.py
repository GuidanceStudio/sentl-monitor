"""Wording in the two report languages: the deck's labels, the sections of a comparison between two snapshots,
and the phrases by which an answer says it found no source."""

SECTIONS = {
    "it": {
        "purpose": "Cosa abbiamo fatto e a che scopo",
        "themes": "Da dove vengono i temi",
        "dimensions": "Le dimensioni e come ci siamo arrivati",
        "questions": "Le domande",
        "scoring": "Come vengono valutate le risposte",
        "findings": "Cosa dicono gli assistenti",
        "changes": "Cosa è cambiato",
        "summary": "In sintesi",
        "limits": "Cosa un singolo run non mostra",
    },
    "en": {
        "purpose": "What we did and to what end",
        "themes": "Where the themes came from",
        "dimensions": "The dimensions and how we reached them",
        "questions": "The questions",
        "scoring": "How the answers are scored",
        "findings": "What the assistants say",
        "changes": "What changed",
        "summary": "In short",
        "limits": "What a single run cannot show",
    },
}

COMPARE_ORDER = ["purpose", "changes", "limits"]

# The report of `compare`, between two snapshots of one subject.
COMPARE = {
    "it": {
        "title": "{subject}: due snapshot a confronto",
        "purpose": "Abbiamo confrontato due snapshot di {subject}, quello del {first} e quello del {second}: {questions} "
                   "domande poste a {models}, con un run per parte.",
        "dimension": "Dimensione", "score": "Punteggio del {date}", "presence": "Presenza del {date}",
        "change": "Cambiamento tra i due snapshot", "no_figure": "nessun dato", "no_change": "nessun cambiamento",
        "higher_score": "punteggio più alto", "lower_score": "punteggio più basso",
        "higher_presence": "presenza più alta", "lower_presence": "presenza più bassa",
        "rule": "La presenza è la quota di risposte che nominano {subject}. Un cambiamento è segnato quando il punteggio si "
                "sposta di almeno {score} punti o la presenza di almeno {presence} punti percentuali.",
        "limits": "Ogni parte è un solo run: una differenza tra due singoli run non è una tendenza.",
        "shared": "Sono confrontati solo gli assistenti presenti in entrambi gli snapshot: {models}.",
    },
    "en": {
        "title": "{subject}: two snapshots compared",
        "purpose": "We compared two snapshots of {subject}, of {first} and of {second}: {questions} questions put to "
                   "{models}, with one run on each side.",
        "dimension": "Dimension", "score": "Score on {date}", "presence": "Presence on {date}",
        "change": "Change between the snapshots", "no_figure": "no figure", "no_change": "no change",
        "higher_score": "higher score", "lower_score": "lower score",
        "higher_presence": "higher presence", "lower_presence": "lower presence",
        "rule": "Presence is the share of answers that name {subject}. A change is marked when the score moves by at least "
                "{score} points or the presence by at least {presence} percentage points.",
        "limits": "Each side is one run: a difference between two single runs is not a trend.",
        "shared": "Compared here are only the assistants of both snapshots: {models}.",
    },
}

# The labels of the deck. A label states what its value asserts, in the words of the language.
DECK = {
    "it": {
        "of": "su",
        "cover_title": "Cosa rispondono gli assistenti AI su {subject}",
        "cover_what": "Abbiamo fatto {questions} domande {assistants}, come le farebbero {who}, "
                      "e abbiamo raccolto e valutato le {answers} risposte{parts}.",
        "cover_what_repeated": "Abbiamo fatto {questions} domande {assistants}, più volte, come le farebbero {who}, "
                               "e abbiamo raccolto e valutato le {answers} risposte{parts}.",
        "cover_parts": ": {reach} alle domande senza il nome di {subject} e {description} a quelle su {subject}",
        "assistant_one": "a un assistente AI",
        "assistant_many": "agli assistenti AI",
        "cover_first": "Prima rilevazione",
        "cover_next": "Rilevazione",
        "cover_by": "A cura di {by}, con i dati di Sentl",
        "opening_title": "Cosa mostra questo report",
        "purpose": "Obiettivo",
        "question_one": "domanda",
        "question_many": "domande",
        "answer_many": "risposte",
        "overlap": "{n} delle domande delle altre colonne, {answers} risposte",
        "card_assistants": "Assistenti: {assistants}",
        "or": "o",
        "reading_title": "Come è fatta la rilevazione",
        "reading_answers": "I numeri contano risposte, non domande: ogni domanda va a {few} di questi assistenti, anche più "
                           "volte. {spread}.",
        "reading_answers_always": "I numeri contano risposte, non domande: ogni domanda va a {few} di questi assistenti, più "
                                  "volte. {spread}.",
        "reading_answers_one": "I numeri contano risposte, non domande: ogni domanda è ripetuta. {spread}.",
        "reading_answers_once": "I numeri contano risposte, non domande: ogni domanda è stata posta una volta, a {few} di "
                                "questi assistenti. {spread}.",
        "spread_one": "Ogni domanda ha {n} risposte",
        "spread_first": "{q} domande hanno {n} risposte ciascuna",
        "spread_rest": "{q} ne hanno {n}",
        "spread_rest_one": "{q} ne ha {n}",
        "spread_range": "Ogni domanda ha tra {low} e {high} risposte",
        "reading_assistants": "Assistenti: {assistants}.",
        "reading_scores": "Ogni risposta è valutata in automatico, con un criterio scritto per quella domanda prima di "
                          "leggere le risposte: {bands}.",
        "reading_first": "È la prima rilevazione: il confronto nel tempo parte dal prossimo report.",
        "reading_once": "È una rilevazione singola: le stesse domande, rifatte più avanti, mostrano cosa cambia nel tempo.",
        "reading_list": "Tutte le domande sono alla slide {n}.",
        "reading_list_many": "Tutte le domande sono alle slide {n}-{last}.",
        "origins_line": "Le domande vengono {origins}.",
        "origins": {"client_material": "dai materiali dell'azienda", "client_issue": "dalle richieste dell'azienda",
                    "client_analysis": "dalle analisi su {subject}", "search": "dalle ricerche su Google",
                    "probe": "da una prima prova con gli assistenti"},
        "found_kicker": "Cosa abbiamo trovato",
        "actions_kicker": "Cosa fare",
        "sources_kicker": "Quante risposte citano ogni fonte",
        "card": {"description": "Risposte favorevoli per {subject}. Sui concorrenti questo dato non è misurato.", "description_fidelity": "Risposte fedeli ai fatti",
                 "facts": "Risposte che riportano il dato di oggi"},
        "versus": "Risposte su {b} che nominano ciascun nome.",
        "and": "e",
        "close": "Nel confronto con {subject}, {names}: una nuova rilevazione può invertire l'ordine.",
        "close_first": {"more": "{name} ha {n} {answers} in più", "fewer": "{name} ha {n} {answers} in meno",
                        "same": "{name} ha lo stesso numero di risposte"},
        "close_next": {"more": "{name} {n} in più", "fewer": "{name} {n} in meno", "same": "{name} lo stesso numero"},
        "close_answers": ("risposta", "risposte"),
        "rank": "{subject}: posizione {rank} su {field} nomi monitorati; qui i primi {shown}.",
        "rank_below": "{subject}: posizione {rank} su {field} nomi monitorati; qui i primi {shown} e {subject}.",
        "left_out": "Non si contano le risposte a domande che nominano già quel concorrente.",
        "one_assistant": "A queste domande risponde solo {assistant}.",
        "groups": {"reach": "Domande senza il nome di {subject}", "description": "Domande su {subject}",
                   "facts": "Domande sui dati di {subject}"},
        "action": "Azione {n}",
        "action_site": "{site}: citato da {n} delle {y} risposte {where}.",
        "action_site_row": "{site}: citato da {n} delle {y} risposte su «{label}».",
        "action_here": "alle domande di questa slide",
        "action_there": "alle domande della slide {slide}",
        "action_lists": "{url} elenca {names}, non {subject}.",
        "action_lists_with": "{url} elenca {names}.",
        "share_kind": "deck di monitoraggio",
        "share_span": "dal {start} al {end}",
        "action_shows": "{url} riporta «{term}».",
        "action_page": "Pagina più citata: {page} ({n}).",
        "actions_head": ("N.", "Cosa fare", "Perché", "Slide"),
        "action_who": {"owned": "Sulle pagine di {subject}", "third": "Richiesta a un sito di terzi"},
        "actions_note": "Il prossimo report rimisura gli stessi numeri e li mette accanto a questi.",
        "actions_note_once": "Le stesse domande, rifatte più avanti, mostrano se questi numeri cambiano.",
        "changed_kicker": "Cosa è cambiato dal {then}",
        "changed_head": ("Domanda", "{then}", "{now}", "Il dato"),
        "changed_values": {"up": "è salito", "down": "è sceso", "same": "non è cambiato", "small": "si è mosso meno di {step} punti"},
        "changed_note": "Il confronto tiene solo le domande poste agli stessi assistenti in entrambe le date.",
        "earlier_kicker": "Le azioni proposte il {then}",
        "earlier_head": ("Azione proposta", "Il dato del {then}", "Lo stesso dato del {now}"),
        "earlier_note": "I dati non dicono se un'azione è stata fatta né se ha spostato le risposte.",
        "reach_head": ("Tema", "Risposte che nominano {subject}", "", "Concorrenti più nominati (risposte)"),
        "description_head": ("Tema", "Risposte"),
        "description_head_fidelity": ("Tema", "Risposte"),
        "facts_head": ("Dato di oggi", "Cosa riportano le risposte"),
        "facts_heads": {"current": "Lo riportano", "outdated": "Solo un dato vecchio", "silent": "Non lo dicono",
                        "favourable": "Risposte favorevoli"},
        "rated": {"4-5": "Risposta favorevole", "3": "Risposta neutra", "1-2": "Risposta sfavorevole"},
        "question_head": "Domanda",
        "bands": {"4-5": "Favorevoli", "3": "Neutre", "1-2": "Sfavorevoli"},
        "bands_fidelity": {"4-5": "Fedeli", "3": "Parziali", "1-2": "Lontane"},
        "bands_line": "favorevole se è positiva per {subject}, sfavorevole se è negativa o non trova quello che il criterio chiede, neutra se sta in mezzo",
        "bands_line_fidelity": "fedele ai fatti, parziale o lontana",
        "fact_parts": {"current": "Riportano il dato di oggi", "outdated": "Riportano solo un dato vecchio",
                       "silent": "Non riportano il dato"},
        "fact_source": "Fonte: {source}, {date}",
        "fact_from": "Da {n} domande",
        "fact_sites": "Pagine che le {n} risposte col solo dato vecchio citano e quelle col dato di oggi quasi mai (tra parentesi, quante risposte).",
        "fact_authors": {"owned": "Di {subject}", "third": "Di terzi", "foil": "Dei concorrenti"},
        "question": "Domanda",
        "assistant": "Assistente",
        "sources_head": ("Gruppo di domande", "Citano pagine di {subject}", "Citano pagine dei concorrenti",
                         "Citano altri siti: stampa, comparatori, recensioni", "Altri siti più citati (risposte)"),
        "method_title": "Come è stata fatta la rilevazione",
        "method_head": ("Progetto su Sentl", "Domande", "Assistenti", "Risposte", "Rilevazioni nel periodo"),
        "frequency": {"daily": "in programma ogni giorno", "weekly": "in programma ogni settimana",
                      "monthly": "in programma ogni mese", "none": "senza programmazione"},
        "scores_title": "Come è valutata ogni risposta",
        "scores": "Ogni domanda ha un proprio criterio, scritto prima di leggere le risposte, e ogni risposta è valutata in "
                  "automatico su quel criterio: {line}.",
        "scope_note": "Non tutti gli assistenti ricevono tutte le domande: la tabella dice quali.",
        "monitored_title": "Concorrenti monitorati",
        "owned_pages": "Pagine di {subject} più citate (risposte): {pages}.",
        "site_naming": "{domain} ({n} risposte, {k} con {subject})",
        "namesake": "un'altra organizzazione di nome {name}",
        "site_naming_note": "Sulle domande senza il nome, accanto a ogni sito: le risposte che lo citano e quante nominano {subject}.",
        "sources_overlap": "Una risposta può citare più tipi di fonte e conta allora in ciascuna delle loro colonne: sommando le "
                           "colonne la si conta più volte.",
        "limits_title": "Cosa queste risposte non dicono",
        "limit_versions": "Gli assistenti sono interrogati nelle versioni indicate, senza account né cronologia: l'app usata da "
                          "una persona può rispondere in modo diverso.",
        "where_title": "Dove leggere ogni risposta",
        "where": "Tutte le risposte, con le fonti citate, sono nell'app di Sentl.",
        "ask_title": "Per approfondire: da chiedere a Claude o ChatGPT collegati a Sentl",
        "questions_title": "Le {n} domande",
        "questions_more": "Le {n} domande ({page} di {pages})",
    },
    "en": {
        "of": "of",
        "cover_title": "What AI assistants answer about {subject}",
        "cover_what": "We put {questions} questions to {assistants}, as {who} would ask them, and collected and rated the "
                      "{answers} answers{parts}.",
        "cover_what_repeated": "We put {questions} questions to {assistants}, several times over, as {who} would ask them, and "
                               "collected and rated the {answers} answers{parts}.",
        "cover_parts": ": {reach} to the questions without {subject}'s name and {description} to those about {subject}",
        "assistant_one": "an AI assistant",
        "assistant_many": "AI assistants",
        "cover_first": "First reading",
        "cover_next": "Reading",
        "cover_by": "Prepared by {by}, with data from Sentl",
        "opening_title": "What this report shows",
        "purpose": "Purpose",
        "question_one": "question",
        "question_many": "questions",
        "answer_many": "answers",
        "overlap": "{n} of the questions in the other columns, {answers} answers",
        "card_assistants": "Assistants: {assistants}",
        "or": "or",
        "reading_title": "How the reading was made",
        "reading_answers": "Figures count answers, not questions: each question goes to {few} of these assistants, some "
                           "several times. {spread}.",
        "reading_answers_always": "Figures count answers, not questions: each question goes to {few} of these assistants, "
                                  "several times. {spread}.",
        "reading_answers_one": "Figures count answers, not questions: each question is repeated. {spread}.",
        "reading_answers_once": "Figures count answers, not questions: each question was asked once, to {few} of these "
                                "assistants. {spread}.",
        "spread_one": "Each question has {n} answers",
        "spread_first": "{q} questions have {n} answers each",
        "spread_rest": "{q} have {n}",
        "spread_rest_one": "{q} has {n}",
        "spread_range": "Each question has {low} to {high} answers",
        "reading_assistants": "Assistants: {assistants}.",
        "reading_scores": "Each answer is rated automatically, against criteria written for that question before the "
                          "answers were read: {bands}.",
        "reading_first": "This is the first reading: comparison over time starts with the next report.",
        "reading_once": "This is a single reading: asking the same questions again later shows what changes over time.",
        "reading_list": "Every question is listed on slide {n}.",
        "reading_list_many": "Every question is listed on slides {n}-{last}.",
        "origins_line": "The questions come from {origins}.",
        "origins": {"client_material": "the company's material", "client_issue": "the company's own requests",
                    "client_analysis": "analyses of {subject}", "search": "Google searches",
                    "probe": "a first trial with the assistants"},
        "found_kicker": "What we found",
        "actions_kicker": "What to do",
        "sources_kicker": "How many answers cite each source",
        "card": {"description": "Answers favourable for {subject}. This figure is not measured for competitors.", "description_fidelity": "Answers faithful to the facts",
                 "facts": "Answers stating today's figure"},
        "versus": "Answers out of {b} naming each name.",
        "and": "and",
        "close": "Compared with {subject}, {names}: a new reading can reverse the order.",
        "close_first": {"more": "{name} has {n} more {answers}", "fewer": "{name} has {n} fewer {answers}",
                        "same": "{name} has the same number of answers"},
        "close_next": {"more": "{name} {n} more", "fewer": "{name} {n} fewer", "same": "{name} the same number"},
        "close_answers": ("answer", "answers"),
        "rank": "{subject}: position {rank} of {field} names monitored; the first {shown} shown.",
        "rank_below": "{subject}: position {rank} of {field} names monitored; the first {shown} and {subject} shown.",
        "left_out": "Answers to a question that already names a competitor do not count for it.",
        "one_assistant": "Only {assistant} was asked these questions.",
        "groups": {"reach": "Questions without {subject}'s name", "description": "Questions about {subject}",
                   "facts": "Questions on {subject}'s facts"},
        "action": "Action {n}",
        "action_site": "{site}: cited by {n} of the {y} answers {where}.",
        "action_site_row": "{site}: cited by {n} of the {y} answers on «{label}».",
        "action_here": "to the questions on this slide",
        "action_there": "to the questions on slide {slide}",
        "action_lists": "{url} lists {names}, not {subject}.",
        "action_lists_with": "{url} lists {names}.",
        "share_kind": "monitoring deck",
        "share_span": "{start} to {end}",
        "action_shows": "{url} shows «{term}».",
        "action_page": "Page cited most: {page} ({n}).",
        "actions_head": ("No.", "What to do", "Why", "Slide"),
        "action_who": {"owned": "On {subject}'s own pages", "third": "A request to a third-party site"},
        "actions_note": "The next report measures the same figures again and sets them beside these.",
        "actions_note_once": "Asking the same questions again later shows whether these figures change.",
        "changed_kicker": "What changed since {then}",
        "changed_head": ("Question", "{then}", "{now}", "The figure"),
        "changed_values": {"up": "rose", "down": "fell", "same": "did not change", "small": "moved less than {step} points"},
        "changed_note": "The comparison keeps only the questions asked of the same assistants on both dates.",
        "earlier_kicker": "The actions proposed on {then}",
        "earlier_head": ("Action proposed", "The figure of {then}", "The same figure of {now}"),
        "earlier_note": "The figures do not say whether an action was taken or whether it moved the answers.",
        "reach_head": ("Topic", "Answers naming {subject}", "", "Competitors named most (answers)"),
        "description_head": ("Topic", "Answers"),
        "description_head_fidelity": ("Topic", "Answers"),
        "facts_head": ("Today's figure", "What the answers state"),
        "facts_heads": {"current": "State it", "outdated": "Only an old figure", "silent": "Do not state it",
                        "favourable": "Favourable answers"},
        "rated": {"4-5": "Favourable answer", "3": "Neutral answer", "1-2": "Unfavourable answer"},
        "question_head": "Question",
        "bands": {"4-5": "Favourable", "3": "Neutral", "1-2": "Unfavourable"},
        "bands_fidelity": {"4-5": "Faithful", "3": "Partial", "1-2": "Far off"},
        "bands_line": "favourable if it is positive for {subject}, unfavourable if it is negative or does not find what the criterion asks for, neutral if it falls in between",
        "bands_line_fidelity": "faithful to the facts, partial or far off",
        "fact_parts": {"current": "State today's figure", "outdated": "State only an old figure", "silent": "Do not state it"},
        "fact_source": "Source: {source}, {date}",
        "fact_from": "From {n} questions",
        "fact_sites": "Pages the {n} answers with only the old figure cite and those with today's hardly ever do (answers in brackets).",
        "fact_authors": {"owned": "{subject}'s", "third": "Third parties", "foil": "Competitors"},
        "question": "Question",
        "assistant": "Assistant",
        "sources_head": ("Group of questions", "Cite {subject}'s pages", "Cite competitors' pages",
                         "Cite other sites: press, comparison sites, reviews", "Other sites cited most (answers)"),
        "method_title": "How the reading was made",
        "method_head": ("Project in Sentl", "Questions", "Assistants", "Answers", "Times asked in the period"),
        "frequency": {"daily": "scheduled every day", "weekly": "scheduled every week", "monthly": "scheduled every month",
                      "none": "no schedule"},
        "scores_title": "How each answer is rated",
        "scores": "Each question has its own criteria, written before the answers were read, and each answer is rated "
                  "automatically against them: {line}.",
        "scope_note": "Not every assistant gets every question: the table says which.",
        "monitored_title": "Competitors monitored",
        "owned_pages": "{subject}'s pages cited most (answers): {pages}.",
        "site_naming": "{domain} ({n} answers, {k} with {subject})",
        "namesake": "another organisation named {name}",
        "site_naming_note": "On the questions without the name, beside each site: the answers citing it and how many name {subject}.",
        "sources_overlap": "An answer can cite more than one kind of source and then counts in each of their columns: adding "
                           "the columns counts it more than once.",
        "limits_title": "What these answers do not say",
        "limit_versions": "The assistants are asked in the versions listed, with no account or history: the app a person uses "
                          "may answer differently.",
        "where_title": "Where to read every answer",
        "where": "Every answer, with the sources it cites, is in the Sentl app.",
        "ask_title": "To go further: ask Claude or ChatGPT connected to Sentl",
        "questions_title": "The {n} questions",
        "questions_more": "The {n} questions ({page} of {pages})",
    },
}


# The quick deck (DEVPLAN M33): what its slides print beside the writer's texts. Its other words are the deck's (DECK).
QUICK = {
    "it": {
        "kind": "Sintesi",
        "share_kind": "sintesi",
        "cover_what": "Abbiamo fatto {questions} domande {assistants} e raccolto {answers} risposte{parts}.",
        "cover_what_repeated": "Abbiamo fatto {questions} domande {assistants}, più volte, e raccolto {answers} "
                               "risposte{parts}.",
        "naming": "risposte che nominano {subject}",
        "rival_one": "concorrente più nominato: {names}",
        "rival_many": "concorrenti più nominati: {names}",
        "no_rival": "nessun concorrente nominato",
        "bands": "favorevoli · neutre {mid} · sfavorevoli {bad}",
        "bands_fidelity": "fedeli · parziali {mid} · lontane {bad}",
        "quote_who": "{assistant}, alla domanda «{question}»",
        "sources_kicker": "Da dove leggono le risposte e come sono contate",
        "sources_title": "I siti più citati e come abbiamo contato",
        "reach_col": "Nelle {n} risposte alle domande senza il nome di {subject}",
        "description_col": "Nelle {n} risposte alle domande su {subject}",
        "own_site": "sito di {subject}",
        "no_sites": "Nessun sito citato",
        "count_note": "Il numero accanto a ogni sito conta le risposte che lo citano.",
        "assistants": "Assistenti interrogati: {makers}.",
        "asked_always": "Ogni domanda è stata posta più volte nel periodo.",
        "asked_some": "Alcune domande sono state poste più volte nel periodo.",
        "rating": "Le risposte alle domande su {subject} sono valutate da 1 a 5, con un criterio scritto per ogni "
                  "domanda: {bands}.",
        "rating_bands": "favorevole 4 o 5, neutra 3, sfavorevole 1 o 2",
        "rating_bands_fidelity": "fedele ai fatti 4 o 5, parziale 3, lontana 1 o 2",
        "presence": "Per le domande senza il nome di {subject} si conta in quante risposte compare {names}.",
    },
    "en": {
        "kind": "Summary",
        "share_kind": "summary",
        "cover_what": "We put {questions} questions to {assistants} and collected {answers} answers{parts}.",
        "cover_what_repeated": "We put {questions} questions to {assistants}, several times over, and collected {answers} "
                               "answers{parts}.",
        "naming": "answers naming {subject}",
        "rival_one": "competitor named most: {names}",
        "rival_many": "competitors named most: {names}",
        "no_rival": "no competitor named",
        "bands": "favourable · neutral {mid} · unfavourable {bad}",
        "bands_fidelity": "faithful · partial {mid} · far off {bad}",
        "quote_who": "{assistant}, asked “{question}”",
        "sources_kicker": "Where the answers read from, and how they are counted",
        "sources_title": "The sites cited most and how we counted",
        "reach_col": "In the {n} answers to the questions without {subject}'s name",
        "description_col": "In the {n} answers to the questions about {subject}",
        "own_site": "{subject}'s site",
        "no_sites": "No site cited",
        "count_note": "The number beside each site counts the answers citing it.",
        "assistants": "Assistants asked: {makers}.",
        "asked_always": "Each question was asked more than once in the period.",
        "asked_some": "Some questions were asked more than once in the period.",
        "rating": "The answers to the questions about {subject} are rated from 1 to 5, against criteria written for each "
                  "question: {bands}.",
        "rating_bands": "favourable 4 or 5, neutral 3, unfavourable 1 or 2",
        "rating_bands_fidelity": "faithful to the facts 4 or 5, partial 3, far off 1 or 2",
        "presence": "For the questions without {subject}'s name, the figure counts the answers in which {names} appears.",
    },
}


def join(items, lang):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {DECK[lang]['and']} " + items[-1]


# Phrases by which an answer says the assistant found no source of the kind the question asks
# for, matched on the folded answer (lower case, no accents). Each is anchored on the
# assistant's own search: the first person, "the provided results", or evidence that is not
# available or limited as such. Product sentences ("limited integrations", "a limited free
# plan") name no evidence, and a sentence whose subject is a third party (THIRD_PERSON: users,
# customers) reports someone else's experience, so neither counts.
EVIDENCE_EN = r"(?:information|data|details|reviews|sources|reports|testimonials|figures)"
EVIDENCE_IT = r"(?:informazion[ei]|dati|dettagli|recensioni|fonti|testimonianze|notizie)"
MISSING_EVIDENCE = {
    "en": [
        r"\b(?:not accessible|not available|unavailable|not found|limited|scarce|sparse|absent) (?:in|from|among) the "
        r"(?:provided |available |retrieved |returned |search )?(?:search )?(?:results|sources)\b",
        r"\bi (?:could not|couldn't|was unable to|am unable to|did not|didn't|cannot|can't) (?:find|locate|access|retrieve)"
        r"\b[^.]{0,60}?\b" + EVIDENCE_EN + r"\b",
        r"\bi (?:found|have found|see) (?:no|little|limited|few|only limited)\b[^.]{0,40}?\b" + EVIDENCE_EN + r"\b",
        r"\bno (?:(?:specific|reliable|public|detailed|recent|verified|employee|independent|current) )*" + EVIDENCE_EN
        + r" (?:(?:was|were|is|are|could be|can be) )?(?:found|available|located|publicly available)\b",
        r"\bthere (?:is|are|'s) (?:very |quite |only )?(?:limited|little|scarce|no|few) "
        r"(?:(?:public|reliable|specific|detailed|verified|independent|employee) )*" + EVIDENCE_EN + r"\b",
        r"\b" + EVIDENCE_EN + r" (?:on|about|for|regarding) [^.]{0,80}?\b(?:is|are|was|were|remains|remain) "
        r"(?:quite |very |rather |somewhat |fairly |extremely )?(?:limited|scarce|sparse|unavailable|not available|"
        r"hard to find)\b(?! to\b)",
        r"\b" + EVIDENCE_EN + r"\b[^.]{0,40}?\b(?:is|are) not publicly available\b",
    ],
    "it": [
        r"\b(?:non (?:e|sono) (?:stat[oaie] )?(?:accessibil[ei]|disponibil[ei]|trovat[oaie]|reperibil[ei])|"
        r"limitat[oaie]|scars[oaie]|assent[ei]) (?:nei|negli|nelle|tra i|tra le|dai|dalle) (?:risultati|fonti)\b",
        r"\bnon (?:ho|abbiamo) (?:trovato|reperito|individuato|potuto (?:trovare|reperire|consultare|accedere a))\b"
        r"[^.]{0,60}?\b" + EVIDENCE_IT + r"\b",
        r"\bnon (?:sono riuscit[oaie]|siamo riuscit[ie]) a (?:trovare|reperire)\b[^.]{0,60}?\b" + EVIDENCE_IT + r"\b",
        r"\bnon e stato possibile (?:trovare|reperire|accedere a)\b[^.]{0,60}?\b" + EVIDENCE_IT + r"\b",
        r"\bnon (?:sono|risultano|ci sono) (?:(?:disponibil[ei]|reperibil[ei]|pubblicamente disponibili) )?"
        r"(?:(?:molte|poche) )?" + EVIDENCE_IT + r"\b",
        r"\bnessun[ao]? (?:informazione|fonte|recensione|dato|testimonianza)\b[^.]{0,40}?"
        r"\b(?:disponibil[ei]|trovat[oaie]|reperibil[ei])\b",
        r"\b(?:le )?" + EVIDENCE_IT + r" (?:pubblic[hei]+ )?(?:su|sul|sullo|sulla|sui|sugli|sulle|riguardo a|"
        r"riguardo al|riguardo alla|relative a|relativi a) [^.]{0,80}?\b(?:sono|risultano|appaiono) "
        r"(?:piuttosto |molto |abbastanza |alquanto )?(?:limitat[ei]|scars[ei]|poch[ei]|insufficienti)\b",
        r"\bci sono (?:poche|scarse|pochissime) " + EVIDENCE_IT + r"\b",
    ],
}

# A third party as the subject of the sentence, before the phrase: its experience, not the
# assistant's search.
THIRD_PERSON = {
    "en": r"\b(?:users?|customers?|clients?|consumers?|buyers?|shoppers?|subscribers?)\b(?: [\w'-]+){0,3}? "
          r"(?:say|says|said|report|reports|reported|complain|complains|complained|note|noted|mention|mentioned|"
          r"could|can|cannot|can't|were|are|did|do|does|have|had)\b",
    "it": r"\b(?:utenti|utente|clienti|cliente|consumatori|acquirenti|abbonati)\b(?: [\w'-]+){0,3}? "
          r"(?:dicono|dice|hanno detto|segnalano|segnala|lamentano|lamenta|riferiscono|raccontano|non)\b",
}
