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
LATER_ORDER = ["summary", "changes", "findings", "purpose", "themes", "dimensions", "questions", "scoring"]

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
