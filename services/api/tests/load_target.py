"""API con tanti dati di prova per il test di carico (seduta 24).

Prepara un database nuovo con PERSONE persone, ognuna con qualche fit e migliaia di voti già dati,
pubblica medie e classifiche come farebbero i lavori orari, poi avvia l'API come in produzione:
un solo processo (come un'istanza di Cloud Run). I token delle persone finiscono in
`load-users.json` per k6.

    uv run python -m tests.load_target [persone]
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import sys
import uuid
from pathlib import Path

import tests.conftest as cf

STYLES = ["old-money", "streetwear", "elegant", "minimal", "jappo", "gala"]


async def main(people: int) -> None:
    import httpx
    import uvicorn
    from moto.server import ThreadedMotoServer

    from tests.scan_target import prepare_database

    prepare_database()
    s3_port = cf._free_port()
    ThreadedMotoServer(ip_address="127.0.0.1", port=s3_port, verbose=False).start()
    os.environ["WEARX_STORAGE_ENDPOINT_URL"] = f"http://127.0.0.1:{s3_port}"

    from app.auth import set_jwks
    from app.config import get_settings
    from app.db import session_scope
    from app.feed import refresh_all
    from app.main import create_app
    from app.storage import ObjectStore, set_store
    from app.votes import publish_stats
    from tests.authkit import KeySet, bearer
    from tests.test_accounts import onboarding_body

    get_settings.cache_clear()
    store = ObjectStore(get_settings())
    await store.ensure_bucket()
    set_store(store)
    keys = KeySet()
    set_jwks(keys.cache())
    app = create_app()
    rng = random.Random(24)  # noqa: S311 - dati di prova, non crittografia
    users: list[dict[str, str]] = []
    posts: list[str] = []

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://load", timeout=30
    ) as client:
        for n in range(people):
            with cf.admin_conn(cf.TEST_DB) as db:
                user_id = cf.create_auth_user(db)
                cf.pass_age_check(db, user_id)
            token = keys.token(user_id, lifetime=6 * 3600)
            styles = rng.sample(STYLES, 3)
            nickname = f"carico.{n:04d}"
            r = await client.post(
                "/v1/onboarding/profile",
                json=onboarding_body(nickname, styles=styles),
                headers=bearer(token),
            )
            r.raise_for_status()
            if n % 4 == 0:  # un quarto Business (profilo pubblico)
                r = await client.patch(
                    "/v1/me", json={"account_type": "business"}, headers=bearer(token)
                )
                r.raise_for_status()
            with cf.admin_conn(cf.TEST_DB) as db:
                db.execute(
                    "update app.profiles set created_at = now() - interval '60 days' where id = %s",
                    (user_id,),
                )
                uploads = [cf.ready_upload(db, user_id) for _ in range(rng.randint(1, 4))]
            for upload in uploads:
                r = await client.post(
                    "/v1/posts",
                    json={
                        "style": rng.choice(styles),
                        "media": [str(upload)],
                        "caption": f"Fit {rng.randint(1, 999)}",
                        "items": [{"brand": "Marca", "name": "Capo", "price_cents": 4900}],
                    },
                    headers=bearer(token),
                )
                r.raise_for_status()
                posts.append(r.json()["id"])
            users.append({"token": token, "nickname": nickname, "id": str(user_id)})

    # Voti già dati (pseudonimi casuali): circa 25 per fit.
    with cf.admin_conn(cf.TEST_DB) as db:
        rows = []
        for post in posts:
            for _ in range(rng.randint(5, 45)):
                key = hashlib.sha256(uuid.uuid4().bytes).digest()
                rows.append((post, key, rng.randint(30, 100)))
        with db.cursor() as cur:
            cur.executemany(
                "insert into app.votes (post_id, voter_key, score, weight, base_weight)"
                " values (%s, %s, %s, 1, 1)",
                rows,
            )
        db.execute(
            """update app.post_stats st set vote_count = v.c, vote_sum = v.s,
                      vote_wsum = v.s, vote_wcount = v.c, unpublished_writes = 3
                 from (select post_id, count(*) c, sum(score) s from app.votes group by post_id) v
                where st.post_id = v.post_id"""
        )
    async with session_scope() as session:
        await publish_stats(session)
    async with session_scope() as session:
        await refresh_all(session)

    await asyncio.to_thread(
        Path("load-users.json").write_text, json.dumps({"users": users, "posts": posts})
    )
    print(f"Carico pronto: {len(users)} persone, {len(posts)} fit, {len(rows)} voti", flush=True)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="warning", access_log=False)
    )
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 200))
