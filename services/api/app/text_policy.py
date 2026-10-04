"""Regole sui testi scritti dagli utenti (nickname, bio).

Nickname e bio sono, insieme a didascalie e nomi dei capi, gli unici canali di testo
dell'app (non ci sono commenti): sono anche l'unico veicolo possibile per insulti e
impersonificazioni. Qui ci sono i controlli deterministici; il classificatore di testo
per gli insulti arriva con la moderazione (seduta 16).
"""

from __future__ import annotations

import re
import unicodedata

from app.errors import ApiError

NICKNAME_RE = re.compile(r"^[a-z0-9._]{3,20}$")

# Nomi esatti riservati.
RESERVED_NICKNAMES = frozenset(
    {
        "abuse",
        "account",
        "api",
        "app",
        "help",
        "info",
        "legal",
        "me",
        "news",
        "null",
        "privacy",
        "root",
        "security",
        "settings",
        "system",
        "team",
        "terms",
        "undefined",
        "www",
        "aiuto",
        "assistenza",
        "termini",
        "regole",
    }
)
# Parti che non possono comparire in nessun nickname: impedirebbero di distinguere
# un account ufficiale da uno che lo imita.
RESERVED_FRAGMENTS = ("wearx", "admin", "moderat", "support", "staff", "official", "ufficial")

# Caratteri invisibili o che invertono la direzione del testo: usati per spoofing.
_INVISIBLE_RANGES = (
    (0x200B, 0x200F),  # spazi a larghezza zero, marcatori di direzione
    (0x202A, 0x202E),  # override di direzione (es. testo che si legge al contrario)
    (0x2060, 0x2064),  # word joiner e operatori invisibili
    (0x2066, 0x2069),  # isolatori di direzione
    (0xFEFF, 0xFEFF),  # BOM / spazio a larghezza zero
    (0x00AD, 0x00AD),  # trattino morbido
)
_FORBIDDEN_CHARS = re.compile(
    "[" + "".join(f"{chr(a)}-{chr(b)}" for a, b in _INVISIBLE_RANGES) + "]"
)

BIO_MAX_CHARS = 150
BIO_MAX_LINES = 4


def nickname_problem(nickname: str) -> str | None:
    """None se il nickname è utilizzabile, altrimenti il motivo: 'invalid' o 'reserved'."""
    if not NICKNAME_RE.fullmatch(nickname):
        return "invalid"
    # Punti e underscore non devono servire a mascherare una parola riservata (w.e.a.r.x).
    compact = nickname.replace(".", "").replace("_", "")
    if nickname in RESERVED_NICKNAMES or compact in RESERVED_NICKNAMES:
        return "reserved"
    if any(fragment in compact for fragment in RESERVED_FRAGMENTS):
        return "reserved"
    if nickname[0] in "._" or nickname[-1] in "._" or ".." in nickname:
        return "invalid"
    return None


def clean_bio(raw: str | None) -> str | None:
    """Normalizza la bio; solleva 422 se contiene caratteri non ammessi o è troppo lunga."""
    if raw is None:
        return None
    text = unicodedata.normalize("NFC", raw).strip()
    if not text:
        return None
    if _FORBIDDEN_CHARS.search(text):
        raise ApiError(422, "text.invalid_characters", "La bio contiene caratteri non ammessi")
    for ch in text:
        if ch != "\n" and unicodedata.category(ch) in ("Cc", "Cf", "Co", "Cs"):
            raise ApiError(422, "text.invalid_characters", "La bio contiene caratteri non ammessi")
    if len(text) > BIO_MAX_CHARS:
        raise ApiError(
            422, "text.too_long", f"La bio può avere al massimo {BIO_MAX_CHARS} caratteri"
        )
    if text.count("\n") >= BIO_MAX_LINES:
        raise ApiError(
            422, "text.too_many_lines", f"La bio può avere al massimo {BIO_MAX_LINES} righe"
        )
    return text
