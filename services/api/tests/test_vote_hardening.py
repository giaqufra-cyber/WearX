"""Seduta 22: media pubblicata ogni ora (senza ricavare i singoli voti) e voti sospetti."""

from __future__ import annotations

import pytest

from app import votes as votes_module
from app.db import session_scope
from app.votes import detect_vote_abuse, voter_key
from tests.test_admin_console import _staff
from tests.test_votes import _person, _post, _seen, _stats, _vote, publish

pytestmark = pytest.mark.usefixtures("store")


async def _voters(client, keys, db_admin, n):
    return [await _person(client, keys, db_admin) for _ in range(n)]


async def detect():
    async with session_scope() as session:
        return await detect_vote_abuse(session)


def _flags(db_admin, user_id):
    """Segnali di un votante (gli altri test lasciano voti e segnali nel database)."""
    return db_admin.execute(
        "select rule, votes_affected from app.vote_flags where voter_key = %s order by id",
        (voter_key(user_id),),
    ).fetchall()


# ---------- Pubblicazione oraria ----------


async def test_media_da_5_voti_e_a_gruppi_di_almeno_3(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    people = await _voters(client, keys, db_admin, 9)

    for _, h in people[:4]:
        await _vote(client, post_id, h, 60)
    await publish()
    own = await _seen(client, post_id, author)
    assert (own["vote_count"], own["average"], own["average_note"]) == (4, None, "few_votes")

    await _vote(client, post_id, people[4][1], 80)  # quinto voto
    await publish()
    own = await _seen(client, post_id, author)
    assert (own["vote_count"], own["average"]) == (5, 64.0)

    # Un solo voto nuovo: il numero sale, la media resta quella di prima (non si ricava il voto).
    await _vote(client, post_id, people[5][1], 100)
    await publish()
    own = await _seen(client, post_id, author)
    assert (own["vote_count"], own["average"], own["average_note"]) == (6, 64.0, None)

    # Un altro voto nuovo: 2 in attesa, la media resta.
    await _vote(client, post_id, people[6][1], 40)
    await publish()
    assert (await _seen(client, post_id, author))["average"] == 64.0
    # Anche cambiare un voto conta come aggiornamento: 2 nuovi + 1 cambiato = 3.
    await _vote(client, post_id, people[0][1], 90)
    await publish()
    own = await _seen(client, post_id, author)
    # (90 + 60 x 3 + 80 + 100 + 40) / 7 = 70
    assert (own["vote_count"], own["average"]) == (7, 70.0)
    await _vote(client, post_id, people[7][1], 50)
    await publish()
    assert (await _seen(client, post_id, author))["average"] == 70.0
    # Chi ha votato vede gli stessi valori pubblicati.
    seen = await _seen(client, post_id, people[7][1])
    assert (seen["vote_count"], seen["average"], seen["mine"]) == (8, 70.0, 50)


async def test_senza_aggiornamento_nulla_cambia(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    for _, h in await _voters(client, keys, db_admin, 5):
        await _vote(client, post_id, h, 70)
    own = await _seen(client, post_id, author)
    assert (own["vote_count"], own["average"]) == (0, None)
    await publish()
    await publish()  # ripetuto: stesso risultato
    own = await _seen(client, post_id, author)
    assert (own["vote_count"], own["average"]) == (5, 70.0)


# ---------- Voti sospetti ----------


async def test_stesso_voto_ovunque_neutralizzato_e_ripristinabile(
    client, keys, db_admin, monkeypatch
):
    monkeypatch.setattr(votes_module, "SAME_SCORE_MIN_VOTES", 4)
    authors = [await _person(client, keys, db_admin) for _ in range(2)]
    posts = [await _post(client, db_admin, a_id, a) for a_id, a in authors for _ in range(2)]
    bot_id, bot = await _person(client, keys, db_admin)
    honest = await _voters(client, keys, db_admin, 5)
    for j, p in enumerate(posts):
        await _vote(client, p, bot, 77)
        for i, (_, h) in enumerate(honest):
            await _vote(client, p, h, 50 + i * 10 + j)
    await publish()

    await detect()
    await detect()  # ripetuto: nessun doppione
    assert _flags(db_admin, bot_id) == [("same_score", 4)]
    assert all(_flags(db_admin, h_id) == [] for h_id, _ in honest)
    weights = db_admin.execute(
        "select distinct weight from app.votes where voter_key = %s", (voter_key(bot_id),)
    ).fetchall()
    assert weights == [(0.0,)]
    count, *_, wsum, wcount = _stats(db_admin, posts[0])
    assert (count, wsum / wcount) == (5, 70.0)  # solo i 5 voti onesti
    await publish()
    own = await _seen(client, posts[0], authors[0][1])
    assert (own["vote_count"], own["average"]) == (5, 70.0)

    # Il bot non se ne accorge: il suo voto resta "suo"; i voti nuovi non contano.
    assert (await _seen(client, posts[0], bot))["mine"] == 77
    extra = await _post(client, db_admin, *authors[0])
    await _vote(client, extra, bot, 77)
    assert _stats(db_admin, extra)[0] == 0

    # Lo staff ripristina (falso positivo): i voti tornano a contare.
    _, staff, _ = await _staff(client, keys, db_admin)
    listed = (await client.get("/v1/admin/vote-flags", headers=staff)).json()
    flag_id = db_admin.execute(
        "select id from app.vote_flags where voter_key = %s", (voter_key(bot_id),)
    ).fetchone()[0]
    [flag] = [f for f in listed if f["id"] == flag_id]
    assert (flag["rule"], flag["author"], flag["votes_affected"], flag["active"]) == (
        "same_score",
        None,
        4,
        True,
    )
    assert len(flag["voter"]) == 8
    r = await client.post(f"/v1/admin/vote-flags/{flag['id']}/lift", headers=staff)
    assert r.status_code == 204
    r = await client.post(f"/v1/admin/vote-flags/{flag['id']}/lift", headers=staff)
    assert r.status_code == 404
    assert _stats(db_admin, posts[0])[0] == 6
    assert _stats(db_admin, extra)[0] == 1
    audit = db_admin.execute(
        "select count(*) from app.admin_audit_log where action = 'admin.lift_vote_flag'"
    ).fetchone()
    assert audit[0] >= 1


async def test_spinta_mirata_su_un_autore(client, keys, db_admin, monkeypatch):
    monkeypatch.setattr(votes_module, "AUTHOR_BURST_MIN_VOTES", 3)
    target_id, target = await _person(client, keys, db_admin)
    other_id, other = await _person(client, keys, db_admin)
    pumped = [await _post(client, db_admin, target_id, target) for _ in range(3)]
    elsewhere = await _post(client, db_admin, other_id, other)
    fan_id, fan = await _person(client, keys, db_admin)
    for p in pumped:
        await _vote(client, p, fan, 100)
    await _vote(client, elsewhere, fan, 100)

    await detect()
    assert _flags(db_admin, fan_id) == [("author_burst", 3)]
    rows = dict(
        db_admin.execute(
            "select post_id::text, weight from app.votes where voter_key = %s",
            (voter_key(fan_id),),
        ).fetchall()
    )
    assert all(rows[p] == 0 for p in pumped)
    assert rows[elsewhere] == 1.0  # solo i fit di quell'autore
    _, staff, _ = await _staff(client, keys, db_admin)
    nickname = db_admin.execute(
        "select nickname::text from app.profiles where id = %s", (target_id,)
    ).fetchone()[0]
    listed = (await client.get("/v1/admin/vote-flags", headers=staff)).json()
    assert any(f["rule"] == "author_burst" and f["author"] == nickname for f in listed)


async def test_voti_vari_non_segnalati(client, keys, db_admin, monkeypatch):
    monkeypatch.setattr(votes_module, "SAME_SCORE_MIN_VOTES", 4)
    monkeypatch.setattr(votes_module, "AUTHOR_BURST_MIN_VOTES", 3)
    author_id, author = await _person(client, keys, db_admin)
    posts = [await _post(client, db_admin, author_id, author) for _ in range(4)]
    person_id, person = await _person(client, keys, db_admin)
    for p, score in zip(posts, (88, 97, 100, 61), strict=True):
        await _vote(client, p, person, score)
    await detect()
    assert _flags(db_admin, person_id) == []


async def test_raffica_di_voti_fermata(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    _, voter = await _person(client, keys, db_admin)
    codes = [(await _vote(client, post_id, voter, 1 + i)).status_code for i in range(41)]
    assert codes[:40] == [200] * 40
    assert codes[40] == 429
