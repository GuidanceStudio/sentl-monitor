"""Report wording in the two report languages."""

import re

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

FIRST_ORDER = ["purpose", "themes", "dimensions", "questions", "scoring", "summary", "findings", "changes"]
SNAPSHOT_ORDER = ["purpose", "dimensions", "questions", "scoring", "findings", "limits"]
LATER_ORDER = ["summary", "changes", "findings", "purpose", "themes", "dimensions", "questions", "scoring"]
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

ORIGINS = {
    "it": {"client_material": "Materiali del cliente", "client_issue": "Questioni sollevate dal cliente",
           "client_analysis": "Altre analisi del cliente", "search": "Ricerche su Google",
           "probe": "Domande di prova"},
    "en": {"client_material": "The client's material", "client_issue": "Issues the client raised",
           "client_analysis": "The client's other analyses", "search": "Google searches",
           "probe": "Pilot questions"},
}

# The same origins inside a sentence: lower case except proper nouns.
ORIGINS_INLINE = {
    "it": {"client_material": "materiali del cliente", "client_issue": "questioni sollevate dal cliente",
           "client_analysis": "altre analisi del cliente", "search": "ricerche su Google",
           "probe": "domande di prova"},
    "en": {"client_material": "the client's material", "client_issue": "issues the client raised",
           "client_analysis": "the client's other analyses", "search": "Google searches",
           "probe": "pilot questions"},
}

AUDIENCE = {
    "it": {"generic_consumer": "un consumatore qualsiasi", "personas": "persone con profili diversi",
           "stakeholders": "i portatori di interesse del cliente", "mixed": "un insieme di profili"},
    "en": {"generic_consumer": "a generic consumer", "personas": "people with different profiles",
           "stakeholders": "the client's stakeholders", "mixed": "a mix of profiles"},
}

