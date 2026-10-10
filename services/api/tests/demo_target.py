"""Demo di WearX da aprire sul telefono (iPhone in Safari, app per Sideloadly, Android).

Tutto gira su questo computer, come l'ambiente dei test end-to-end (tests/e2e_target.py), ma:
- dietro UN SOLO indirizzo (porta 8090), che `scripts/demo.sh` pubblica con un tunnel https
  (Cloudflare): API, accesso finto, foto e app web stanno sullo stesso link;
- con dati di prova "da vetrina": persone, fit disegnati per stile, capi, voti, follow;
- con i lavori periodici del worker accelerati (medie dei voti pubblicate ogni minuto).

Solo per provare l'app: accesso finto (il codice di conferma è sempre 123456), database nuovo
a ogni avvio, nessun dato vero. Avvio: `scripts/demo.sh` dalla cartella del progetto.

    DEMO_PUBLIC_URL=https://….trycloudflare.com uv run python -m tests.demo_target
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import random
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PUBLIC_URL = os.environ.get("DEMO_PUBLIC_URL", "http://localhost:8090").rstrip("/")
DEMO_PORT = int(os.environ.get("DEMO_PORT", "8090"))
# Prima di importare l'ambiente E2E: indirizzo pubblico dell'API (pagina di verifica dell'età
# di prova) e ritorno ammesso per l'app web della demo.
os.environ.setdefault("WEARX_PUBLIC_API_URL", PUBLIC_URL)
os.environ.setdefault("WEARX_DEMO_WEB_ORIGIN", PUBLIC_URL)

import tests.e2e_target as e2e  # noqa: E402 - dopo le variabili d'ambiente qui sopra
from tests import conftest as cf  # noqa: E402

DEMO_DIST = Path(__file__).resolve().parents[3] / "apps" / "mobile" / "dist-demo"
# Prima parte dell'indirizzo che va all'API (il resto è l'app web o l'archivio delle foto).
API_ROOTS = frozenset({"v1", "legal", "r", "healthz", "readyz"})
GUEST = {"nickname": "ospite.demo", "email": "ospite@demo.test", "password": "Demo-WearX-2026!"}


# ---------- Foto disegnate: una figura stilizzata per stile, come nelle schermate ----------


@dataclass(frozen=True)
class Look:
    top: str
    inner: str | None
    bottom: str
    shoes: str
    accent: str | None = None  # papillon (o cravatta con tie=True)
    tie: bool = False
    oversize: bool = False
    long_coat: bool = False
    wide: bool = False


TONES = {
    "gala": "#3D1018",
    "old-money": "#2F3A2B",
    "streetwear": "#33302B",
    "jappo": "#1F2946",
    "minimal": "#4E4A45",
    "elegant": "#2A2A2F",
}
LOOKS: dict[str, list[Look]] = {
    "gala": [
        Look("#121216", "#EDE6D6", "#121216", "#0A0A0A", accent="#0A0A0A"),
        Look("#9B1B2E", "#F1E9DA", "#141418", "#0A0A0A", accent="#141418"),
        Look("#1D2B4A", "#EFE8DA", "#1D2B4A", "#0B0B0B", accent="#0B0B0B"),
    ],
    "old-money": [
        Look("#D8C7A8", "#F3EEE4", "#26324A", "#5A3A21"),
        Look("#2F4A3A", "#EFE7D8", "#CDBB98", "#4A2F1C"),
        Look("#F0E9DC", None, "#7B6A55", "#3B2A1C"),
    ],
    "streetwear": [
        Look("#8A8F98", None, "#4B4F3A", "#F2F2F2", oversize=True),
        Look("#C2462E", None, "#22252B", "#EDEDED", oversize=True),
        Look("#1C1C1E", "#E8E8E8", "#5B6B7C", "#F4F4F4", oversize=True),
    ],
    "jappo": [
        Look("#1E1E22", "#F2F2F2", "#3A3A44", "#121214", long_coat=True, wide=True),
        Look("#4C5B48", "#E6E1D6", "#1E1E22", "#111111", long_coat=True, wide=True),
    ],
    "minimal": [
        Look("#E9E6E1", None, "#9A948C", "#F5F5F5"),
        Look("#2B2B2B", None, "#D9D4CC", "#1A1A1A"),
    ],
    "elegant": [
        Look("#2B3A55", "#F0F0F0", "#2B3A55", "#1A1A1A", accent="#7A1F2B", tie=True),
        Look("#5B5E63", "#F4F1EA", "#5B5E63", "#2A1B12", accent="#1F2A44", tie=True),
    ],
}
SKIN = ["#E3B999", "#C99A73", "#8D5E3C", "#F0CDB0", "#B07A52"]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return (
        round(a[0] + (b[0] - a[0]) * t),
        round(a[1] + (b[1] - a[1]) * t),
        round(a[2] + (b[2] - a[2]) * t),
    )


def draw_look(style: str, look: Look, skin: str, *, shade: float = 0.0, shift: int = 0) -> Any:
    """Figura stilizzata 1080x1350 (4:5) su fondo sfumato nel colore dello stile."""
    from PIL import Image, ImageDraw

    w, h = 1080, 1350
    tone = _rgb(TONES[style])
    top_color = _mix(tone, (0, 0, 0), 0.55 - shade)
    bottom_color = _mix(tone, (255, 255, 255), 0.08 + shade)
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_mix(top_color, bottom_color, y / h))
    # Righe orizzontali leggere (come le schermate del prototipo).
    for y in range(0, h, 9):
        d.line([(0, y), (w, y)], fill=_mix(_mix(top_color, bottom_color, y / h), (0, 0, 0), 0.08))

    cx = 540 + shift
    # Ombra a terra.
    d.ellipse([cx - 230, 1195, cx + 230, 1245], fill=_mix(bottom_color, (0, 0, 0), 0.35))

    torso_w = 210 if look.oversize else 180
    waist_w = 170 if look.oversize else 150
    torso_end = 1010 if look.long_coat else (820 if look.oversize else 780)
    arm_x = torso_w + 6

    # Pantaloni e scarpe.
    leg_out = 160 if look.wide else 130
    d.rectangle([cx - leg_out, 760, cx - 6, 1170], fill=look.bottom)
    d.rectangle([cx + 6, 760, cx + leg_out, 1170], fill=look.bottom)
    d.rectangle([cx - leg_out - 12, 1165, cx - 2, 1212], fill=look.shoes)
    d.rectangle([cx + 2, 1165, cx + leg_out + 12, 1212], fill=look.shoes)

    # Braccia e mani.
    d.rectangle([cx - arm_x - 62, 440, cx - arm_x, 810], fill=look.top)
    d.rectangle([cx + arm_x, 440, cx + arm_x + 62, 810], fill=look.top)
    d.ellipse([cx - arm_x - 60, 798, cx - arm_x - 2, 852], fill=skin)
    d.ellipse([cx + arm_x + 2, 798, cx + arm_x + 60, 852], fill=skin)

    # Busto (trapezio) e camicia interna.
    d.polygon(
        [
            (cx - torso_w, 430),
            (cx + torso_w, 430),
            (cx + waist_w, torso_end),
            (cx - waist_w, torso_end),
        ],
        fill=look.top,
    )
    if look.inner:
        d.polygon([(cx - 42, 430), (cx + 42, 430), (cx + 30, 760), (cx - 30, 760)], fill=look.inner)
    if look.accent and look.tie:
        d.polygon(
            [(cx - 14, 438), (cx + 14, 438), (cx + 20, 640), (cx, 668), (cx - 20, 640)],
            fill=look.accent,
        )
    elif look.accent:
        d.polygon([(cx - 34, 440), (cx, 462), (cx - 34, 484)], fill=look.accent)
        d.polygon([(cx + 34, 440), (cx, 462), (cx + 34, 484)], fill=look.accent)
    if look.oversize:
        # Cappuccio / girocollo morbido.
        d.ellipse([cx - 95, 400, cx + 95, 470], fill=_mix(_rgb(look.top), (0, 0, 0), 0.18))

    # Collo e testa.
    d.rectangle([cx - 26, 390, cx + 26, 438], fill=skin)
    d.ellipse([cx - 78, 250, cx + 78, 410], fill=skin)

    # Segni d'angolo.
    mark = _mix(bottom_color, (255, 255, 255), 0.5)
    d.line([(60, 60), (130, 60)], fill=mark, width=3)
    d.line([(60, 60), (60, 130)], fill=mark, width=3)
    d.line([(w - 60, h - 60), (w - 130, h - 60)], fill=mark, width=3)
    d.line([(w - 60, h - 60), (w - 60, h - 130)], fill=mark, width=3)
    return img


def detail_crop(img: Any) -> Any:
    """Seconda foto del carosello: dettaglio del busto."""
    return img.crop((270, 250, 810, 925)).resize((1080, 1350))


async def put_image(store: Any, upload_id: uuid.UUID, img: Any) -> None:
    from app.media.keys import variant_key

    for width in (320, 640, 1080):
        variant = img.resize((width, round(width * 1.25)))
        buf = io.BytesIO()
        variant.save(buf, "WEBP", quality=82)
        await store.put(variant_key(upload_id, width), buf.getvalue(), "image/webp")


# ---------- Dati di prova "da vetrina" ----------

PEOPLE = [
    GUEST,
    {"nickname": "giulia.rossi", "email": "giulia@demo.test"},
    {"nickname": "marco.bianchi", "email": "marco@demo.test"},
    {"nickname": "sofia.verdi", "email": "sofia@demo.test"},
    {"nickname": "luca.neri", "email": "luca@demo.test"},
    {"nickname": "chiara.ferri", "email": "chiara@demo.test"},
    {"nickname": "tommaso.galli", "email": "tommaso@demo.test"},
    {"nickname": "elena.conti", "email": "elena@demo.test"},
]
STYLES = ["old-money", "streetwear", "jappo", "gala", "minimal", "elegant"]
CAPSULE_NAMES = {
    "old-money": "Weekend al lago",
    "streetwear": "In città",
    "jappo": "Tokyo mood",
    "gala": "Serate",
    "minimal": "Ufficio",
    "elegant": "Cerimonie",
}
BIOS = [
    "Cachemire, mocassini e tanta pazienza.",
    "Sneaker prima di tutto. Milano.",
    "Linee pulite, tre colori al massimo.",
    "Vintage trovato nei mercatini.\nTrento → Monaco",
    "Sartoria su misura e serate lunghe.",
    "Tecnico in montagna, elegante in città.",
    "Se piove, layering.",
]

# autore, stile, didascalia, look, foto, voto medio, capi (marchio, capo, prezzo €)
POSTS: list[tuple[str, str, str, int, int, int, list[tuple[str, str, int]]]] = [
    (
        "giulia.rossi",
        "gala",
        "Prima del galà al Sociale di Trento",
        0,
        2,
        88,
        [("Sartoria Nove", "Smoking in lana", 1890), ("Calzoleria Adige", "Derby lucide", 590)],
    ),
    (
        "marco.bianchi",
        "old-money",
        "Domenica in centro, cachemire e mocassini",
        0,
        2,
        81,
        [
            ("Maglificio Garda", "Girocollo in cachemire", 420),
            ("Atelier Brera", "Chino blu notte", 180),
            ("Calzoleria Adige", "Mocassini in camoscio", 390),
        ],
    ),
    (
        "sofia.verdi",
        "streetwear",
        "Drop del sabato",
        1,
        3,
        74,
        [
            ("Northside", "Hoodie oversize", 120),
            ("Cargo Lab", "Pantalone cargo", 95),
            ("Runway 9", "Sneakers bianche", 150),
        ],
    ),
    (
        "luca.neri",
        "jappo",
        "Layering per Harajuku… versione Bolzano",
        0,
        2,
        86,
        [("Kumo", "Cappotto lungo", 340), ("Kumo", "Pantalone ampio", 160)],
    ),
    (
        "chiara.ferri",
        "minimal",
        "Tre capi, zero rumore",
        0,
        1,
        69,
        [("Linea Bianca", "T-shirt pesante", 45), ("Linea Bianca", "Pantalone ampio", 110)],
    ),
    (
        "tommaso.galli",
        "elegant",
        "Laurea del fratello",
        0,
        2,
        83,
        [
            ("Sartoria Nove", "Abito blu", 980),
            ("Camiceria Ponte", "Camicia bianca", 120),
            ("Seterie Como", "Cravatta bordeaux", 85),
        ],
    ),
    (
        "elena.conti",
        "gala",
        "Capodanno in rosso",
        1,
        3,
        92,
        [("Atelier Brera", "Giacca in velluto", 640), ("Sartoria Nove", "Pantalone nero", 290)],
    ),
    (
        "giulia.rossi",
        "old-money",
        "Pranzo al lago",
        1,
        2,
        77,
        [("Maglificio Garda", "Cardigan verde", 360), ("Atelier Brera", "Pantalone beige", 210)],
    ),
    (
        "marco.bianchi",
        "streetwear",
        "Concerto all'Arena",
        0,
        1,
        63,
        [("Northside", "Felpa grigia", 110), ("Runway 9", "Sneakers", 140)],
    ),
    (
        "sofia.verdi",
        "jappo",
        "Pioggia, cappotto e calma",
        1,
        2,
        79,
        [("Kumo", "Trench lungo", 380)],
    ),
    (
        "luca.neri",
        "minimal",
        "Ufficio, versione silenziosa",
        1,
        1,
        71,
        [("Linea Bianca", "Maglia nera", 70), ("Linea Bianca", "Pantalone sabbia", 120)],
    ),
    (
        "chiara.ferri",
        "elegant",
        "Matrimonio di Anna",
        1,
        2,
        85,
        [("Atelier Brera", "Completo grigio", 760), ("Seterie Como", "Cravatta blu", 80)],
    ),
    (
        "tommaso.galli",
        "streetwear",
        "Giro in skate al parco",
        2,
        2,
        68,
        [("Cargo Lab", "Bomber nero", 160), ("Cargo Lab", "Jeans chiari", 90)],
    ),
    (
        "elena.conti",
        "old-money",
        "Vernissage in Brera",
        2,
        2,
        90,
        [("Maglificio Garda", "Maglione panna", 290), ("Atelier Brera", "Pantalone tabacco", 230)],
    ),
    (
        "giulia.rossi",
        "gala",
        "Serata all'opera",
        2,
        2,
        84,
        [("Sartoria Nove", "Smoking blu notte", 1650)],
    ),
    (
        "marco.bianchi",
        "elegant",
        "Colloquio andato bene",
        1,
        1,
        76,
        [("Sartoria Nove", "Abito grigio", 890)],
    ),
    # I fit dell'ospite (per il portfolio e gli Insight).
    (
        "ospite.demo",
        "old-money",
        "Il mio primo fit su WearX",
        2,
        2,
        80,
        [("Maglificio Garda", "Maglione panna", 290)],
    ),
    (
        "ospite.demo",
        "streetwear",
        "Sabato in città",
        0,
        2,
        72,
        [("Northside", "Hoodie grigia", 120), ("Runway 9", "Sneakers bianche", 150)],
    ),
]


async def demo_seed(auth: Any, client: Any, store: Any) -> dict[str, Any]:
    from tests.test_accounts import onboarding_body

    quiet_logs()
    rng = random.Random(2026)  # noqa: S311 - dati di prova, non sicurezza
    tokens: dict[str, str] = {}
    control: dict[str, Any] = {"people": {}}
    for i, person in enumerate(PEOPLE):
        password = person.get("password", "Fit-di-prova-2026!")
        user = auth.create(person["email"], password)
        user["confirmed"] = True
        with cf.admin_conn(cf.TEST_DB) as db:
            cf.pass_age_check(db, uuid.UUID(user["id"]))
        token = auth.session(user)["access_token"]
        styles = STYLES if person is GUEST else rng.sample(STYLES, 3)
        r = await client.post(
            "/v1/onboarding/profile",
            json=onboarding_body(person["nickname"], styles=styles),
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code != 201:
            raise RuntimeError(f"onboarding {person['nickname']}: {r.status_code} {r.text}")
        with cf.admin_conn(cf.TEST_DB) as db:
            # Account "vecchi": i voti contano pieni e niente limiti dei nuovi arrivati.
            db.execute(
                "update app.profiles set created_at = now() - interval '60 days' where id = %s",
                (user["id"],),
            )
        tokens[person["nickname"]] = token
        control["people"][person["nickname"]] = {"id": user["id"], "order": i}

    def auth_header(nick: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens[nick]}"}

    # Foto profilo (il busto di un look, quadrato) e bio per quasi tutti (seduta 27).
    from app.media.keys import variant_key

    for k, person in enumerate(PEOPLE[1:]):
        nick = person["nickname"]
        style = STYLES[k % len(STYLES)]
        look = LOOKS[style][k % len(LOOKS[style])]
        portrait = draw_look(style, look, SKIN[k % len(SKIN)]).crop((240, 160, 840, 760))
        owner = uuid.UUID(control["people"][nick]["id"])
        with cf.admin_conn(cf.TEST_DB) as db:
            upload_id = cf.ready_upload(db, owner)
        for width in (320, 640, 1080):
            buf = io.BytesIO()
            portrait.resize((width, width)).save(buf, "WEBP", quality=86)
            await store.put(variant_key(upload_id, width), buf.getvalue(), "image/webp")
        body = {"avatar": str(upload_id), "bio": BIOS[k % len(BIOS)]}
        r = await client.patch("/v1/me", json=body, headers=auth_header(nick))
        if r.status_code != 200:
            raise RuntimeError(f"profilo {nick}: {r.status_code} {r.text}")

    posts: list[tuple[str, str, int]] = []  # (id, autore, voto medio)
    for author, style, caption, look_i, photos, score, items in POSTS:
        look = LOOKS[style][look_i % len(LOOKS[style])]
        skin = SKIN[rng.randrange(len(SKIN))]
        base = draw_look(style, look, skin, shift=rng.randint(-30, 30))
        images = [base, detail_crop(base), draw_look(style, look, skin, shade=0.12, shift=-60)]
        owner = uuid.UUID(control["people"][author]["id"])
        media: list[str] = []
        for img in images[:photos]:
            with cf.admin_conn(cf.TEST_DB) as db:
                upload_id = cf.ready_upload(db, owner)
            await put_image(store, upload_id, img)
            media.append(str(upload_id))
        body = {
            "style": style,
            "media": media,
            "caption": caption,
            "items": [
                {
                    "brand": brand,
                    "name": name,
                    "price_cents": price * 100,
                    "media_position": 0,
                    "pin_x": round(0.35 + 0.3 * (k % 2), 2),
                    "pin_y": round(0.38 + 0.22 * k, 2),
                }
                for k, (brand, name, price) in enumerate(items)
            ],
        }
        r = await client.post("/v1/posts", json=body, headers=auth_header(author))
        if r.status_code != 201:
            raise RuntimeError(f"post {caption}: {r.status_code} {r.text}")
        posts.append((r.json()["id"], author, score))

    # Capsule (seduta 28): per ogni persona una capsula per stile in cui ha almeno due fit, e una
    # "Preferiti" con un fit rimasto fuori: nel profilo si vedono schede di misure diverse.
    by_author: dict[str, list[tuple[str, str]]] = {}
    for (post_id, author, _), spec in zip(posts, POSTS, strict=True):
        by_author.setdefault(author, []).append((post_id, spec[1]))
    for author, owned in by_author.items():
        groups: dict[str, list[str]] = {}
        for post_id, style in owned:
            groups.setdefault(style, []).append(post_id)
        named = [
            (CAPSULE_NAMES.get(st, st.title()), ids) for st, ids in groups.items() if len(ids) > 1
        ]
        # Un fit sta in una sola capsula: "Preferiti" prende un fit rimasto fuori, se c'è.
        grouped = {post_id for _, ids in named for post_id in ids}
        loose = [post_id for post_id, _ in owned if post_id not in grouped]
        if loose:
            named.append(("Preferiti", loose[:1]))
        for name, ids in named:
            r = await client.post(
                "/v1/me/capsules", json={"name": name}, headers=auth_header(author)
            )
            r.raise_for_status()
            capsule_id = r.json()["id"]
            for post_id in ids:
                r = await client.patch(
                    f"/v1/posts/{post_id}",
                    json={"capsule_id": capsule_id},
                    headers=auth_header(author),
                )
                r.raise_for_status()

    # Voti: tutti tranne l'autore e l'ospite (così il feed dell'ospite è pieno di fit da votare).
    voters = [p["nickname"] for p in PEOPLE if p is not GUEST]
    for post_id, author, score in posts:
        for voter in voters:
            if voter == author:
                continue
            vote = max(1, min(100, score + rng.randint(-9, 9)))
            r = await client.put(
                f"/v1/posts/{post_id}/vote",
                json={"score": vote, "style_confirm": rng.random() > 0.08},
                headers=auth_header(voter),
            )
            if r.status_code not in (200, 201):
                raise RuntimeError(f"voto {voter}: {r.status_code} {r.text}")

    # Follow: l'ospite segue giulia (accettato) e ha chiesto a sofia (in attesa);
    # marco segue l'ospite, luca ha chiesto di seguirlo (richiesta da accettare).
    async def follow(who: str, whom: str, accept: bool) -> None:
        r = await client.post(f"/v1/users/{whom}/follow", headers=auth_header(who))
        r.raise_for_status()
        if accept:
            r = await client.post(
                "/v1/me/follow-requests",
                json={"nickname": who, "decision": "accept"},
                headers=auth_header(whom),
            )
            r.raise_for_status()

    await follow("ospite.demo", "giulia.rossi", accept=True)
    await follow("ospite.demo", "sofia.verdi", accept=False)
    await follow("marco.bianchi", "ospite.demo", accept=True)
    await follow("luca.neri", "ospite.demo", accept=False)

    await run_periodic_jobs()
    control["posts"] = [p[0] for p in posts]
    return control


# ---------- Lavori periodici (in produzione li fa il worker con i suoi orari) ----------


async def run_periodic_jobs() -> None:
    from app.worker import milestones, refresh_feeds, votes_hourly

    for job in (votes_hourly, refresh_feeds, milestones):
        try:
            await job({})
        except Exception as exc:  # la demo continua anche se un giro fallisce
            print(f"Lavoro {job.__name__} non riuscito: {exc}", file=sys.stderr, flush=True)


async def periodic_loop() -> None:
    while True:
        await asyncio.sleep(60)
        await run_periodic_jobs()


# ---------- Un solo indirizzo per tutto ----------


HOP_BY_HOP = frozenset(
    {
        "connection",
        "keep-alive",
        "transfer-encoding",
        "te",
        "trailer",
        "upgrade",
        "host",
        "proxy-authorization",
        "proxy-authenticate",
        "content-length",
    }
)


def s3_proxy(s3_port: int) -> Any:
    """Inoltra le richieste delle foto (caricamenti firmati e letture) all'archivio finto."""
    import httpx

    client = httpx.AsyncClient(base_url=f"http://127.0.0.1:{s3_port}", timeout=60)

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        headers = [
            (k.decode("latin-1"), v.decode("latin-1"))
            for k, v in scope["headers"]
            if k.decode("latin-1").lower() not in HOP_BY_HOP
        ]
        path = scope["raw_path"].decode("latin-1") if scope.get("raw_path") else scope["path"]
        query = scope.get("query_string", b"").decode("latin-1")
        url = path + (f"?{query}" if query else "")
        upstream = await client.request(scope["method"], url, headers=headers, content=body)
        out = [
            (k.encode("latin-1"), v.encode("latin-1"))
            for k, v in upstream.headers.items()
            if k.lower() not in HOP_BY_HOP and k.lower() != "content-encoding"
        ]
        out.append((b"content-length", str(len(upstream.content)).encode()))
        await send({"type": "http.response.start", "status": upstream.status_code, "headers": out})
        await send({"type": "http.response.body", "body": upstream.content})

    return app


