"""Report wording in the two report languages."""

SECTIONS = {
    "it": {
        "purpose": "Cosa abbiamo fatto e a che scopo",
        "themes": "Da dove vengono i temi",
        "dimensions": "Le dimensioni e come ci siamo arrivati",
        "questions": "Le domande",
        "scoring": "Come vengono valutate le risposte",
        "findings": "Cosa dicono gli assistenti",
        "changes": "Cosa è cambiato",
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
        "limits": "What a single run cannot show",
    },
}

FIRST_ORDER = ["purpose", "themes", "dimensions", "questions", "scoring", "findings", "changes"]

ORIGINS = {
    "it": {"client_material": "Materiali del cliente", "client_issue": "Questioni sollevate dal cliente",
           "client_analysis": "Altre analisi del cliente", "search": "Ricerche su Google",
           "probe": "Domande di prova"},
    "en": {"client_material": "The client's material", "client_issue": "Issues the client raised",
           "client_analysis": "The client's other analyses", "search": "Google searches",
           "probe": "Pilot questions"},
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
        "paired": "Dove una domanda ha la sua opposta, abbiamo posto entrambe le versioni, in positivo e in negativo.",
        "collected": "Nel periodo sono state raccolte {received} risposte, {judged} delle quali valutate.",
        "sources": "Per ogni risposta abbiamo registrato le fonti citate dall'assistente.",
        "no_search": "Nessun dato di ricerca è stato raccolto per questo studio: i temi vengono dalle fonti elencate sopra.",
        "from_theme": "dal tema «{theme}» ({origins})",
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
        "finding_title": "[[titolo: cosa viene detto a chi chiede]]",
        "finding_body": "[[da scrivere: {dimension}]]",
        "first": "Questa è la prima misurazione: il prossimo rapporto si confronterà con questa.",
    },
    "en": {
        "and": "and",
        "title_period": "{subject} · period from {start} to {end} · report of {date}",
        "title_day": "{subject} · measured on {start} · report of {date}",
        "asked": "We asked {questions} questions to {count} AI assistants: {names}.",
        "asked_one": "We asked {questions} questions to one AI assistant: {names}.",
        "paired": "Where a question has an opposite, we asked both versions, in positive and in negative.",
        "collected": "In the period {received} answers were collected, {judged} of them scored.",
        "sources": "For each answer we recorded the sources the assistant cited.",
        "no_search": "No search data was collected for this study: the themes come from the sources listed above.",
        "from_theme": "from the theme “{theme}” ({origins})",
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
        "finding_title": "[[title: what the person asking is told]]",
        "finding_body": "[[to write: {dimension}]]",
        "first": "This is the first measurement: the next report compares against it.",
    },
}


def join(items, lang):
    items = list(items)
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + f" {TEXT[lang]['and']} " + items[-1]