TEXT = {
    "it": {
        "and": "e",
        "title_period": "{subject} · periodo dal {start} al {end} · rapporto del {date}",
        "title_day": "{subject} · rilevazione del {start} · rapporto del {date}",
        "asked": "Abbiamo posto {questions} domande a {count} assistenti AI: {names}.",
        "asked_one": "Abbiamo posto {questions} domande a un assistente AI: {names}.",
        "asked_projects": "Abbiamo posto le domande in {count} progetti:",
        "project_questions": ("{n} domanda", "{n} domande"),
        "project_assistants": ("a un assistente AI ({names})", "a {count} assistenti AI ({names})"),
        "project_rounds": ("ciascuna posta una volta per rilevazione", "ciascuna posta {rounds} volte per rilevazione"),
        "schedule": {"daily": "con una rilevazione al giorno", "weekly": "con una rilevazione a settimana",
                     "monthly": "con una rilevazione al mese"},
        "shared_rubric": "Criteri comuni a più domande",
        "shared_note": "I criteri comuni a più domande sono riportati una volta per tutte, con i cinque punteggi.",
        "anchors_all": "5: {a5} · 4: {a4} · 3: {a3} · 2: {a2} · 1: {a1}",
        "paired": "Dove una domanda ha la sua opposta, abbiamo posto entrambe le versioni, in positivo e in negativo.",
        "collected": "Nel periodo sono state raccolte {received} risposte, {judged} delle quali valutate.",
        "sources": "Per ogni risposta abbiamo registrato le fonti citate dall'assistente.",
        "no_search": "Nessun dato di ricerca è stato raccolto per questo studio: i temi vengono dalle fonti elencate sopra.",
        "demand_title": "Domanda di ricerca",
        "demand_suggestions": ("{n} suggerimento distinto di Google", "{n} suggerimenti distinti di Google"),
        "demand_monthly": "Ricerche al mese: {classes} ({provider}, {when}).",
        "volume_classes": {"subject": "che nominano il soggetto", "foil": "che nominano un concorrente",
                           "component": "sul solo componente", "generic": "altre ricerche"},
        "no_volume": "I conteggi sono suggerimenti di Google: misurano in quanti modi un tema viene formulato, "
                     "non quante persone lo cercano.",
        "from_theme": "dal tema «{theme}» ({origins})",
        "from_origins": "da {origins}",
        "who_asks": "Chi pone le domande: {audience}. {reason}",
        "persona_beside": "Il profilo di chi chiede è indicato accanto a ogni domanda.",
        "project_question": "Domanda del progetto: {question}",
        "project_decision": "Decisione che informa: {decision}",
        "asked_by": "chi chiede: {persona}",
        "judge": "Un modello indipendente, in Sentl, ha valutato ogni risposta da 1 a 5 secondo criteri scritti per "
                 "ciascuna domanda da {by} il {date}. Per ogni domanda indichiamo cosa significano 5, 3 e 1.",
        "anchors": "5: {a5} · 3: {a3} · 1: {a1}",
        "figures": "Il punteggio di una dimensione è la media delle sue risposte valutate; il punteggio complessivo "
                   "è la media delle dimensioni. Una dimensione con meno dell'80% delle risposte valutate è "
                   "descritta senza punteggio.",
        "axis_stance": "Un punteggio alto dice che le risposte sono favorevoli a {subject}, con argomenti; "
                       "non dice che sono accurate.",
        "axis_fidelity": "Un punteggio alto dice che le risposte sono accurate rispetto ai fatti forniti al giudice; "
                         "non dice che sono favorevoli a {subject}.",
        "axis_none": "Un punteggio alto dice che le risposte soddisfano i criteri; non misura quanto spesso "
                     "{subject} viene nominato, che è riportato a parte come presenza.",
        "snapshot_why": "Perché è stata scelta",
        "figures_snapshot": "Il punteggio di una dimensione è la media delle sue risposte valutate. Non c'è un "
                            "punteggio complessivo: ogni dimensione si legge da sola. Una dimensione con meno "
                            "dell'80% delle risposte valutate è descritta senza punteggio.",
        "snapshot_reading": "Una dimensione la cui domanda nomina {subject} si legge dal punteggio; una la cui "
                            "domanda non nomina nessun marchio si legge da se e dove {subject} compare nelle risposte.",
        "limits_body": ("Ogni dimensione poggia su una sola domanda e su una sola risposta di ciascun assistente, "
                        "date il {date}.",
                        "Uno studio di monitoraggio aggiunge più domande per dimensione, domande in versione "
                        "positiva e negativa e rilevazioni ripetute, confrontate periodo per periodo."),
        "finding_title": "[[titolo: cosa viene detto a chi chiede]]",
        "finding_body": "[[da scrivere: {dimension}]]",
        "first": "Questa è la prima misurazione: il prossimo rapporto si confronterà con questa.",
        "change_rule": "Tra un periodo e l'altro, il punteggio di una dimensione o di una domanda è dato come cambiato "
                       "quando esce dall'intervallo dei quattro periodi precedenti e si discosta dal precedente di "
                       "almeno 0,3 punti, 0,5 se c'è un solo periodo precedente; la presenza, quando si discosta di "
                       "almeno 10 punti percentuali, 20 con un solo periodo precedente. Il giudizio di un assistente "
                       "su una domanda è sfavorevole sotto 2,5, intermedio da 2,5 a 3,5 e favorevole da 3,5 in su; un "
                       "cambio di giudizio è riportato solo quando la media dell'assistente sulla domanda si sposta "
                       "anche di almeno 0,3 punti, 0,5 con un solo periodo precedente.",
        "changes_marker": "[[da scrivere: cosa è cambiato nelle risposte rispetto al periodo precedente]]",
        "changes_marker_halves": "[[da scrivere: cosa è cambiato nelle risposte tra la prima e la seconda metà del "
                                 "periodo]]",
        "compared_period": "Il confronto è con il periodo precedente, dal {start} al {end}.",
        "compared_day": "Il confronto è con la rilevazione precedente, del {start}.",
        "rebuilt_previous": "Non c'è un rapporto precedente: i dati del confronto vengono dalle rilevazioni già "
                            "presenti nel progetto.",
        "halves": "Non essendoci un periodo precedente, la seconda metà di questo periodo, {second}, è confrontata con "
                  "la prima, {first}.",
        "span": "dal {start} al {end}",
        "span_day": "il {start}",
        "half_counts": "{project}: {runs1} e {answers1} nella prima metà, {runs2} e {answers2} nella seconda.",
        "half_counts_one": "{project}: {runs} e {answers} solo nella {half} metà, quindi non è confrontato.",
        "half_names": {"first": "prima", "second": "seconda"},
        "runs_n": ("{n} rilevazione", "{n} rilevazioni"),
        "answers_n": ("{n} risposta", "{n} risposte"),
        "reworded": "Dal {since} la domanda «{previous}» è posta nella formulazione «{text}».",
        "new_intent": "Dal {since} la domanda «{text}» sostituisce «{previous}»: il confronto per questa domanda "
                      "riparte da questo periodo.",
        "criteria": "Dal {since} i criteri di valutazione della domanda «{text}» sono cambiati: il suo punteggio "
                    "riparte da questo periodo e non è confrontato con i precedenti.",
        "created": "Dal {since} è posta anche la domanda «{text}»: il confronto per questa domanda parte da questo "
                   "periodo.",
        "retired": "La domanda «{previous}» non è più posta.",
        "dimension_added": "La dimensione {name} è nuova: il confronto parte da questo periodo.",
        "dimension_archived": "La dimensione {name} non è più misurata.",
        "models_added": ("In questo periodo risponde anche {names}.", "In questo periodo rispondono anche {names}."),
        "models_removed": ("{names} non risponde più.", "{names} non rispondono più."),
        "models_basis": ("I confronti sono calcolati sulle risposte dell'unico assistente presente in entrambi i "
                         "periodi, {names}.",
                         "I confronti sono calcolati sulle risposte degli assistenti presenti in entrambi i periodi: "
                         "{names}."),
        "models_none": "Nessun assistente è presente in entrambi i periodi: i punteggi non sono confrontati.",
        "models_basis_halves": ("I confronti sono calcolati sulle risposte dell'unico assistente presente in entrambe "
                                "le metà, {names}.",
                                "I confronti sono calcolati sulle risposte degli assistenti presenti in entrambe le "
                                "metà: {names}."),
        "models_none_halves": "Nessun assistente è presente in entrambe le metà: i punteggi non sono confrontati.",
    },
    "en": {
        "and": "and",
        "title_period": "{subject} · period from {start} to {end} · report of {date}",
        "title_day": "{subject} · measured on {start} · report of {date}",
        "asked": "We asked {questions} questions to {count} AI assistants: {names}.",
        "asked_one": "We asked {questions} questions to one AI assistant: {names}.",
        "asked_projects": "We asked the questions in {count} projects:",
        "project_questions": ("{n} question", "{n} questions"),
        "project_assistants": ("to one AI assistant ({names})", "to {count} AI assistants ({names})"),
        "project_rounds": ("each asked once per run", "each asked {rounds} times per run"),
        "schedule": {"daily": "run every day", "weekly": "run every week", "monthly": "run every month"},
        "shared_rubric": "Criteria shared by several questions",
        "shared_note": "Criteria shared by several questions are given once for all of them, with the five points.",
        "anchors_all": "5: {a5} · 4: {a4} · 3: {a3} · 2: {a2} · 1: {a1}",
        "paired": "Where a question has an opposite, we asked both versions, in positive and in negative.",
        "collected": "In the period {received} answers were collected, {judged} of them scored.",
        "sources": "For each answer we recorded the sources the assistant cited.",
        "no_search": "No search data was collected for this study: the themes come from the sources listed above.",
        "demand_title": "Search demand",
        "demand_suggestions": ("{n} distinct Google suggestion", "{n} distinct Google suggestions"),
        "demand_monthly": "Monthly searches: {classes} ({provider}, {when}).",
        "volume_classes": {"subject": "naming the subject", "foil": "naming a competitor",
                           "component": "about the component alone", "generic": "other searches"},
        "no_volume": "The counts are Google suggestions: they measure how many ways a theme is phrased, "
                     "not how many people search it.",
        "from_theme": "from the theme “{theme}” ({origins})",
        "from_origins": "from {origins}",
        "who_asks": "Who asks: {audience}. {reason}",
        "persona_beside": "The profile of who asks is given beside each question.",
        "project_question": "The project's question: {question}",
        "project_decision": "The decision it informs: {decision}",
        "asked_by": "asked by: {persona}",
        "judge": "An independent model, in Sentl, scored each answer from 1 to 5 against criteria written for each "
                 "question by {by} on {date}. For each question we give what 5, 3 and 1 mean.",
        "anchors": "5: {a5} · 3: {a3} · 1: {a1}",
        "figures": "A dimension's score is the mean of its scored answers; the overall score is the mean of the "
                   "dimensions. A dimension with fewer than 80% of its answers scored is described without a score.",
        "axis_stance": "A high score means the answers are favourable to {subject}, with grounds; "
                       "it does not mean they are accurate.",
        "axis_fidelity": "A high score means the answers are accurate against the facts given to the judge; "
                         "it does not mean they are favourable to {subject}.",
        "axis_none": "A high score means the answers meet the criteria; it does not measure how often {subject} "
                     "is named, which is reported separately as presence.",
        "snapshot_why": "Why it was chosen",
        "figures_snapshot": "A dimension's score is the mean of its scored answers. There is no overall score: each "
                            "dimension is read on its own. A dimension with fewer than 80% of its answers scored is "
                            "described without a score.",
        "snapshot_reading": "A dimension whose question names {subject} is read by its score; one whose question "
                            "names no brand is read by whether and where {subject} appears in the answers.",
        "limits_body": ("Each dimension rests on one question and on one answer from each assistant, given on "
                        "{date}.",
                        "A monitoring study adds several questions per dimension, questions asked in a positive and "
                        "a negative version, and repeated runs compared period by period."),
        "finding_title": "[[title: what the person asking is told]]",
        "finding_body": "[[to write: {dimension}]]",
        "first": "This is the first measurement: the next report compares against it.",
        "change_rule": "Between periods, the score of a dimension or a question is reported as changed when it lies "
                       "outside the range of the four previous periods and differs from the previous one by at least "
                       "0.3 points, or 0.5 with a single previous period; presence, when it differs by at least 10 "
                       "percentage points, or 20 with a single previous period. An assistant's verdict on a question is "
                       "unfavourable below 2.5, mixed from 2.5 to 3.5 and favourable from 3.5; a change of verdict is "
                       "reported only when the assistant's mean on the question also moves by at least 0.3 points, or "
                       "0.5 with a single previous period.",
        "changes_marker": "[[to write: what changed in the answers since the previous period]]",
        "changes_marker_halves": "[[to write: what changed in the answers between the first and the second half of "
                                 "the period]]",
        "compared_period": "The comparison is with the previous period, from {start} to {end}.",
        "compared_day": "The comparison is with the previous measurement, of {start}.",
        "rebuilt_previous": "There is no earlier report: the data compared come from the runs already in the project.",
        "halves": "There is no earlier period, so the second half of this period, {second}, is compared with the first "
                  "half, {first}.",
        "span": "from {start} to {end}",
        "span_day": "on {start}",
        "half_counts": "{project}: {runs1} and {answers1} in the first half, {runs2} and {answers2} in the second.",
        "half_counts_one": "{project}: {runs} and {answers} in the {half} half only, so it is not compared.",
        "half_names": {"first": "first", "second": "second"},
        "runs_n": ("{n} run", "{n} runs"),
        "answers_n": ("{n} answer", "{n} answers"),
        "reworded": "From {since} the question «{previous}» is asked as «{text}».",
        "new_intent": "From {since} the question «{text}» replaces «{previous}»: the comparison for this question "
                      "starts again from this period.",
        "criteria": "From {since} the scoring criteria of the question «{text}» changed: its score starts again from "
                    "this period and is not compared with earlier ones.",
        "created": "From {since} the question «{text}» is also asked: its comparison starts from this period.",
        "retired": "The question «{previous}» is no longer asked.",
        "dimension_added": "The dimension {name} is new: its comparison starts from this period.",
        "dimension_archived": "The dimension {name} is no longer measured.",
        "models_added": ("In this period {names} also answers.", "In this period {names} also answer."),
        "models_removed": ("{names} no longer answers.", "{names} no longer answer."),
        "models_basis": ("The comparisons use the answers of the one assistant present in both periods, {names}.",
                         "The comparisons use the answers of the assistants present in both periods: {names}."),
        "models_none": "No assistant is present in both periods: the scores are not compared.",
        "models_basis_halves": ("The comparisons use the answers of the one assistant present in both halves, {names}.",
                                "The comparisons use the answers of the assistants present in both halves: {names}."),
        "models_none_halves": "No assistant is present in both halves: the scores are not compared.",
    },
}