def demo_router(api: Any, auth: Any, static: Any, photos: Any, bucket: str) -> Any:
    """Smista per indirizzo: /auth/v1 → accesso finto, /<bucket> → foto, API, il resto → app web."""

    async def not_found(send: Any) -> None:
        await send({"type": "http.response.start", "status": 404, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def app(scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] == "lifespan":
            await api(scope, receive, send)
            return
        if scope["type"] != "http":
            return
        path: str = scope["path"]
        first = path.split("/", 2)[1] if path.count("/") >= 1 else ""
        if path.startswith("/__e2e/"):
            await not_found(send)  # i comandi dei test non escono dal computer
        elif path.startswith("/auth/v1/"):
            await auth(scope, receive, send)
        elif first == bucket:
            await photos(scope, receive, send)
        elif first in API_ROOTS:
            await api(scope, receive, send)
        else:
            await static(scope, receive, send)

    return app


def print_banner() -> None:
    line = "─" * 64
    print(f"\n{line}\n  WearX demo pronta\n{line}", flush=True)
    print(f"\n  Link: {PUBLIC_URL}\n", flush=True)
    print("  Accesso già pronto:  ospite@demo.test  /  Demo-WearX-2026!", flush=True)
    print("  Nuova registrazione: il codice di conferma è sempre 123456\n", flush=True)
    if PUBLIC_URL.startswith("https://"):
        try:
            import segno

            print("  iPhone con l'app WearX Demo installata: inquadra questo QR con la", flush=True)
            print("  Fotocamera (oppure incolla il link nell'app).\n", flush=True)
            segno.make(f"wearx://demo?server={PUBLIC_URL}", error="l").terminal(compact=True)
            print("\n  Safari (iPhone, iPad, Android): inquadra questo QR.\n", flush=True)
            segno.make(PUBLIC_URL, error="l").terminal(compact=True)
        except ImportError:
            pass
    print(f"\n  Per fermare la demo: Ctrl+C\n{line}\n", flush=True)


def quiet_logs() -> None:
    """Nel terminale della demo solo avvisi ed errori, non una riga per ogni richiesta."""
    import logging

    for name in ("werkzeug", "httpx", "wearx", "wearx.access", "arq", "arq.worker", "arq.jobs"):
        logging.getLogger(name).setLevel(logging.WARNING)


async def main() -> None:
    quiet_logs()
    if not (DEMO_DIST / "index.html").is_file():
        sys.exit(f"Manca l'app web della demo in {DEMO_DIST} (la prepara scripts/demo.sh)")
    from app.media.jobs import process_upload
    from app.worker import export_data

    booted = await e2e.boot(
        storage_public_url=PUBLIC_URL,
        seed_fn=demo_seed,
        worker_functions=[process_upload, export_data],
    )
    router = demo_router(
        booted.api,
        booted.auth_asgi,
        e2e.static_app(DEMO_DIST),
        s3_proxy(booted.s3_port),
        booted.settings.storage_bucket,
    )
    quiet_logs()  # create_app riconfigura i log
    await e2e.serve(router, DEMO_PORT, booted)
    booted.tasks.append(asyncio.create_task(periodic_loop()))
    while not all(s.started for s in booted.servers):  # noqa: ASYNC110 - attesa dell'avvio
        await asyncio.sleep(0.05)
    ready = json.dumps({"url": PUBLIC_URL, "port": DEMO_PORT})
    await asyncio.to_thread(Path("demo-ready.json").write_text, ready)
    print_banner()
    await asyncio.gather(*booted.tasks)


if __name__ == "__main__":
    asyncio.run(main())
