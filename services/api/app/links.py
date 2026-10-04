"""Link ai negozi: solo https verso siti veri (sez. 6.4 e 12).

Si rifiutano: http, credenziali nell'indirizzo (https://utente:pw@…), indirizzi IP,
localhost e domini interni, porte diverse da 443, indirizzi troppo lunghi.
Il controllo di sicurezza del sito (liste di phishing/malware) arriva con la seduta 21:
fino ad allora il link resta "pending".
"""

from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit, urlunsplit

from app.errors import ApiError

MAX_URL_LENGTH = 2048
_BLOCKED_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home", ".corp", ".test")


def _invalid(reason: str) -> ApiError:
    return ApiError(422, "link.invalid", "Link al negozio non valido", detail=reason)


def normalize_shop_url(raw: str) -> tuple[str, str]:
    """Restituisce (url normalizzato, dominio senza www.) oppure solleva 422 link.invalid."""
    text = raw.strip()
    if not text or len(text) > MAX_URL_LENGTH or any(c.isspace() for c in text):
        raise _invalid("indirizzo vuoto, troppo lungo o con spazi")
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise _invalid("indirizzo non leggibile") from None
    if parts.scheme.lower() != "https":
        raise _invalid("serve un indirizzo https://")
    if parts.username or parts.password or "@" in parts.netloc:
        raise _invalid("credenziali nell'indirizzo")
    if port not in (None, 443):
        raise _invalid("porta non ammessa")
    host = (parts.hostname or "").rstrip(".")
    if not host:
        raise _invalid("manca il sito")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise _invalid("indirizzo IP al posto del sito")
    try:
        ascii_host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        raise _invalid("nome del sito non valido") from None
    if "." not in ascii_host or ascii_host == "localhost" or ascii_host.endswith(_BLOCKED_SUFFIXES):
        raise _invalid("sito non pubblico")
    url = urlunsplit(("https", ascii_host, parts.path or "/", parts.query, ""))
    if len(url) > MAX_URL_LENGTH:
        raise _invalid("indirizzo troppo lungo")
    domain = ascii_host.removeprefix("www.")
    return url, domain
