"""Moderazione: controlli sulle foto e sui testi, segnalazioni con priorità, decisioni dello
staff con motivazione, scala delle sanzioni, reclami (sez. 13.2 e 14)."""

from __future__ import annotations

import pytest

from app.moderation.scanning import HashHit, decide, set_classifier, set_hash_matchers
from tests.authkit import bearer
from tests.conftest import ready_upload
from tests.imagekit import photo
from tests.test_accounts import onboard
from tests.test_media_api import _upload_and_process

pytestmark = pytest.mark.usefixtures("store")


async def _person(client, keys, db_admin, *, minor=False, aged=True, business=False):
    user_id, headers, profile = await onboard(client, keys, db_admin, minor=minor)
    if aged:  # account di almeno 24 ore: le sue segnalazioni contano per le azioni automatiche
        db_admin.execute(
            "update app.profiles set created_at = now() - interval '30 days' where id = %s",
            (user_id,),
        )
    if business:
        db_admin.execute(
            "update app.profiles set account_type = 'business' where id = %s", (user_id,)
        )
    return user_id, headers, profile["nickname"]


async def _post(client, db_admin, user_id, headers, *, media=None, caption="Un fit"):
    media = media or [str(ready_upload(db_admin, user_id))]
    r = await client.post(
        "/v1/posts",
        json={"style": "old-money", "media": media, "caption": caption},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _report(client, headers, post_id, reason="spam", **extra):
    body = {"target_type": "post", "target_id": post_id, "reason": reason, **extra}
    return await client.post("/v1/reports", json=body, headers=headers)


async def _staff(client, keys, db_admin, role="moderator"):
    user_id, _, _ = await _person(client, keys, db_admin)
    db_admin.execute("insert into app.staff (user_id, role) values (%s, %s)", (user_id, role))
    return user_id, bearer(keys.token(user_id, aal="aal2"))


def _status(db_admin, post_id):
    return db_admin.execute(
        "select status::text from app.posts where id = %s", (post_id,)
    ).fetchone()[0]


# ---------- Decisione sulle foto (funzione pura) ----------


def test_decisione_sulle_foto():
    assert decide(HashHit("csam", "photodna"), {}, minor=False).incident is True
    removed = decide(HashHit("removed", "action:x"), {}, minor=False)
    assert (removed.verdict, removed.incident, removed.reason) == ("block", False, "hash:removed")
    assert decide(None, {}, minor=False).verdict == "allow"
    assert decide(None, {"sexual": 0.9}, minor=False).verdict == "block"
    assert decide(None, {"sexual": 0.6}, minor=False).verdict == "review"
    assert decide(None, {"sexual": 0.4}, minor=False).verdict == "allow"
    # Per i 16-17 le soglie sono più severe.
    assert decide(None, {"sexual": 0.4}, minor=True).verdict == "review"
    assert decide(None, {"sexual": 0.6}, minor=True).verdict == "block"
    assert decide(None, {"nudity": 0.7, "violence": 0.95}, minor=False).reason == "label:violence"
    assert decide(None, {"altro": 1.0}, minor=False).verdict == "allow"  # categorie sconosciute


# ---------- Pipeline delle foto ----------


class _Labels:
    def __init__(self, labels):
        self.labels = labels

    async def classify(self, image):
        return self.labels


async def test_foto_da_rivedere_mette_il_fit_in_coda(client, keys, db_admin, store, queue):
    set_classifier(_Labels({"nudity": 0.7}))
    try:
        uid, h, _ = await _person(client, keys, db_admin)
        upload_id, outcome = await _upload_and_process(client, h, store, queue, photo(seed=1))
    finally:
        set_classifier(None)
    assert outcome == "ready"
    row = db_admin.execute(
        "select needs_review, scan_labels from app.media_uploads where id = %s", (upload_id,)
    ).fetchone()
    assert row == (True, {"nudity": 0.7})
    post = await _post(client, db_admin, uid, h, media=[upload_id])
    assert _status(db_admin, post) == "active"  # adulto: resta visibile, ma in coda
    report = db_admin.execute(
        "select reason, priority, auto, reporter_id from app.reports where target_id = %s", (post,)
    ).fetchone()
    assert report == ("nudity", 1, True, None)


async def test_foto_da_rivedere_di_un_16_17_resta_nascosta(client, keys, db_admin, store, queue):
    set_classifier(_Labels({"sexual": 0.35}))
    try:
        uid, h, _ = await _person(client, keys, db_admin, minor=True)
        upload_id, outcome = await _upload_and_process(client, h, store, queue, photo(seed=2))
    finally:
        set_classifier(None)
    assert outcome == "ready"
    post = await _post(client, db_admin, uid, h, media=[upload_id])
    assert _status(db_admin, post) == "hidden_moderation"
    notices = (await client.get("/v1/me/moderation", headers=h)).json()
    assert notices[0]["action"] == "hide"
    assert notices[0]["automated"] is True
    assert "controllo automatico" in notices[0]["reason"]


async def test_materiale_illegale_noto_sospende_e_apre_un_caso_p0(
    client, keys, db_admin, store, queue
):
    class KnownBad:
        async def match(self, session, sha256, phash):
            return HashHit("csam", "servizio-esterno")

    set_hash_matchers([KnownBad()])
    try:
        uid, h, _ = await _person(client, keys, db_admin)
        upload_id, outcome = await _upload_and_process(client, h, store, queue, photo(seed=3))
    finally:
        set_hash_matchers(None)
    assert outcome == "rejected:blocked"
    status = db_admin.execute("select status::text from app.profiles where id = %s", (uid,))
    assert status.fetchone() == ("suspended",)
    report = db_admin.execute(
        """select reason, priority, auto from app.reports
            where target_type = 'profile' and target_id = %s""",
        (uid,),
    ).fetchone()
    assert report == ("minor_safety", 0, True)
    # Anche da sospeso vede la motivazione e può fare reclamo.
    notices = (await client.get("/v1/me/moderation", headers=h)).json()
    assert (notices[0]["action"], notices[0]["can_appeal"]) == ("suspend", True)
    # Nessuna foto conservata.
    stored = db_admin.execute(
        "select status::text from app.media_uploads where id = %s", (upload_id,)
    ).fetchone()
    assert stored == ("rejected",)


# ---------- Testi ----------


async def test_parole_offensive(client, keys, db_admin):
    uid, h, _ = await _person(client, keys, db_admin)
    media = [str(ready_upload(db_admin, uid))]
    r = await client.post(
        "/v1/posts",
        json={"style": "old-money", "media": media, "caption": "sei una p.u.t.t.a.n.a"},
        headers=h,
    )
    assert (r.status_code, r.json()["code"]) == (422, "text.not_allowed")
    r = await client.patch("/v1/me", json={"bio": "Fr0c10 chi legge"}, headers=h)
    assert r.json()["code"] == "text.not_allowed"
    r = await client.post("/v1/auth/nickname-check", json={"nickname": "la_puttana99"})
    assert r.json() == {"nickname": "la_puttana99", "available": False, "reason": "reserved"}
    # Parole innocue che contengono pezzi simili passano.
    r = await client.post("/v1/auth/nickname-check", json={"nickname": "montenegro_style"})
    assert r.json()["available"] is True
    # Chi segnala può citare l'insulto ricevuto.
    other_id, other_h, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, other_id, other_h)
    r = await _report(client, h, post, "harassment", details="mi ha scritto troia nel brand")
    assert r.status_code == 201


