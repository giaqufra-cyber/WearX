"""Voti: anonimato, statistiche esatte (anche in contemporanea), conferma dello stile."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.votes import bucket, style_match, vote_weight, voter_key
from tests.conftest import ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")


async def _person(client, keys, db_admin, *, aged=True, **kw):
    user_id, headers, _ = await onboard(client, keys, db_admin, **kw)
    if aged:  # account "vecchio": il voto pesa 1
        db_admin.execute(
            "update app.profiles set created_at = now() - interval '30 days' where id = %s",
            (user_id,),
        )
    return user_id, headers


async def _post(client, db_admin, user_id, headers, style="old-money"):
    media = [str(ready_upload(db_admin, user_id))]
    r = await client.post("/v1/posts", json={"style": style, "media": media}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _vote(client, post_id, headers, score, confirm=None):
    body = {"score": score}
    if confirm is not None:
        body["style_confirm"] = confirm
    return await client.put(f"/v1/posts/{post_id}/vote", json=body, headers=headers)


def _stats(db_admin, post_id):
    return db_admin.execute(
        """select vote_count, vote_sum, hist, confirm_yes, confirm_no, vote_wsum, vote_wcount
             from app.post_stats where post_id = %s""",
        (post_id,),
    ).fetchone()


# ---------- Regole pure ----------


def test_chiave_anonima_del_votante():
    a, b = uuid.uuid4(), uuid.uuid4()
    assert voter_key(a) == voter_key(a)
    assert voter_key(a) != voter_key(b)
    assert len(voter_key(a)) == 32
    assert a.bytes not in voter_key(a)


def test_peso_e_fasce():
    now = datetime.now(UTC)
    assert vote_weight(now - timedelta(hours=2), now) == 0.5
    assert vote_weight(now - timedelta(days=2), now) == 1.0
    assert [bucket(s) for s in (1, 10, 11, 50, 91, 100)] == [1, 1, 2, 5, 10, 10]
    assert style_match(5, 4) is None  # meno di 10 risposte
    assert style_match(7, 3) == 0.7


# ---------- Voto ----------


async def test_voto_e_riepilogo(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, voter = await _person(client, keys, db_admin)
    _, other = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)

    before = (await client.get(f"/v1/posts/{post_id}", headers=voter)).json()["vote"]
    assert before == {
        "mine": None,
        "my_style_confirm": None,
        "average": None,
        "vote_count": None,
        "style_match": None,
        "ask_style_confirm": True,
    }

    r = await _vote(client, post_id, voter, 80, confirm=True)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "mine": 80,
        "my_style_confirm": True,
        "average": 80.0,
        "vote_count": 1,
        "style_match": None,
        "ask_style_confirm": False,
    }
    # Chi non ha votato non vede la media (nessuna influenza).
    seen = (await client.get(f"/v1/posts/{post_id}", headers=other)).json()["vote"]
    assert (seen["average"], seen["vote_count"]) == (None, None)
    # L'autore la vede sempre, ma non può votarsi.
    own = (await client.get(f"/v1/posts/{post_id}", headers=author)).json()["vote"]
    assert (own["average"], own["vote_count"], own["ask_style_confirm"]) == (80.0, 1, False)
    r = await _vote(client, post_id, author, 100)
    assert (r.status_code, r.json()["code"]) == (403, "vote.own_post")

    count, total, hist, yes, no, _, _ = _stats(db_admin, post_id)
    assert (count, total, hist[7], yes, no) == (1, 80, 1, 1, 0)


async def test_nel_database_non_c_e_chi_ha_votato(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    voter_id, voter = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    await _vote(client, post_id, voter, 55)
    rows = db_admin.execute(
        "select voter_key from app.votes where post_id = %s", (post_id,)
    ).fetchall()
    assert rows == [(voter_key(voter_id),)]
    columns = db_admin.execute(
        "select column_name from information_schema.columns "
        "where table_schema = 'app' and table_name = 'votes'"
    ).fetchall()
    assert not any("user" in c[0] for c in columns)


async def test_cambiare_voto(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, voter = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    await _vote(client, post_id, voter, 80, confirm=True)
    await _vote(client, post_id, voter, 75, confirm=False)  # stessa fascia (71-80)
    count, total, hist, yes, no, _, _ = _stats(db_admin, post_id)
    assert (count, total, hist[7], yes, no) == (1, 75, 1, 1, 0)  # la conferma resta la prima
    r = await _vote(client, post_id, voter, 30)  # fascia diversa
    assert r.json()["mine"] == 30
    count, total, hist, *_ = _stats(db_admin, post_id)
    assert (count, total, hist[2], hist[7], sum(hist)) == (1, 30, 1, 0, 1)


@pytest.mark.parametrize("score", [0, 101, -5])
async def test_voto_fuori_scala(client, keys, db_admin, score):
    author_id, author = await _person(client, keys, db_admin)
    _, voter = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    r = await _vote(client, post_id, voter, score)
    assert (r.status_code, r.json()["code"]) == (422, "request.invalid")


async def test_post_non_visibili_non_si_votano(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, minor = await _person(client, keys, db_admin, minor=True)
    adult_only = await _post(client, db_admin, author_id, author, style="beach-party")
    hidden = await _post(client, db_admin, author_id, author)
    db_admin.execute("update app.posts set status = 'hidden_moderation' where id = %s", (hidden,))
    deleted = await _post(client, db_admin, author_id, author)
    await client.delete(f"/v1/posts/{deleted}", headers=author)
    for post_id in (adult_only, hidden, deleted, str(uuid.uuid4())):
        r = await _vote(client, post_id, minor, 70)
        assert (r.status_code, r.json()["code"]) == (404, "post.not_found")


async def test_account_nuovi_pesano_meta(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, fresh = await _person(client, keys, db_admin, aged=False)
    _, old = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    await _vote(client, post_id, fresh, 100)
    r = await _vote(client, post_id, old, 40)
    # (100 x 0,5 + 40 x 1) / 1,5 = 60
    assert (r.json()["average"], r.json()["vote_count"]) == (60.0, 2)


async def test_numero_di_voti_nascosto_dall_autore(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, voter = await _person(client, keys, db_admin)
    db_admin.execute("update app.profiles set hide_vote_count = true where id = %s", (author_id,))
    post_id = await _post(client, db_admin, author_id, author)
    r = await _vote(client, post_id, voter, 70)
    assert (r.json()["average"], r.json()["vote_count"]) == (70.0, None)
    own = (await client.get(f"/v1/posts/{post_id}", headers=author)).json()["vote"]
    assert own["vote_count"] == 1


# ---------- Contemporaneità ----------


async def test_tanti_voti_insieme_statistiche_esatte(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    voters = [await _person(client, keys, db_admin) for _ in range(40)]
    scores = [(i * 7) % 100 + 1 for i in range(40)]
    results = await asyncio.gather(
        *[_vote(client, post_id, h, s) for (_, h), s in zip(voters, scores, strict=True)]
    )
    assert all(r.status_code == 200 for r in results)
    count, total, hist, *_ = _stats(db_admin, post_id)
    assert (count, total, sum(hist)) == (40, sum(scores), 40)
    for b in range(1, 11):
        assert hist[b - 1] == sum(1 for s in scores if bucket(s) == b)


async def test_stessa_persona_dieci_voti_insieme_un_voto_solo(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, voter = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    results = await asyncio.gather(*[_vote(client, post_id, voter, 50 + i) for i in range(10)])
    assert all(r.status_code == 200 for r in results)
    stored = db_admin.execute(
        "select count(*), max(score) from app.votes where post_id = %s", (post_id,)
    ).fetchone()
    count, total, hist, *_ = _stats(db_admin, post_id)
    assert stored[0] == 1
    assert (count, total, sum(hist)) == (1, stored[1], 1)


# ---------- Conferma dello stile ----------


async def test_sotto_il_70_per_cento_il_post_esce_dallo_stile(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    voters = [await _person(client, keys, db_admin) for _ in range(11)]
    for i, (_, headers) in enumerate(voters[:10]):
        await _vote(client, post_id, headers, 60, confirm=i < 6)  # 6 sì, 4 no = 60%
    status = db_admin.execute("select status::text from app.posts where id = %s", (post_id,))
    assert status.fetchone() == ("style_rejected",)

    # Resta visibile e votabile (portfolio), ma senza più la domanda sullo stile.
    _, late = voters[10]
    seen = (await client.get(f"/v1/posts/{post_id}", headers=late)).json()
    assert seen["status"] == "style_rejected"
    assert seen["vote"]["ask_style_confirm"] is False
    r = await _vote(client, post_id, late, 70, confirm=True)
    assert (r.status_code, r.json()["style_match"]) == (200, 0.6)

    # L'autore cambia stile: torna attivo e la verifica riparte da zero.
    r = await client.patch(f"/v1/posts/{post_id}", json={"style": "elegant"}, headers=author)
    assert r.json()["status"] == "active"
    assert _stats(db_admin, post_id)[3:5] == (0, 0)
    _, newcomer = await _person(client, keys, db_admin)
    seen = (await client.get(f"/v1/posts/{post_id}", headers=newcomer)).json()
    assert seen["vote"]["ask_style_confirm"] is True


async def test_con_il_70_per_cento_resta(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    for i in range(10):
        _, headers = await _person(client, keys, db_admin)
        r = await _vote(client, post_id, headers, 75, confirm=i < 7)
    assert r.json()["style_match"] == 0.7
    status = db_admin.execute("select status::text from app.posts where id = %s", (post_id,))
    assert status.fetchone() == ("active",)


async def test_solo_i_primi_30_confermano(client, keys, db_admin):
    author_id, author = await _person(client, keys, db_admin)
    _, voter = await _person(client, keys, db_admin)
    post_id = await _post(client, db_admin, author_id, author)
    db_admin.execute("update app.post_stats set confirm_yes = 30 where post_id = %s", (post_id,))
    seen = (await client.get(f"/v1/posts/{post_id}", headers=voter)).json()
    assert seen["vote"]["ask_style_confirm"] is False
    r = await _vote(client, post_id, voter, 90, confirm=False)
    assert r.json()["my_style_confirm"] is None
    assert _stats(db_admin, post_id)[3:5] == (30, 0)