# The chart file for a deck: a heading per chart naming what it shows and the period or halves it
# covers as the report names them, and an md2 title with the unit.
CHARTS = {
    "it": {
        "file_title": "{subject}: grafici del rapporto del {date}",
        "profile": "{project}: punteggio medio per dimensione, {covers}",
        "profile_title": "Punteggio medio per dimensione (1–5)",
        "by_model": "{project}: punteggio medio per dimensione e assistente, {covers}",
        "by_model_title": "Punteggio medio per dimensione e assistente (1–5)",
        "currency": "{project} · {dimension}, «{question}»: risposte che riportano il dato attuale, su quelle che lo "
                    "riportano attuale o superato, per rilevazione, {covers}",
        "currency_title": "Risposte che riportano il dato attuale (%)",
        "presence": "{project} · {dimension}, «{question}»: risposte che nominano {subject}, per rilevazione, {covers}",
        "presence_title": "Risposte che nominano {subject} (%)",
        "sources_fact": "{project} · {dimension}, «{question}»: domini citati dalle risposte che riportano solo il dato "
                        "superato e da quelle che riportano il dato attuale, {covers}",
        "sources_score": "{project} · {dimension}, «{question}»: domini citati dalle risposte con punteggio 1-2 e da "
                         "quelle con punteggio 4-5, {covers}",
        "sources_title": "Risposte che citano il dominio, su quelle del gruppo che citano una fonte (%)",
        "groups": {"outdated": "Solo il dato superato", "current": "Il dato attuale", "low": "Punteggio 1-2",
                   "high": "Punteggio 4-5"},
        "half": {"first": "prima metà", "second": "seconda metà"},
        # [halves][plural], worded as the report's own sentences (models_basis, models_basis_halves).
        "basis_models": (("sulle risposte dell'unico assistente presente in entrambi i periodi, {names}",
                          "sulle risposte degli assistenti presenti in entrambi i periodi: {names}"),
                         ("sulle risposte dell'unico assistente presente in entrambe le metà, {names}",
                          "sulle risposte degli assistenti presenti in entrambe le metà: {names}")),
        "basis_questions": (("senza {questions}, non confrontabile tra i due periodi",
                             "senza {questions}, non confrontabili tra i due periodi"),
                            ("senza {questions}, non confrontabile tra le due metà",
                             "senza {questions}, non confrontabili tra le due metà")),
        "own_runs": "rilevazioni",
        "dimension": "Dimensione", "run": "Rilevazione", "domain": "Dominio",
    },
    "en": {
        "file_title": "{subject}: charts of the report of {date}",
        "profile": "{project}: mean score by dimension, {covers}",
        "profile_title": "Mean score by dimension (1–5)",
        "by_model": "{project}: mean score by dimension and assistant, {covers}",
        "by_model_title": "Mean score by dimension and assistant (1–5)",
        "currency": "{project} · {dimension}, «{question}»: answers stating the current fact, of those stating it "
                    "current or outdated, by run, {covers}",
        "currency_title": "Answers stating the current fact (%)",
        "presence": "{project} · {dimension}, «{question}»: answers naming {subject}, by run, {covers}",
        "presence_title": "Answers naming {subject} (%)",
        "sources_fact": "{project} · {dimension}, «{question}»: domains cited by the answers stating only the outdated "
                        "fact and by those stating the current one, {covers}",
        "sources_score": "{project} · {dimension}, «{question}»: domains cited by the answers scored 1-2 and by those "
                         "scored 4-5, {covers}",
        "sources_title": "Answers citing the domain, of the group's answers citing a source (%)",
        "groups": {"outdated": "Outdated fact only", "current": "Current fact", "low": "Scored 1-2",
                   "high": "Scored 4-5"},
        "half": {"first": "first half", "second": "second half"},
        "basis_models": (("on the answers of the one assistant present in both periods, {names}",
                          "on the answers of the assistants present in both periods: {names}"),
                         ("on the answers of the one assistant present in both halves, {names}",
                          "on the answers of the assistants present in both halves: {names}")),
        "basis_questions": (("without {questions}, not comparable between the two periods",) * 2,
                            ("without {questions}, not comparable between the two halves",) * 2),
        "own_runs": "runs",
        "dimension": "Dimension", "run": "Run", "domain": "Domain",
    },
}


