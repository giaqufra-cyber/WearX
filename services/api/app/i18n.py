"""Lingua delle risposte (seduta 34): italiano o inglese.

Come nell'app, il testo italiano è la chiave: `tr("Post non trovato", lang)` restituisce
"Post not found" in inglese e il testo com'è in italiano. Le traduzioni stanno in
`app/i18n_en.py`; un test controlla che ogni testo passato a `tr()`, `N_()` o come titolo di un
errore abbia la sua traduzione, con gli stessi segnaposto `{nome}`.

La lingua arriva dall'app con `Accept-Language` ("it" o "en"), oppure con `?lang=` dove l'app non
può mandare header (pagine aperte nel browser, risposta in cache). Senza indicazioni: italiano.
Qualsiasi altra lingua diventa inglese, come nell'app.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Annotated, Any, Literal

from fastapi import Depends, Request

from app.i18n_en import EN

Lang = Literal["it", "en"]
LANGS: tuple[Lang, ...] = ("it", "en")


def parse_lang(value: str | None) -> Lang:
    """`Accept-Language` -> "it" o "en" (conta la prima lingua dell'elenco)."""
    if not value:
        return "it"
    first = value.split(",")[0].split(";")[0].strip().lower()
    if not first or first == "*" or first.startswith("it"):
        return "it"
    return "en"


def request_lang(request: Request) -> Lang:
    query = request.query_params.get("lang")
    if query in LANGS:
        return query
    return parse_lang(request.headers.get("accept-language"))


RequestLang = Annotated[Lang, Depends(request_lang)]

# La lingua della richiesta in corso (la imposta il middleware), per le query che non ricevono
# la richiesta: es. le schede dei post, usate da feed, profilo, salvati...
lang_var: ContextVar[Lang] = ContextVar("lang", default="it")


def current_lang() -> Lang:
    return lang_var.get()


def N_(text: str) -> str:
    """Segna un testo da tradurre più avanti (costanti di modulo, etichette passate ad altri)."""
    return text


def tr(text: str, lang: Lang, **params: Any) -> str:
    """Il testo nella lingua chiesta, con i segnaposto riempiti.

    I parametri di tipo stringa che sono a loro volta testi del dizionario (es. il nome di un
    campo, "La bio") si traducono anche loro.
    """
    template = EN.get(text, text) if lang == "en" else text
    if not params:
        return template
    values = {
        key: (EN.get(value, value) if lang == "en" and isinstance(value, str) else value)
        for key, value in params.items()
    }
    return template.format(**values)


# Nome e descrizione di uno stile (tabella con alias `s`) nella lingua `:lang` della query.
STYLE_NAME_SQL = "(case when :lang = 'en' then coalesce(s.name_en, s.name) else s.name end)"
STYLE_TAGLINE_SQL = (
    "(case when :lang = 'en' then coalesce(s.tagline_en, s.tagline) else s.tagline end)"
)
