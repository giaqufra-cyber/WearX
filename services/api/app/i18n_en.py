"""Traduzioni inglesi dei testi del server (seduta 34). Chiave: il testo italiano.

Un test (tests/test_i18n.py) controlla che ogni testo usato nel codice sia qui, con gli stessi
segnaposto, e che qui non restino testi che il codice non usa più.
"""

EN: dict[str, str] = {
    # Accesso e account (auth.py, profiles.py, middleware.py, errors.py)
    "Sessione scaduta": "Session expired",
    "Serve un account WearX": "You need a WearX account",
    "Token non valido": "Invalid token",
    "Accesso richiesto": "Sign-in required",
    "Accesso momentaneamente non verificabile": "We can't verify your sign-in right now",
    "Completa la registrazione per continuare": "Finish signing up to continue",
    "Accesso terminato da un altro dispositivo": "Signed out from another device",
    "Account sospeso": "Account suspended",
    "Account in cancellazione": "Account being deleted",
    "Aggiorna WearX per continuare": "Update WearX to continue",
    "Dati non validi": "Invalid data",
    "Errore interno": "Internal error",
    "Troppe richieste, riprova tra poco": "Too many requests, try again shortly",
    "Risorsa non trovata": "Not found",
    "Serve l'app ufficiale su un dispositivo verificato": (
        "You need the official app on a verified device"
    ),
    "Serve l'accesso con il secondo fattore": "Two-factor sign-in required",
    "Serve il ruolo di amministratore": "Administrator role required",
    # Profilo e registrazione
    "Gli account Business non sono ancora disponibili": "Business accounts aren't available yet",
    "Il profilo Business è solo per maggiorenni": "Business profiles are for adults only",
    "I termini sono cambiati: rileggili e accettali di nuovo": (
        "The terms have changed: read them and accept them again"
    ),
    "Nickname non valido": "Invalid nickname",
    "Questo nickname non è disponibile": "This nickname isn't available",
    "Nickname già in uso": "Nickname already taken",
    "Prima va verificata l'età": "Your age needs to be verified first",
    "Uno degli stili scelti è riservato ai 18+": "One of the styles you chose is for 18+ only",
    "Il profilo esiste già": "The profile already exists",
    "Questo account è privato": "This account is private",
    "Profilo non trovato": "Profile not found",
    "La foto non è pronta o non è tua": "The photo isn't ready or isn't yours",
    "Questa foto non può essere usata come foto profilo": (
        "This photo can't be used as a profile photo"
    ),
    # Verifica dell'età e del dispositivo
    "Metodo di verifica non disponibile": "Verification method not available",
    "Indirizzo di ritorno non ammesso": "Return address not allowed",
    "Data di nascita non valida": "Invalid date of birth",
    "L'età è già verificata": "Your age is already verified",
    "WearX è riservata a chi ha almeno 16 anni": "WearX is only for people aged 16 and over",
    "Il servizio di verifica non risponde, riprova": (
        "The verification service isn't responding, try again"
    ),
    "Webhook non valido": "Invalid webhook",
    "Verifica non trovata": "Verification not found",
    "Fornitore sconosciuto": "Unknown provider",
    "Accesso senza sessione: rientra nell'app": "Signed in without a session: open the app again",
    "Verifica del dispositivo non riuscita": "Device check failed",
    "Verifica del dispositivo non disponibile": "Device check not available",
    "Chiave del dispositivo sconosciuta": "Unknown device key",
    # Testi liberi (text_policy.py) e nomi dei campi
    "{field} contiene caratteri non ammessi": "{field} contains characters that aren't allowed",
    "{field} può avere al massimo {max_chars} caratteri": (
        "{field} can be at most {max_chars} characters"
    ),
    "{field} contiene parole non ammesse": "{field} contains words that aren't allowed",
    "{field} può avere al massimo {max_lines} righe": "{field} can be at most {max_lines} lines",
    "La bio": "The bio",
    "La didascalia": "The caption",
    "Il brand": "The brand",
    "Il nome del capo": "The item name",
    "Il nome della capsula": "The capsule name",
    "Il nome dello stile": "The style name",
    "La descrizione": "The description",
    "Il testo può avere al massimo {max_chars} caratteri": (
        "The text can be at most {max_chars} characters"
    ),
    # Fit, foto e capsule
    "Cursore del feed non valido": "Invalid feed cursor",
    "Il feed è scaduto: ricarica": "The feed has expired: refresh",
    "Cursore non valido": "Invalid cursor",
    "Posizione non valida": "Invalid position",
    "Troppe foto in caricamento: finisci prima": "Too many photos uploading: finish those first",
    "La foto non è ancora arrivata": "The photo hasn't arrived yet",
    "La foto è troppo pesante": "The photo is too large",
    "Foto non trovata": "Photo not found",
    "Dai un nome alla capsula": "Give the capsule a name",
    "Hai già una capsula con questo nome": "You already have a capsule with this name",
    "Puoi avere al massimo {max} capsule": "You can have at most {max} capsules",
    "Capsula non trovata": "Capsule not found",
    "Stile non disponibile": "Style not available",
    "Il capo punta a una foto che non c'è": "The item points to a photo that doesn't exist",
    "Ogni capo ha bisogno di brand e nome": "Every item needs a brand and a name",
    "La stessa foto compare due volte": "The same photo appears twice",
    "Non puoi pubblicare fino al {date}": "You can't post until {date}",
    "Idempotency-Key non valida": "Invalid Idempotency-Key",
    "Pubblicazione già in corso": "Already posting",
    "Una o più foto non sono pronte o non sono tue": (
        "One or more photos aren't ready or aren't yours"
    ),
    "Puoi modificare solo i tuoi post": "You can only edit your own posts",
    "Lo stile di un post si cambia una volta sola": "A post's style can only be changed once",
    "Post non trovato": "Post not found",
    "Il fit è ancora in elaborazione": "The fit is still processing",
    "I tuoi fit sono già nel tuo profilo": "Your fits are already on your profile",
    "Non puoi votare i tuoi fit": "You can't score your own fits",
    "Questo post non si può votare": "This post can't be scored",
    # Persone
    "Richiesta non trovata": "Request not found",
    "Questa persona non può seguirti": "This person can't follow you",
    "Non puoi bloccare te stesso": "You can't block yourself",
    "Non puoi seguire te stesso": "You can't follow yourself",
    "Token push non valido": "Invalid push token",
    # Stili e proposte
    "Stile non trovato": "Style not found",
    "Puoi seguire al massimo {max} stili": "You can follow at most {max} styles",
    "Resta almeno in uno stile: il tuo feed è fatto di questi": (
        "Stay in at least one style: your feed is made of them"
    ),
    "Scrivi un nome di almeno due lettere": "Write a name with at least two letters",
    "Questo stile c'è già": "This style already exists",
    "Hai già {max} proposte aperte: aspetta che arrivino alla soglia": (
        "You already have {max} open proposals: wait for them to reach the threshold"
    ),
    "Proposta non trovata": "Proposal not found",
    "Nessuna proposta aperta con questo id": "No open proposal with this id",
    # Negozi e link
    "Link al negozio non valido": "Invalid shop link",
    "indirizzo vuoto, troppo lungo o con spazi": "address empty, too long or with spaces",
    "indirizzo non leggibile": "address can't be read",
    "serve un indirizzo https://": "an https:// address is needed",
    "credenziali nell'indirizzo": "credentials in the address",
    "porta non ammessa": "port not allowed",
    "manca il sito": "the site is missing",
    "indirizzo IP al posto del sito": "IP address instead of a site",
    "nome del sito non valido": "invalid site name",
    "sito non pubblico": "site isn't public",
    "indirizzo troppo lungo": "address too long",
    "Questo sito è già verificato da un altro account": (
        "This site is already verified by another account"
    ),
    "Puoi aggiungere al massimo 5 siti": "You can add at most 5 sites",
    "Sito non trovato": "Site not found",
    "Il file non c'è o non contiene il codice.": (
        "The file isn't there or doesn't contain the code."
    ),
    "Non riusciamo a raggiungere il sito in https.": "We can't reach the site over https.",
    "Verifica non riuscita": "Verification failed",
    "Serve un account Business": "You need a Business account",
    "LINK BLOCCATO": "LINK BLOCKED",
    "Abbiamo fermato questo link": "We've stopped this link",
    "Il sito {site} è stato segnalato come pericoloso (truffe, phishing o malware). "
    "Per sicurezza non ti ci portiamo.": (
        "The site {site} has been reported as dangerous (scams, phishing or malware). "
        "To keep you safe, we won't take you there."
    ),
    "Link non valido": "Invalid link",
    "Questo indirizzo non porta a nessun negozio.": "This address doesn't lead to any shop.",
    "Link non più disponibile": "Link no longer available",
    "Il capo è stato modificato o il fit non c'è più.": (
        "The item has been changed or the fit no longer exists."
    ),
    # Insight
    "Insight non disponibili": "Insights not available",
    "Periodo non valido: 7, 28 o 90 giorni": "Invalid period: 7, 28 or 90 days",
    # Privacy, dispositivi, cancellazione
    "Per questo dispositivo usa Esci": "For this device, use Sign out",
    "Dispositivo non trovato": "Device not found",
    "Puoi chiedere un nuovo archivio domani": "You can ask for a new archive tomorrow",
    "Il nickname non corrisponde": "The nickname doesn't match",
    "Account sospeso: scrivi al supporto": "Account suspended: write to support",
    "Cancellazione già chiesta": "Deletion already requested",
    "Nessuna cancellazione in corso": "No deletion in progress",
    "Messaggio non trovato": "Message not found",
    # Segnalazioni e reclami
    "Non puoi segnalare te stesso": "You can't report yourself",
    "Contenuto non trovato": "Content not found",
    "Non puoi segnalare un tuo fit": "You can't report your own fit",
    "Spiega perché pensi che sia un errore": "Explain why you think it's a mistake",
    "Decisione non trovata": "Decision not found",
    "Il reclamo si fa sulla decisione sul fit": "Appeal the decision on the fit instead",
    "Il tempo per il reclamo è scaduto": "The time to appeal has run out",
    "Hai già fatto reclamo per questa decisione": "You've already appealed this decision",
    # Pannello dello staff (risponde in inglese solo se chiesto)
    "Questa persona non ha limitazioni": "This person has no restrictions",
    "Esiste già uno stile con questo slug": "A style with this slug already exists",
    "La fine viene prima dell'inizio": "The end comes before the start",
    "Serve almeno un amministratore": "At least one administrator is needed",
    "Segnalazione non trovata o già annullata": "Report not found or already withdrawn",
    "Decisione non valida per questo contenuto": "Decision not valid for this content",
    "Motivo non valido": "Invalid reason",
    "Reclamo non trovato": "Appeal not found",
    "Reclamo già deciso": "Appeal already decided",
    "Serve un altro moderatore": "A different moderator is needed",
    # Motivazioni di moderazione (moderation/actions.py)
    "nudità o contenuti sessuali": "nudity or sexual content",
    "sicurezza dei minori": "child safety",
    "molestie, minacce o dati personali di altre persone": (
        "harassment, threats or other people's personal data"
    ),
    "spam": "spam",
    "stile sbagliato": "wrong style",
    "link pericoloso": "dangerous link",
    "foto di qualcun altro": "someone else's photo",
    "violazione delle regole della community": "breach of the community guidelines",
    "più segnalazioni di persone diverse": "several reports from different people",
    "una foto corrisponde a materiale illegale già noto": (
        "a photo matches known illegal material"
    ),
    "il controllo automatico delle foto": "the automatic photo check",
    "il tuo reclamo è stato accolto": "your appeal was upheld",
    "un moderatore ha verificato che rispetta le regole": (
        "a moderator checked that it follows the rules"
    ),
    "una revisione dello staff": "a staff review",
    "Se pensi che sia un errore puoi fare reclamo da questo avviso entro 6 mesi.": (
        "If you think it's a mistake you can appeal from this notice within 6 months."
    ),
    "Il reclamo si fa sull'avviso del fit e, se accolto, annulla anche questa decisione.": (
        "Appeal from the notice about the fit: if upheld, it also reverses this decision."
    ),
    "Un tuo fit": "One of your fits",
    "Decisione automatica": "Automated decision",
    "Decisione di un moderatore": "Decision by a moderator",
    "{fit} è stato nascosto: non compare più nel feed né nel tuo profilo per gli altri": (
        "{fit} has been hidden: others no longer see it in the feed or on your profile"
    ),
    "{what}. Motivo: {why}. {who}: un moderatore lo rivede presto e, se non viola le regole, "
    "torna visibile. {appeal}": (
        "{what}. Reason: {why}. {who}: a moderator will review it soon and, if it doesn't break "
        "the rules, it will be visible again. {appeal}"
    ),
    "{what}. Motivo: {why}. {who}. {appeal}": "{what}. Reason: {why}. {who}. {appeal}",
    "La bio e la foto del tuo profilo sono state tolte; quella foto non si può ricaricare. "
    "Puoi scriverne di nuove. Motivo: {why}. {who}. {appeal}": (
        "Your profile's bio and photo have been removed; that photo can't be uploaded again. "
        "You can add new ones. Reason: {why}. {who}. {appeal}"
    ),
    "{fit} è stato rimosso e le sue foto non si possono ripubblicare. Motivo: {why}. "
    "{who}. {appeal}": (
        "{fit} has been removed and its photos can't be posted again. Reason: {why}. "
        "{who}. {appeal}"
    ),
    "Avviso: un tuo contenuto ha violato le regole della community ({why}). Al prossimo "
    "problema la pubblicazione viene sospesa per {days} giorni. {appeal}": (
        "Warning: some of your content broke the community guidelines ({why}). If it happens "
        "again, posting will be suspended for {days} days. {appeal}"
    ),
    "Non puoi pubblicare nuovi fit fino al {day}. Motivo: {why}. Puoi ancora vedere "
    "e votare. {who}. {appeal}": (
        "You can't post new fits until {day}. Reason: {why}. You can still browse and score. "
        "{who}. {appeal}"
    ),
    "Il tuo account è sospeso in attesa di verifica. Motivo: {why}. {who}. "
    "Un moderatore controlla il caso il prima possibile. {appeal}": (
        "Your account is suspended pending review. Reason: {why}. {who}. "
        "A moderator will check the case as soon as possible. {appeal}"
    ),
    "Il tuo account è stato chiuso. Motivo: {why}. {who}. {appeal}": (
        "Your account has been closed. Reason: {why}. {who}. {appeal}"
    ),
    "Annullata anche la sanzione decisa insieme al fit: non conta più per le "
    "sanzioni successive.": (
        "The penalty decided together with the fit has been reversed too: it no longer counts "
        "towards future penalties."
    ),
    "Abbiamo annullato una decisione precedente: {why}. Ci scusiamo per il disagio.": (
        "We've reversed an earlier decision: {why}. We're sorry for the inconvenience."
    ),
    "Decisione di moderazione. Motivo: {why}. {who}. {appeal}": (
        "Moderation decision. Reason: {why}. {who}. {appeal}"
    ),
    # Notifiche e push (notifications.py, push.py)
    "Un tuo fit è stato nascosto": "One of your fits has been hidden",
    "Un tuo fit è stato rimosso": "One of your fits has been removed",
    "Abbiamo spostato un tuo fit in un altro stile": (
        "We've moved one of your fits to another style"
    ),
    "Il tuo account è sospeso": "Your account is suspended",
    "Il tuo account è stato chiuso": "Your account has been closed",
    "Hai ricevuto un avviso": "You've received a warning",
    "Pubblicazione sospesa per 7 giorni": "Posting suspended for 7 days",
    "Abbiamo annullato una decisione": "We've reversed a decision",
    "Il tuo fit": "Your fit",
    "Il tuo fit «{caption}»": "Your fit “{caption}”",
    "Qualcuno": "Someone",
    "{who} vuole seguirti": "{who} wants to follow you",
    "Accetta per fargli vedere il tuo portfolio.": "Accept to let them see your portfolio.",
    "Nuova richiesta": "New request",
    "{who} ha iniziato a seguirti": "{who} started following you",
    "Nuovo follower": "New follower",
    "{who} ha accettato la tua richiesta": "{who} accepted your request",
    "Ora vedi il suo portfolio.": "You can now see their portfolio.",
    "Richiesta accettata": "Request accepted",
    "{fit} ha raggiunto {count} voti": "{fit} has reached {count} scores",
    "Apri il fit per vedere la media.": "Open the fit to see the average.",
    "Nuovo traguardo": "New milestone",
    "Novità dalla moderazione": "News from moderation",
    "Tocca per leggere il motivo e, se vuoi, fare reclamo.": (
        "Tap to read the reason and, if you want, appeal."
    ),
    "Tocca per i dettagli.": "Tap for details.",
    "Hai un nuovo avviso della moderazione": "You have a new moderation notice",
    "Reclamo accolto": "Appeal upheld",
    "Reclamo respinto": "Appeal rejected",
    "Abbiamo annullato la decisione.": "We've reversed the decision.",
    "La decisione resta. Tocca per leggere la risposta.": (
        "The decision stands. Tap to read the reply."
    ),
    "Il tuo reclamo è stato deciso": "Your appeal has been decided",
    "Il tuo archivio dei dati è pronto": "Your data archive is ready",
    "Scaricalo entro 7 giorni da Impostazioni > I tuoi dati.": (
        "Download it within 7 days from Privacy and security > Download your data."
    ),
    "Archivio pronto": "Archive ready",
    "Novità su WearX": "News on WearX",
    "Hai {count} nuove notifiche": "You have {count} new notifications",
    # Pagine legali (routers/legal.py)
    "Bozza.": "Draft.",
    "Testo da far rivedere a un legale prima del lancio: le parti tra parentesi quadre vanno "
    "completate.": (
        "Text to be reviewed by a lawyer before launch: the parts in square brackets still "
        "need completing."
    ),
    "Altri documenti": "Other documents",
    "Pagina non trovata": "Page not found",
    "Termini di servizio": "Terms of Service",
    "Informativa privacy": "Privacy Policy",
    "Regole della community": "Community Guidelines",
    "Come funziona il feed": "How the feed works",
    "Cancellare l'account": "Deleting your account",
}
