"""Link ai negozi e account Business (seduta 21). Nessuna rete: risposte e DNS simulati."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.db import session_scope
from app.link_check import check_due_links, check_link, parent_domains
from app.links import go_token, parse_go_token
from app.routers import business
from app.routers.go import _with_utm
from tests.authkit import bearer
from tests.conftest import ready_upload
from tests.test_accounts import onboard

pytestmark = pytest.mark.usefixtures("store")

PUBLIC = "93.184.216.34"


def test_domini_padre_e_codici_firmati():
    assert parent_domains("a.b.shop.com") == ["a.b.shop.com", "b.shop.com", "shop.com"]
    link, post = uuid.uuid4(), uuid.uuid4()
    token = go_token(link, post, 3)
    assert parse_go_token(token) == (link, post, 3)
    tampered = token[:-2] + ("AA" if token[-2:] != "AA" else "BB")
    assert parse_go_token(tampered) is None
    assert parse_go_token("x" * 80) is None
    assert parse_go_token("%%%") is None
    assert _with_utm("https://zara.com/p?a=1") == (
        "https://zara.com/p?a=1&utm_source=wearx&utm_medium=social"
    )
    assert _with_utm("https://zara.com/p?utm_source=ig") == "https://zara.com/p?utm_source=ig"


async def _person(client, keys, db_admin, *, business=False):
    user_id, headers, profile = await onboard(client, keys, db_admin)
    if business:
        db_admin.execute(
            "update app.profiles set account_type = 'business' where id = %s", (user_id,)
        )
    return user_id, headers, profile["nickname"]


async def _post(client, db_admin, user_id, headers, urls):
    media = [str(ready_upload(db_admin, user_id))]
    items = [{"brand": f"B{i}", "name": f"Capo {i}", "url": u} for i, u in enumerate(urls)]
    r = await client.post(
        "/v1/posts",
        json={"style": "old-money", "media": media, "items": items},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _link(db_admin, url):
    row = db_admin.execute(
        """select id, url, domain, status::text as status, final_url, fail_count
             from app.links where url = %s""",
        (url,),
    ).fetchone()
    keys = ("id", "url", "domain", "status", "final_url", "fail_count")
    return dict(zip(keys, row, strict=True))


def _status(db_admin, url):
    return db_admin.execute(
        "select status::text, block_reason, final_url from app.links where url = %s", (url,)
    ).fetchone()


# Un piccolo "internet" finto: host -> (stato, intestazioni).
WEB: dict[str, tuple[int, dict[str, str]]] = {}
DNS: dict[str, list[str]] = {}


def _handler(request: httpx.Request) -> httpx.Response:
    status, headers = WEB.get(
        request.url.host + request.url.path, WEB.get(request.url.host, (200, {}))
    )
    return httpx.Response(status, headers=headers, text="ok")


async def _resolve(host: str) -> list[str]:
    if host in DNS:
        return DNS[host]
    import socket

    raise socket.gaierror("sito inesistente")


def _client():
    return httpx.AsyncClient(transport=httpx.MockTransport(_handler), follow_redirects=False)


class Threats:
    def __init__(self, bad: dict[str, str]):
        self.bad = bad

    async def threats(self, urls):
        return {u: t for u, t in self.bad.items() if u in urls}


async def test_controllo_dei_link(client, keys, db_admin):
    tag = uuid.uuid4().hex[:6]
    hosts = {
        "ok": f"ok-{tag}.com",
        "gone": f"gone-{tag}.com",
        "bots": f"bots-{tag}.com",
        "down": f"down-{tag}.com",
        "inner": f"inner-{tag}.com",
        "hop": f"hop-{tag}.com",
        "plain": f"plain-{tag}.com",
        "ghost": f"ghost-{tag}.com",
        "evil": f"evil-{tag}.com",
    }
    urls = {k: f"https://{h}/p" for k, h in hosts.items()}
    for host in hosts.values():
        DNS[host] = [PUBLIC]
    del DNS[hosts["ghost"]]
    DNS[hosts["inner"]] = ["10.0.0.7"]  # nome pubblico che porta in rete interna
    WEB[hosts["gone"]] = (404, {})
    WEB[hosts["bots"]] = (403, {})
    WEB[hosts["down"]] = (503, {})
    WEB[hosts["hop"] + "/p"] = (301, {"location": f"https://www.{hosts['ok']}/finale"})
    DNS[f"www.{hosts['ok']}"] = [PUBLIC]
    WEB[hosts["plain"] + "/p"] = (302, {"location": f"http://{hosts['plain']}/p"})

    user_id, me, _ = await _person(client, keys, db_admin)
    await _post(client, db_admin, user_id, me, list(urls.values())[:8])
    await _post(client, db_admin, user_id, me, [urls["evil"]])
    threats = {urls["evil"]: "SOCIAL_ENGINEERING"}

    async with session_scope() as session, _client() as http:
        for key in urls:
            await check_link(session, _link(db_admin, urls[key]), http, threats, _resolve)
        await session.commit()
    assert _status(db_admin, urls["ok"])[0] == "safe"
    assert _status(db_admin, urls["gone"])[0] == "broken"
    assert _status(db_admin, urls["bots"])[0] == "safe"  # molti negozi respingono i robot
    assert _status(db_admin, urls["down"])[0] == "pending"  # si riprova
    assert _status(db_admin, urls["inner"])[:2] == ("blocked", "indirizzo interno")
    hop = _status(db_admin, urls["hop"])
    assert (hop[0], hop[2]) == ("safe", f"https://www.{hosts['ok']}/finale")
    assert _status(db_admin, urls["plain"])[0] == "blocked"  # redirect verso http
    assert _status(db_admin, urls["ghost"])[0] == "broken"
    assert _status(db_admin, urls["evil"])[:2] == (
        "blocked",
        "sito pericoloso (SOCIAL_ENGINEERING)",
    )

    # Tre errori del server di fila: non raggiungibile.
    async with session_scope() as session, _client() as http:
        for _ in range(2):
            await check_link(session, _link(db_admin, urls["down"]), http, {}, _resolve)
            await session.commit()
    assert _status(db_admin, urls["down"])[0] == "broken"
    when = db_admin.execute(
        """select next_check_at > now() + interval '6 days' from app.links where url = %s""",
        (urls["ok"],),
    ).fetchone()
    assert when == (True,)

    # Il lavoro periodico: link nuovi controllati in blocco.
    fresh = f"https://ok-{tag}.com/nuovo"
    await _post(client, db_admin, user_id, me, [fresh])
    async with session_scope() as session, _client() as http:
        await check_due_links(
            session, limit=500, client=http, checker=Threats({}), resolve=_resolve
        )
    assert _status(db_admin, fresh)[0] == "safe"


async def test_redirect_firmato(client, keys, db_admin):
    tag = uuid.uuid4().hex[:6]
    user_id, me, _ = await _person(client, keys, db_admin)
    _, viewer, _ = await _person(client, keys, db_admin)
    url = f"https://shop-{tag}.com/giacca?c=nero"
    post = await _post(client, db_admin, user_id, me, [url])
    link = post["items"][0]["link"]
    assert link["url"] == url and link["go_url"].startswith("http://localhost:8000/r/")
    assert link["verified"] is False
    path = link["go_url"].removeprefix("http://localhost:8000")

    r = await client.get(path)
    assert (r.status_code, r.headers["location"]) == (302, url)
    assert r.headers["referrer-policy"] == "no-referrer"
    clicks = db_admin.execute(
        "select l.clicks, s.shop_clicks from app.links l, app.post_stats s "
        "where l.url = %s and s.post_id = %s",
        (url, post["id"]),
    ).fetchone()
    assert clicks == (1, 1)

    r = await client.get(path[:-3] + "abc")
    assert r.status_code == 404 and "Link non valido" in r.text

    # Il dominio viene bloccato dallo staff: il link si ferma al clic.
    staff_id, _, _ = await _person(client, keys, db_admin)
    db_admin.execute("insert into app.staff (user_id, role) values (%s, 'moderator')", (staff_id,))
    staff = bearer(keys.token(staff_id, aal="aal2"))
    r = await client.post(
        "/v1/admin/blocked-domains",
        json={"domain": f"https://www.shop-{tag}.com/", "reason": "truffa segnalata"},
        headers=staff,
    )
    assert (r.status_code, r.json()["domain"], r.json()["links"]) == (201, f"shop-{tag}.com", 1)
    r = await client.get(path)
    assert r.status_code == 451 and "Abbiamo fermato questo link" in r.text
    item = (await client.get(f"/v1/posts/{post['id']}", headers=viewer)).json()["items"][0]
    assert (item["link"]["status"], item["link"]["url"], item["link"]["go_url"]) == (
        "blocked",
        None,
        None,
    )
    listed = (await client.get("/v1/admin/blocked-domains", headers=staff)).json()
    assert any(d["domain"] == f"shop-{tag}.com" for d in listed)
    _, user, _ = await _person(client, keys, db_admin)
    assert (await client.get("/v1/admin/blocked-domains", headers=user)).status_code == 404

    r = await client.delete(f"/v1/admin/blocked-domains/shop-{tag}.com", headers=staff)
    assert r.status_code == 204
    assert _status(db_admin, url)[0] == "pending"  # da ricontrollare


async def test_negozio_verificato(client, keys, db_admin, monkeypatch):
    tag = uuid.uuid4().hex[:6]
    domain = f"brand-{tag}.com"
    brand_id, brand, brand_nick = await _person(client, keys, db_admin, business=True)
    _, private, _ = await _person(client, keys, db_admin)
    _, viewer, _ = await _person(client, keys, db_admin)

    r = await client.post("/v1/me/shop-domains", json={"domain": domain}, headers=private)
    assert (r.status_code, r.json()["code"]) == (403, "business.required")
    r = await client.post(
        "/v1/me/shop-domains", json={"domain": f"https://www.{domain}/it/"}, headers=brand
    )
    assert r.status_code == 201, r.text
    added = r.json()
    assert (added["domain"], added["verified"]) == (domain, False)
    assert added["file_url"] == f"https://{domain}/.well-known/wearx-verify.txt"
    token = added["file_content"]
    assert token.startswith("wearx-verify=")

    served: dict[str, str] = {}

    def site(request: httpx.Request) -> httpx.Response:
        body = served.get(request.url.host + request.url.path)
        return httpx.Response(200, text=body) if body else httpx.Response(404)

    monkeypatch.setattr(
        business, "client_factory", lambda: httpx.AsyncClient(transport=httpx.MockTransport(site))
    )

    async def resolve(host):
        return [PUBLIC]

    monkeypatch.setattr(business, "resolver", resolve)
    r = await client.post(f"/v1/me/shop-domains/{domain}/verify", headers=brand)
    assert (r.status_code, r.json()["code"]) == (422, "shop.verify_failed")
    served[f"www.{domain}/.well-known/wearx-verify.txt"] = f"{token}\n"
    r = await client.post(f"/v1/me/shop-domains/{domain}/verify", headers=brand)
    assert (r.status_code, r.json()["verified"]) == (200, True)

    post = await _post(
        client, db_admin, brand_id, brand, [f"https://shop.{domain}/x", "https://altro.com/y"]
    )
    items = (await client.get(f"/v1/posts/{post['id']}", headers=viewer)).json()["items"]
    assert [i["link"]["verified"] for i in items] == [True, False]
    profile = (await client.get(f"/v1/users/{brand_nick}", headers=viewer)).json()
    assert profile["verified_domains"] == [domain]
    # Il redirect di un sito verificato dice al negozio che il clic arriva da WearX.
    go = items[0]["link"]["go_url"].removeprefix("http://localhost:8000")
    location = (await client.get(go)).headers["location"]
    assert location.endswith("utm_source=wearx&utm_medium=social")

    # Un altro Business non può prendersi lo stesso sito.
    _, rival, _ = await _person(client, keys, db_admin, business=True)
    r = await client.post("/v1/me/shop-domains", json={"domain": domain}, headers=rival)
    assert (r.status_code, r.json()["code"]) == (409, "shop.taken")
    for n in range(5):
        await client.post("/v1/me/shop-domains", json={"domain": f"s{n}-{tag}.com"}, headers=rival)
    r = await client.post("/v1/me/shop-domains", json={"domain": f"s9-{tag}.com"}, headers=rival)
    assert r.json()["code"] == "shop.limit"

    # Tornando privato, il badge sparisce.
    r = await client.patch("/v1/me", json={"account_type": "private"}, headers=brand)
    assert r.status_code == 200
    items = (await client.get(f"/v1/posts/{post['id']}", headers=brand)).json()["items"]
    assert items[0]["link"]["verified"] is False
    assert (await client.get("/v1/me/shop-domains", headers=brand)).json() == []
