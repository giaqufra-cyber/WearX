"""Chiavi d'ordine del portfolio (indice frazionario, sez. 6.5).

L'ordine è per chiave DECRESCENTE (prima la più "grande"):
- un post nuovo prende `key_now()`: "b" + istante in millisecondi in base 62 a larghezza fissa
  + "V",
  quindi è sempre sopra a quelli già pubblicati;
- spostare un post tra due vicini (seduta 14) usa `key_between`, che produce una chiave
  strettamente in mezzo senza toccare gli altri post.
Le chiavi usano solo [0-9A-Za-z] e si confrontano byte per byte (collation "C").
"""

from __future__ import annotations

import time

DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_INDEX = {c: i for i, c in enumerate(DIGITS)}
_TIME_WIDTH = 8  # 62^8 ms ≈ 6.9 milioni di anni


def _base62(value: int, width: int) -> str:
    out = ""
    for _ in range(width):
        value, rem = divmod(value, 62)
        out = DIGITS[rem] + out
    return out


def key_now(now_ms: int | None = None) -> str:
    ms = int(time.time() * 1000) if now_ms is None else now_ms
    # "V" finale: una chiave non deve mai finire con "0" (non ci sarebbe spazio sotto).
    return "b" + _base62(ms, _TIME_WIDTH) + "V"


def _midpoint(a: str, b: str | None) -> str:
    """Stringa strettamente tra a e b (b=None: nessun limite sopra). Né a né b finiscono con "0"."""
    if b is not None:
        n = 0
        while n < len(b) and (a[n] if n < len(a) else "0") == b[n]:
            n += 1
        if n > 0:
            return b[:n] + _midpoint(a[n:], b[n:])
    digit_a = _INDEX[a[0]] if a else 0
    digit_b = _INDEX[b[0]] if b else len(DIGITS)
    if digit_b - digit_a > 1:
        return DIGITS[(digit_a + digit_b + 1) // 2]
    if b is not None and len(b) > 1:
        return b[0]
    return DIGITS[digit_a] + _midpoint(a[1:], None)


def key_between(low: str | None, high: str | None) -> str:
    """Chiave con low < chiave < high. low=None: sotto tutto; high=None: sopra tutto."""
    for key in (low, high):
        if key is not None and (not key or key[-1] == "0" or any(c not in _INDEX for c in key)):
            raise ValueError(f"chiave non valida: {key!r}")
    if low is not None and high is not None and low >= high:
        raise ValueError("low deve essere minore di high")
    return _midpoint(low or "", high)


# Spostando sempre nello stesso punto le chiavi si allungano di circa un carattere ogni 5
# spostamenti. Oltre questa lunghezza si riscrivono tutte le chiavi della persona.
MAX_KEY_LEN = 40


def spread_keys(count: int) -> list[str]:
    """`count` chiavi corte e ben distanziate, dalla più alta alla più bassa (ordine del
    portfolio). Iniziano con "a": restano sotto le chiavi dei post nuovi ("b" + istante)."""
    if count <= 0:
        return []
    width = 1
    while 62**width < (count + 1) * 62:  # almeno 62 "posti liberi" tra due chiavi vicine
        width += 1
    step = 62**width // (count + 1)
    return ["a" + _base62((count - i) * step, width) + "V" for i in range(count)]