# The labels of the deck. A label states what its value asserts, in the words of the language.
DECK = {
    "it": {
        "of": "su",
        "cover_title": "Cosa rispondono gli assistenti AI su {subject}",
        "cover_what": "Abbiamo fatto {questions} domande {assistants}, come le farebbero {who}, "
                      "e abbiamo raccolto e valutato le {answers} risposte.",
        "cover_what_repeated": "Abbiamo fatto {questions} domande {assistants}, più volte, come le farebbero {who}, "
                               "e abbiamo raccolto e valutato le {answers} risposte.",
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
        "spread_one": "Ogni domanda ha {n} risposte",
        "spread_first": "{q} domande hanno {n} risposte ciascuna",
        "spread_rest": "{q} ne hanno {n}",
        "spread_rest_one": "{q} ne ha {n}",
        "spread_range": "Ogni domanda ha tra {low} e {high} risposte",
        "reading_assistants": "Assistenti: {assistants}.",
        "reading_scores": "Ogni risposta è valutata in automatico, con un criterio scritto per quella domanda prima di "
                          "leggere le risposte: {bands}.",
        "reading_first": "È la prima rilevazione: il confronto nel tempo parte dal prossimo report.",
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
        "close": "{names} sono a {gap} risposte o meno da {subject}: il prossimo report può invertire l'ordine.",
        "close_one": "{names} è a {gap} risposte o meno da {subject}: il prossimo report può invertire l'ordine.",
        "rank": "{subject}: posizione {rank} su {field} nomi monitorati; qui i primi {shown}.",
        "rank_below": "{subject}: posizione {rank} su {field} nomi monitorati; qui i primi {shown} e {subject}.",
        "left_out": "Non si contano le risposte a domande che nominano già quel concorrente.",
        "one_assistant": "A queste domande risponde solo {assistant}.",
        "groups": {"reach": "Domande senza il nome di {subject}", "description": "Domande su {subject}",
                   "facts": "Domande sui dati di {subject}"},
        "action": "Azione {n}",
        "action_site": "{site}: citato da {n} delle {y} risposte {where}.",
        "action_here": "alle domande di questa slide",
        "action_there": "alle domande della slide {slide}",
        "action_lists": "{url} elenca {names}, non {subject}.",
        "action_lists_with": "{url} elenca {names}.",
        "action_shows": "{url} riporta «{term}».",
        "action_page": "Pagina più citata: {page} ({n}).",
        "actions_head": ("N.", "Cosa fare", "Perché", "Slide"),
        "action_who": {"owned": "Sulle pagine di {subject}", "third": "Richiesta a un sito di terzi"},
        "actions_note": "Il prossimo report rimisura gli stessi numeri e li mette accanto a questi.",
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
        "method_head": ("Progetto su Sentl", "Domande", "Assistenti", "Risposte", "Frequenza prevista"),
        "frequency": {"daily": "Ogni giorno", "weekly": "Ogni settimana", "monthly": "Ogni mese"},
        "scores_title": "Come è valutata ogni risposta",
        "scores": "Ogni domanda ha un proprio criterio, scritto prima di leggere le risposte, e ogni risposta è valutata in "
                  "automatico su quel criterio: {line}.",
        "scope_note": "Non tutti gli assistenti ricevono tutte le domande: la tabella dice quali.",
        "monitored_title": "Concorrenti monitorati",
        "owned_pages": "Pagine di {subject} più citate (risposte): {pages}.",
        "site_naming": "{domain} ({n} risposte, {k} con {subject})",
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
                      "{answers} answers.",
        "cover_what_repeated": "We put {questions} questions to {assistants}, several times over, as {who} would ask them, and "
                               "collected and rated the {answers} answers.",
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
        "spread_one": "Each question has {n} answers",
        "spread_first": "{q} questions have {n} answers each",
        "spread_rest": "{q} have {n}",
        "spread_rest_one": "{q} has {n}",
        "spread_range": "Each question has {low} to {high} answers",
        "reading_assistants": "Assistants: {assistants}.",
        "reading_scores": "Each answer is rated automatically, against criteria written for that question before the "
                          "answers were read: {bands}.",
        "reading_first": "This is the first reading: comparison over time starts with the next report.",
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
        "close": "{names} are within {gap} answers of {subject}: the next report can reverse the order.",
        "close_one": "{names} is within {gap} answers of {subject}: the next report can reverse the order.",
        "rank": "{subject}: position {rank} of {field} names monitored; the first {shown} shown.",
        "rank_below": "{subject}: position {rank} of {field} names monitored; the first {shown} and {subject} shown.",
        "left_out": "Answers to a question that already names a competitor do not count for it.",
        "one_assistant": "Only {assistant} was asked these questions.",
        "groups": {"reach": "Questions without {subject}'s name", "description": "Questions about {subject}",
                   "facts": "Questions on {subject}'s facts"},
        "action": "Action {n}",
        "action_site": "{site}: cited by {n} of the {y} answers {where}.",
        "action_here": "to the questions on this slide",
        "action_there": "to the questions on slide {slide}",
        "action_lists": "{url} lists {names}, not {subject}.",
        "action_lists_with": "{url} lists {names}.",
        "action_shows": "{url} shows «{term}».",
        "action_page": "Page cited most: {page} ({n}).",
        "actions_head": ("No.", "What to do", "Why", "Slide"),
        "action_who": {"owned": "On {subject}'s own pages", "third": "A request to a third-party site"},
        "actions_note": "The next report measures the same figures again and sets them beside these.",
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
        "method_head": ("Project in Sentl", "Questions", "Assistants", "Answers", "Planned frequency"),
        "frequency": {"daily": "Every day", "weekly": "Every week", "monthly": "Every month"},
        "scores_title": "How each answer is rated",
        "scores": "Each question has its own criteria, written before the answers were read, and each answer is rated "
                  "automatically against them: {line}.",
        "scope_note": "Not every assistant gets every question: the table says which.",
        "monitored_title": "Competitors monitored",
        "owned_pages": "{subject}'s pages cited most (answers): {pages}.",
        "site_naming": "{domain} ({n} answers, {k} with {subject})",
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


def join(items, lang):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {TEXT[lang]['and']} " + items[-1]


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


# An Italian articulated preposition before a date elides when the day's number starts with a
# vowel sound (otto, undici): dall'8, all'11, dell'8, l'8.
ELIDED = {"il": "l'", "dal": "dall'", "al": "all'", "del": "dell'", "Dal": "Dall'"}
DATE_AFTER = re.compile(r"\b(il|dal|al|del|Dal) \{(\w+)\}")
VOWEL_DAY = re.compile(r"(?:8|11) ")


def phrase(lang, key, **values):
    """TEXT[lang][key] filled with `values`, every date already written by `fmt_date`. Each
    sentence that carries a date goes through here, so an Italian preposition before it elides."""
    template = TEXT[lang][key]
    if lang == "it":
        template = DATE_AFTER.sub(lambda m: ELIDED[m.group(1)] + "{" + m.group(2) + "}"
                                  if VOWEL_DAY.match(str(values.get(m.group(2), ""))) else m.group(0), template)
    return template.format(**values)