# ---------- Segnalazioni ----------


async def test_segnalare_un_fit(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    _, me, _ = await _person(client, keys, db_admin)

    r = await _report(client, me, post, "spam")
    assert r.status_code == 201
    assert (r.json()["priority"], r.json()["review_within_hours"]) == (2, 72)
    again = await _report(client, me, post, "spam")
    assert (again.status_code, again.json()["id"]) == (200, r.json()["id"])  # una sola aperta
    assert _status(db_admin, post) == "active"  # P2: nessuna azione automatica

    r = await _report(client, author, post)
    assert (r.status_code, r.json()["code"]) == (422, "report.own_content")
    r = await _report(client, me, "00000000-0000-0000-0000-000000000000")
    assert (r.status_code, r.json()["code"]) == (404, "post.not_found")
    r = await client.post("/v1/reports", json={"target_type": "post", "reason": "spam"}, headers=me)
    assert r.status_code == 422


async def test_segnalare_profilo_e_link(client, keys, db_admin):
    author_id, author, nick = await _person(client, keys, db_admin)
    media = [str(ready_upload(db_admin, author_id))]
    r = await client.post(
        "/v1/posts",
        json={
            "style": "old-money",
            "media": media,
            "items": [{"brand": "X", "name": "Y", "url": "https://negozio-strano.example/x"}],
        },
        headers=author,
    )
    link_id = r.json()["items"][0]["link"]["id"]
    _, me, my_nick = await _person(client, keys, db_admin)
    r = await client.post(
        "/v1/reports",
        json={"target_type": "profile", "nickname": nick, "reason": "harassment"},
        headers=me,
    )
    assert (r.status_code, r.json()["priority"]) == (201, 1)
    r = await client.post(
        "/v1/reports",
        json={"target_type": "link", "target_id": link_id, "reason": "dangerous_link"},
        headers=me,
    )
    assert r.status_code == 201
    r = await client.post(
        "/v1/reports",
        json={"target_type": "profile", "nickname": my_nick, "reason": "spam"},
        headers=me,
    )
    assert r.json()["code"] == "report.own_content"


async def test_p1_si_nasconde_dopo_tre_persone_vere(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author, caption="Serata")
    # Due account appena creati non bastano (né contano).
    for _ in range(2):
        _, fresh, _ = await _person(client, keys, db_admin, aged=False)
        await _report(client, fresh, post, "nudity")
    for _ in range(2):
        _, trusted, _ = await _person(client, keys, db_admin)
        await _report(client, trusted, post, "nudity")
    assert _status(db_admin, post) == "active"
    _, third, _ = await _person(client, keys, db_admin)
    await _report(client, third, post, "harassment")
    assert _status(db_admin, post) == "hidden_moderation"
    notice = (await client.get("/v1/me/moderation", headers=author)).json()[0]
    assert notice["action"] == "hide"
    assert "«Serata»" in notice["statement"] and "reclamo" in notice["statement"]
    assert notice["post_id"] == post


async def test_p0_nasconde_subito_e_due_persone_sospendono(client, keys, db_admin):
    author_id, author, author_nick = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    _, first, _ = await _person(client, keys, db_admin)
    r = await _report(client, first, post, "minor_safety")
    assert (r.json()["priority"], r.json()["review_within_hours"]) == (0, 1)
    assert _status(db_admin, post) == "hidden_moderation"
    status = db_admin.execute("select status::text from app.profiles where id = %s", (author_id,))
    assert status.fetchone() == ("active",)  # una sola segnalazione non sospende nessuno
    # Il fit ora è nascosto: un'altra persona segnala il profilo.
    _, second, _ = await _person(client, keys, db_admin)
    r = await client.post(
        "/v1/reports",
        json={"target_type": "profile", "nickname": author_nick, "reason": "minor_safety"},
        headers=second,
    )
    assert r.status_code == 201
    status = db_admin.execute("select status::text from app.profiles where id = %s", (author_id,))
    assert status.fetchone() == ("suspended",)


# ---------- Staff ----------


async def test_solo_staff_con_secondo_fattore(client, keys, db_admin):
    _, user, _ = await _person(client, keys, db_admin)
    r = await client.get("/v1/admin/reports/queue", headers=user)
    assert r.status_code == 404  # per chi non è staff non esiste
    staff_id, staff = await _staff(client, keys, db_admin)
    r = await client.get("/v1/admin/reports/queue", headers=bearer(keys.token(staff_id)))
    assert (r.status_code, r.json()["code"]) == (403, "staff.mfa_required")
    assert (await client.get("/v1/admin/reports/queue", headers=staff)).status_code == 200


async def test_coda_raggruppata_per_priorita(client, keys, db_admin):
    db_admin.execute("update app.reports set status = 'dismissed'")
    author_id, author, _ = await _person(client, keys, db_admin)
    spam_post = await _post(client, db_admin, author_id, author, caption="spam")
    bad_post = await _post(client, db_admin, author_id, author, caption="grave")
    for _ in range(2):
        _, r, _ = await _person(client, keys, db_admin)
        await _report(client, r, spam_post, "spam", details="link ovunque")
    _, r, _ = await _person(client, keys, db_admin)
    await _report(client, r, bad_post, "minor_safety")
    db_admin.execute(
        "update app.reports set created_at = now() - interval '2 hours' where target_id = %s",
        (bad_post,),
    )
    _, staff = await _staff(client, keys, db_admin)
    items = (await client.get("/v1/admin/reports/queue", headers=staff)).json()
    assert [i["target_id"] for i in items] == [bad_post, spam_post]
    assert (items[0]["priority"], items[0]["overdue"]) == (0, True)
    assert items[1]["reasons"] == {"spam": 2}
    assert items[1]["details"] == ["link ovunque", "link ovunque"]
    assert items[1]["post"]["caption"] == "spam"
    p2 = (await client.get("/v1/admin/reports/queue?priority=2", headers=staff)).json()
    assert [i["target_id"] for i in p2] == [spam_post]


async def test_archiviare_ripristina_cio_che_era_nascosto_in_automatico(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    _, reporter, _ = await _person(client, keys, db_admin)
    await _report(client, reporter, post, "minor_safety")
    assert _status(db_admin, post) == "hidden_moderation"
    _, staff = await _staff(client, keys, db_admin)
    r = await client.post(
        "/v1/admin/reports/decide",
        json={"target_type": "post", "target_id": post, "decision": "dismiss", "ground": "other"},
        headers=staff,
    )
    assert r.status_code == 200, r.text
    assert r.json()["resolved_reports"] == 1
    assert _status(db_admin, post) == "active"
    last = (await client.get("/v1/me/moderation", headers=author)).json()[0]
    assert last["action"] == "restore" and last["can_appeal"] is False


async def test_scala_delle_sanzioni(client, keys, db_admin):
    author_id, author, nick = await _person(client, keys, db_admin)
    _, staff = await _staff(client, keys, db_admin)

    async def violation(expected):
        post = await _post(client, db_admin, author_id, author)
        r = await client.post(
            "/v1/admin/reports/decide",
            json={
                "target_type": "post",
                "target_id": post,
                "decision": "hide",
                "sanction": "auto",
                "ground": "harassment",
            },
            headers=staff,
        )
        assert r.json()["sanction"] == expected
        return post

    await violation("warn")
    await violation("limit_posting")
    # Pubblicazione sospesa per 7 giorni: si vede e si vota, ma non si pubblica.
    r = await client.post(
        "/v1/posts",
        json={"style": "old-money", "media": [str(ready_upload(db_admin, author_id))]},
        headers=author,
    )
    assert (r.status_code, r.json()["code"]) == (403, "account.posting_restricted")
    assert (await client.get("/v1/feed", headers=author)).status_code == 200
    db_admin.execute(
        "update app.profiles set posting_blocked_until = null where id = %s", (author_id,)
    )
    await violation("ban")
    status = db_admin.execute("select status::text from app.profiles where id = %s", (author_id,))
    assert status.fetchone() == ("suspended",)

    case = (await client.get(f"/v1/admin/users/{nick}", headers=staff)).json()
    assert case["status"] == "suspended"
    assert case["strikes"] == 2  # avviso + sospensione (la chiusura è l'ultima tappa)
    assert {a["action"] for a in case["actions"][:2]} == {"ban", "hide"}  # stessa decisione
    audit = db_admin.execute(
        "select count(*) from app.admin_audit_log where action = 'moderation.decide'"
    ).fetchone()
    assert audit[0] >= 3


async def test_rimozione_blocca_la_stessa_foto(client, keys, db_admin, store, queue):
    uid, h, _ = await _person(client, keys, db_admin)
    image = photo(seed=7)
    upload_id, outcome = await _upload_and_process(client, h, store, queue, image)
    assert outcome == "ready"
    post = await _post(client, db_admin, uid, h, media=[upload_id])
    _, staff = await _staff(client, keys, db_admin)
    r = await client.post(
        "/v1/admin/reports/decide",
        json={
            "target_type": "post",
            "target_id": post,
            "decision": "remove",
            "ground": "stolen_photo",
        },
        headers=staff,
    )
    assert r.status_code == 200, r.text
    assert _status(db_admin, post) == "deleted"
    _, outcome = await _upload_and_process(client, h, store, queue, image)
    assert outcome == "rejected:blocked"
    notice = (await client.get("/v1/me/moderation", headers=h)).json()[0]
    assert notice["action"] == "remove" and notice["post_id"] is None


async def test_reclamo_deciso_da_un_altro_moderatore(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    _, first = await _staff(client, keys, db_admin)
    await client.post(
        "/v1/admin/reports/decide",
        json={
            "target_type": "post",
            "target_id": post,
            "decision": "hide",
            "sanction": "auto",
            "ground": "nudity",
        },
        headers=first,
    )
    notices = (await client.get("/v1/me/moderation", headers=author)).json()
    # Fit nascosto + avviso: il reclamo si fa sul fit e vale per entrambi.
    assert sorted(n["action"] for n in notices) == ["hide", "warn"]
    warn = next(n for n in notices if n["action"] == "warn")
    assert warn["can_appeal"] is False
    assert "Il reclamo si fa sull'avviso del fit" in warn["statement"]
    r = await client.post(
        f"/v1/me/moderation/{warn['id']}/appeal", json={"text": "no"}, headers=author
    )
    assert r.json()["code"] == "appeal.not_allowed"
    notice = next(n for n in notices if n["action"] == "hide")
    r = await client.post(
        f"/v1/me/moderation/{notice['id']}/appeal",
        json={"text": "È un costume da bagno, non c'è nudità."},
        headers=author,
    )
    assert (r.status_code, r.json()["status"]) == (201, "open")
    r = await client.post(
        f"/v1/me/moderation/{notice['id']}/appeal", json={"text": "di nuovo"}, headers=author
    )
    assert (r.status_code, r.json()["code"]) == (409, "appeal.exists")

    appeals = (await client.get("/v1/admin/appeals", headers=first)).json()
    mine = next(a for a in appeals if a["action"]["id"] == notice["id"])
    r = await client.post(
        f"/v1/admin/appeals/{mine['id']}", json={"decision": "reverse", "note": "ok"}, headers=first
    )
    assert (r.status_code, r.json()["code"]) == (409, "appeal.same_moderator")
    _, second = await _staff(client, keys, db_admin)
    r = await client.post(
        f"/v1/admin/appeals/{mine['id']}",
        json={"decision": "reverse", "note": "Costume, ammesso in Beach Party."},
        headers=second,
    )
    assert r.status_code == 200, r.text
    assert _status(db_admin, post) == "active"
    notices = (await client.get("/v1/me/moderation", headers=author)).json()
    assert notices[0]["action"] == "restore"
    hidden = next(n for n in notices if n["id"] == notice["id"])
    assert hidden["appeal"]["status"] == "reversed"
    assert hidden["appeal"]["decision_note"] == "Costume, ammesso in Beach Party."
    # Anche l'avviso è annullato: non conta più nella scala delle sanzioni.
    restores = [n for n in notices if n["action"] == "restore"]
    assert len(restores) == 2
    strikes = db_admin.execute(
        """select count(*) from app.moderation_actions m
            where m.subject_id = %s and m.action = 'warn'
              and not exists (select 1 from app.moderation_actions r
                               where r.action = 'restore' and r.target_id = m.target_id
                                 and r.created_at > m.created_at)""",
        (author_id,),
    ).fetchone()
    assert strikes == (0,)


async def test_reclami_solo_propri_e_nei_tempi(client, keys, db_admin):
    author_id, author, _ = await _person(client, keys, db_admin)
    post = await _post(client, db_admin, author_id, author)
    _, staff = await _staff(client, keys, db_admin)
    await client.post(
        "/v1/admin/reports/decide",
        json={"target_type": "post", "target_id": post, "decision": "hide", "ground": "spam"},
        headers=staff,
    )
    action_id = (await client.get("/v1/me/moderation", headers=author)).json()[0]["id"]
    _, other, _ = await _person(client, keys, db_admin)
    r = await client.post(
        f"/v1/me/moderation/{action_id}/appeal", json={"text": "x"}, headers=other
    )
    assert r.status_code == 404
    db_admin.execute(
        "update app.moderation_actions set created_at = now() - interval '200 days' where id = %s",
        (action_id,),
    )
    r = await client.post(
        f"/v1/me/moderation/{action_id}/appeal", json={"text": "tardi"}, headers=author
    )
    assert (r.status_code, r.json()["code"]) == (409, "appeal.expired")
