"""Testi: insulti e parole d'odio (sez. 14.2). Nickname, bio, didascalie, brand e nomi dei capi
sono l'unico canale di testo di WearX, quindi l'unico veicolo di insulti.

Lista minima IT/EN di parole che non hanno usi legittimi su WearX. Si confrontano parole
intere dopo aver tolto accenti, maiuscole, sostituzioni tipo "pu77ana" e lettere ripetute;
anche le parole scritte a lettere separate ("p u t t a n a", "p.u.t.t.a.n.a").
Non è un classificatore: il classificatore di testo del fornitore si aggiunge dietro
`TextClassifier` quando sarà scelto. Finché non c'è, i casi dubbi passano dalle segnalazioni.
"""

from __future__ import annotations

import re
import unicodedata
from functools import cache
from itertools import pairwise
from pathlib import Path

LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)
_WORDS_FILE = Path(__file__).with_name("blocked_words.txt")


def _collapse(word: str) -> str:
    """'puttanaaa' -> 'putana': lettere ripetute contano una volta."""
    return re.sub(r"(.)\1+", r"\1", word)


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return plain.translate(LEET)


@cache
def blocked_words() -> frozenset[str]:
    words = set()
    for line in _WORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            words.add(_collapse(normalize(line)))
    return frozenset(words)


def _tokens(text: str) -> list[str]:
    raw = re.split(r"[^a-z]+", normalize(text))
    tokens = [t for t in raw if t]
    # Lettere separate da spazi o punti: si ricompongono le sequenze di lettere singole.
    joined, run = [], ""
    for token in tokens:
        if len(token) == 1:
            run += token
            continue
        if len(run) > 1:
            joined.append(run)
        run = ""
    if len(run) > 1:
        joined.append(run)
    # Espressioni di più parole nella lista ("kill yourself" -> "killyourself").
    pairs = [a + b for a, b in pairwise(tokens)]
    return tokens + joined + pairs


def offensive_word(text: str) -> str | None:
    """La prima parola vietata trovata (normalizzata), oppure None."""
    banned = blocked_words()
    for token in _tokens(text):
        collapsed = _collapse(token)
        if collapsed in banned:
            return collapsed
    return None


def offensive_compact(compact: str) -> bool:
    """Per i nickname (senza spazi): la parola vietata può essere una parte del nickname."""
    value = _collapse(normalize(compact))
    return any(len(word) >= 6 and word in value for word in blocked_words()) or (
        value in blocked_words()
    )
