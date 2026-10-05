"""Insight per chi pubblica (seduta 19)."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, time, timedelta

import pytest

from app.db import session_scope
from app.insights import ROME, aggregate_day, aggregate_recent, change, mask
from tests.conftest import ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")


def test_soglie():
    assert [mask(n) for n in (0, 1, 4, 5, 120)] == [0, None, None, 5, 120]
    assert change(10, 5) == 100.0
    assert change(9, 12) == -25.0
    assert change(4, 10) is None and change(10, 4) is None


def _yesterday():
    return datetime.now(ROME).date() - timedelta(days=1)


def _noon(day):
    return datetime.combine(day, time(12), tzinfo=ROME)


async def _post(client, db_admin, user_id, headers, caption):
    media = [str(ready_upload(db_admin, user_id))]
    r = await client.post(
        "/v1/posts",
        json={"style": "old-money", "media": media, "caption": caption},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


def _event(db, name, ts, *, post=None, actor=None, props="{}"):
    db.execute(
        "insert into app.events (actor_key, name, post_id, props, ts) values (%s, %s, %s, %s, %s)",
        (actor or os.urandom(16), name, post, props, ts),
    )


def _vote(db, post, ts, score):
    db.execute(
        "insert into app.votes (post_id, voter_key, score, created_at) values (%s, %s, %s, %s)",
        (post, os.urandom(32), score, ts),
    )


async def _seed(client, keys, db_admin):
    author_id, author, profile = await onboard(client, keys, db_admin)
    star = await _post(client, db_admin, author_id, author, "Prima alla Scala")
    quiet = await _post(client, db_admin, author_id, author, "Lunedì")
    day = _yesterday()
    ts = _noon(day)
    same = os.urandom(16)
    for _ in range(3):  # la stessa persona tre volte = una
        _event(db_admin, "post_impression", ts, post=star, actor=same)
    for _ in range(6):
        _event(db_admin, "post_impression", ts, post=star)
    for _ in range(3):
        _event(db_admin, "post_impression", ts, post=quiet)
    for _ in range(5):
        _event(db_admin, "post_open", ts, post=star)
    _event(db_admin, "shop_click", ts, post=star, props='{"item": 0}')
    _event(db_admin, "shop_click", ts, post=star, props='{"item": 1}')
    for _ in range(2):
        _event(db_admin, "profile_view", ts, props=f'{{"profile_id": "{author_id}"}}')
    for score in (90, 80, 70, 60, 100, 80):
        _vote(db_admin, star, ts, score)
    _vote(db_admin, quiet, ts, 50)
    _vote(db_admin, quiet, ts, 40)
    # Fuori periodo (oggi): non conta ancora.
    _event(db_admin, "post_impression", datetime.now(ROME), post=star)
    async with session_scope() as session:
        await aggregate_day(session, day)
        await session.commit()
    return author_id, author, profile["nickname"], star, quiet, day


async def test_insight_con_soglie(client, keys, db_admin):
    _, author, _, star, quiet, day = await _seed(client, keys, db_admin)
    r = await client.get("/v1/me/insights", headers=author)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["days"], body["bucket"], body["threshold"]) == (7, "day", 5)
    assert body["end"] == day.isoformat()
    totals = body["totals"]
    assert totals["impressions"] == {"value": 10, "change": None}  # 7 + 3 persone
    assert totals["opens"]["value"] == 5
    assert totals["votes"]["value"] == 8
    assert totals["average"] == 71.2  # (480 + 90) / 8
    assert totals["shop_clicks"] == {"value": None, "change": None}  # 2: "meno di 5"
    assert totals["profile_views"]["value"] is None
    assert len(body["series"]) == 7
    last = body["series"][-1]
    assert (last["start"], last["impressions"], last["votes"]) == (day.isoformat(), 10, 8)
    assert body["series"][0]["impressions"] == 0

    first, second = body["top_posts"]
    assert (first["id"], first["caption"]) == (str(star), "Prima alla Scala")
    assert first["style"] == "Old Money"
    assert (first["impressions"], first["votes"], first["average"]) == (7, 6, 80.0)
    assert first["shop_clicks"] is None and first["thumb"]["variants"]
    assert second["id"] == str(quiet)
    # 3 visualizzazioni e 2 voti: troppo pochi per mostrarli, e niente media.
    assert (second["impressions"], second["votes"], second["average"]) == (None, None, None)


async def test_confronto_col_periodo_prima_e_90_giorni(client, keys, db_admin):
    author_id, author, _, star, _, day = await _seed(client, keys, db_admin)
    before = day - timedelta(days=8)
    for _ in range(5):
        _event(db_admin, "post_impression", _noon(before), post=star)
    async with session_scope() as session:
        await aggregate_day(session, before)
        await session.commit()
    totals = (await client.get("/v1/me/insights", headers=author)).json()["totals"]
    assert totals["impressions"] == {"value": 10, "change": 100.0}
    assert totals["votes"]["change"] is None  # nessun voto nel periodo prima

    r = await client.get("/v1/me/insights", params={"days": 90}, headers=author)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["bucket"] == "week"
    assert 13 <= len(body["series"]) <= 14
    assert sum(p["impressions"] or 0 for p in body["series"]) == 15
    assert body["totals"]["impressions"]["value"] == 15
    bad = await client.get("/v1/me/insights", params={"days": 30}, headers=author)
    assert bad.status_code == 422
    assert author_id


async def test_solo_i_propri_dati_e_fit_cancellati(client, keys, db_admin):
    _, author, _, star, quiet, _ = await _seed(client, keys, db_admin)
    _, other, _ = await onboard(client, keys, db_admin)
    body = (await client.get("/v1/me/insights", headers=other)).json()
    assert body["totals"]["impressions"]["value"] == 0
    assert body["top_posts"] == []
    assert (await client.delete(f"/v1/posts/{quiet}", headers=author)).status_code == 204
    top = (await client.get("/v1/me/insights", headers=author)).json()["top_posts"]
    assert [p["id"] for p in top] == [str(star)]


async def test_riepilogo_ripetibile_e_primo_avvio(client, keys, db_admin):
    author_id, author, _, star, _, day = await _seed(client, keys, db_admin)
    before = (await client.get("/v1/me/insights", headers=author)).json()["totals"]
    db_admin.execute("delete from app.job_runs where name = 'insights'")
    async with session_scope() as session:
        assert await aggregate_recent(session) == 90  # primo avvio: tutta la storia
    async with session_scope() as session:
        assert await aggregate_recent(session) == 2  # poi ieri e l'altro ieri
    after = (await client.get("/v1/me/insights", headers=author)).json()
    assert after["totals"] == before
    assert after["updated_at"] is not None
    rows = db_admin.execute(
        "select count(*) from app.insight_daily where post_id = %s and day = %s", (star, day)
    ).fetchone()
    assert rows == (1,)
    assert author_id
