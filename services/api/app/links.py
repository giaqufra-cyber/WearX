"""Link ai negozi: solo https verso siti veri (sez. 6.4 e 12).

Si rifiutano: http, credenziali nell'indirizzo (https://utente:pw@…), indirizzi IP,
localhost e domini interni, porte diverse da 443, indirizzi troppo lunghi.
Il controllo del sito (liste di phishing/malware, pagina esistente) è in `app.link_check`.

Nell'app i link non si aprono direttamente: passano da `/r/<codice>` (redirect firmato), che
controlla lo stato del link AL MOMENTO DEL CLIC (un sito diventato pericoloso dopo la
pubblicazione si ferma lì) e conta il clic.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import ipaddress
import uuid
from urllib.parse import urlsplit, urlunsplit

from app.config import get_settings
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


# ---------- Redirect firmato ----------

_SIG = 10  # byte di firma: abbastanza per non essere indovinata, link corti


def _sign(payload: bytes) -> bytes:
    pepper = get_settings().vote_pepper.get_secret_value().encode()
    return hmac.new(pepper, b"go:" + payload, hashlib.sha256).digest()[:_SIG]


def go_token(link_id: uuid.UUID, post_id: uuid.UUID, item: int) -> str:
    payload = link_id.bytes + post_id.bytes + bytes([item])
    return base64.urlsafe_b64encode(payload + _sign(payload)).decode().rstrip("=")


def parse_go_token(token: str) -> tuple[uuid.UUID, uuid.UUID, int] | None:
    """(link, post, posizione del capo) se il codice è integro, altrimenti None."""
    if len(token) > 64:
        return None
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except (binascii.Error, ValueError):
        return None
    if len(raw) != 33 + _SIG:
        return None
    payload, signature = raw[:33], raw[33:]
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    return uuid.UUID(bytes=payload[:16]), uuid.UUID(bytes=payload[16:32]), payload[32]


def go_url(link_id: uuid.UUID, post_id: uuid.UUID, item: int) -> str:
    base = get_settings().public_api_url.rstrip("/")
    return f"{base}/r/{go_token(link_id, post_id, item)}"
