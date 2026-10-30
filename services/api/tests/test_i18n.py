"""Testi del server in inglese (seduta 34).

Come per l'app: ogni testo che può arrivare a una persona (titoli e dettagli degli errori,
notifiche, push, motivazioni di moderazione, pagine) ha la traduzione inglese con gli stessi
segnaposto, e il dizionario non tiene testi che il codice non usa più.
"""

from __future__ import annotations

import ast
import re
import string
from pathlib import Path

import pytest

from app.i18n import parse_lang, tr
from app.i18n_en import EN

APP = Path(__file__).resolve().parent.parent / "app"

# Funzione -> posizioni degli argomenti che sono testi (più i keyword title/detail).
TEXT_ARGS = {
    "ApiError": (2, 3),
    "problem": (3, 4),
    "_unauthorized": (1,),
    "_invalid": (0,),
    "tr": (0,),
    "t": (0,),
    "N_": (0,),
}


def _literals(node: ast.AST | None) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, ast.IfExp):
        return _literals(node.body) + _literals(node.orelse)
    if isinstance(node, ast.BoolOp):
        return _literals(node.values[-1])
    return []


def used_keys() -> dict[str, str]:
    keys: dict[str, str] = {}
    for file in sorted(APP.rglob("*.py")):
        if file.name == "i18n_en.py":
            continue
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in TEXT_ARGS:
                continue
            args = [node.args[i] for i in TEXT_ARGS[name] if i < len(node.args)]
            args += [k.value for k in node.keywords if k.arg in ("title", "detail")]
            for arg in args:
                for key in _literals(arg):
                    keys[key] = f"{file.relative_to(APP.parent)}:{node.lineno}"
    return keys


def _placeholders(text: str) -> list[str]:
    return sorted(name for _, name, _, _ in string.Formatter().parse(text) if name)


def test_ogni_testo_e_tradotto():
    missing = [f"{where}: {key}" for key, where in used_keys().items() if key not in EN]
    assert missing == []


def test_stessi_segnaposto():
    wrong = [it for it, en in EN.items() if _placeholders(it) != _placeholders(en)]
    assert wrong == []


def test_nessuna_traduzione_inutilizzata():
    assert sorted(set(EN) - set(used_keys())) == []


def test_nessun_titolo_di_errore_composto_a_mano():
    """I valori variabili vanno in `params`, non dentro il testo (altrimenti non si traduce)."""
    bad = []
    for file in sorted(APP.rglob("*.py")):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "ApiError":
                texts = node.args[2:4] + [k.value for k in node.keywords if k.arg == "title"]
                bad += [f"{file.name}:{node.lineno}" for a in texts if isinstance(a, ast.JoinedStr)]
    assert bad == []


@pytest.mark.parametrize(
    ("header", "lang"),
    [
        (None, "it"),
        ("it", "it"),
        ("it-IT,it;q=0.9", "it"),
        ("en", "en"),
        ("en-GB", "en"),
        ("de-DE,de;q=0.9,it;q=0.8", "en"),
        ("*", "it"),
    ],
)
def test_lingua_dalla_richiesta(header, lang):
    assert parse_lang(header) == lang


def test_tr():
    assert tr("Post non trovato", "it") == "Post non trovato"
    assert tr("Post non trovato", "en") == "Post not found"
    assert tr("Testo che non c'è", "en") == "Testo che non c'è"
    # I parametri che sono testi del dizionario (il nome del campo) si traducono anche loro.
    text = "{field} può avere al massimo {max_chars} caratteri"
    assert tr(text, "it", field="La bio", max_chars=150) == (
        "La bio può avere al massimo 150 caratteri"
    )
    assert tr(text, "en", field="La bio", max_chars=150) == "The bio can be at most 150 characters"


async def test_errori_nella_lingua_della_richiesta(client):
    r = await client.get("/v1/me", headers={"Accept-Language": "en"})
    assert r.status_code == 401
    assert (r.json()["code"], r.json()["title"]) == ("auth.required", "Sign-in required")
    r = await client.get("/v1/me")
    assert r.json()["title"] == "Accesso richiesto"
    r = await client.get("/v1/me", params={"lang": "en"})
    assert r.json()["title"] == "Sign-in required"


async def test_pagine_legali_in_inglese(client):
    r = await client.get("/legal/en/privacy")
    assert r.status_code == 200
    assert '<html lang="en">' in r.text
    assert "<title>Privacy Policy · WearX</title>" in r.text
    assert "<strong>Draft.</strong>" in r.text
    assert '<p class="version">Version 2026-10' in r.text
    assert (await client.get("/legal/en/segreti")).status_code == 404
    legal = (await client.get("/v1/config", headers={"Accept-Language": "en"})).json()["legal"]
    assert legal["terms"].endswith("/legal/en/termini")


def test_le_pagine_inglesi_hanno_le_stesse_sezioni():
    """Stessa struttura (titoli di sezione e tabelle) nelle due lingue."""
    for page in (APP / "legal").glob("*.md"):
        it = page.read_text(encoding="utf-8")
        en = (APP / "legal" / "en" / page.name).read_text(encoding="utf-8")
        assert len(re.findall(r"^## ", it, re.M)) == len(re.findall(r"^## ", en, re.M)), page
        assert it.count("|---|") == en.count("|---|"), page
