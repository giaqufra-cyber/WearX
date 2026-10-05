"""API pronta per le scansioni di sicurezza (seduta 22): ZAP in CI, Schemathesis in locale.

Prepara il database di test (come i test), crea due persone con un fit e uno stile, installa
chiavi di firma di prova al posto di Supabase e avvia l'API. Il token della persona finisce in
`scan-token.txt`: lo scanner lo manda come "Authorization: Bearer ..." e così raggiunge anche
gli endpoint che chiedono l'accesso. Solo per scansioni: mai in un ambiente vero.

    uv run python -m tests.scan_target [porta]
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import tests.conftest as cf  # imposta database e Redis di test (WEARX_ENV=test)


def prepare_database() -> None:
    with cf.admin_conn() as conn:
        conn.execute(f"drop database if exists {cf.TEST_DB} with (force)")
        conn.execute(f"create database {cf.TEST_DB}")
        for role in ("anon", "authenticated"):
            if not conn.execute("select 1 from pg_roles where rolname = %s", (role,)).fetchone():
                conn.execute(f"create role {role} nologin")
    cf.run_alembic("upgrade", "head")
    with cf.admin_conn() as conn:
        if not conn.execute("select 1 from pg_roles where rolname = %s", (cf.API_USER,)).fetchone():
            conn.execute(
                f"create role {cf.API_USER} login password '{cf.API_PASSWORD}' in role wearx_api"
            )


async def main(port: int) -> None:
    import httpx
    import uvicorn

    from app.auth import set_jwks
    from app.main import create_app
    from tests.authkit import KeySet, bearer
    from tests.test_accounts import onboarding_body

    prepare_database()
    # Archivio delle foto finto (moto), come nei test.
    from moto.server import ThreadedMotoServer

    s3_port = cf._free_port()
    ThreadedMotoServer(ip_address="127.0.0.1", port=s3_port, verbose=False).start()
    os.environ["WEARX_STORAGE_ENDPOINT_URL"] = f"http://127.0.0.1:{s3_port}"
    from app.config import get_settings
    from app.storage import ObjectStore, set_store

    get_settings.cache_clear()
    store = ObjectStore(get_settings())
    await store.ensure_bucket()
    set_store(store)

    keys = KeySet()
    set_jwks(keys.cache())
    app = create_app()
    people = []
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://scan"
    ) as client:
        with cf.admin_conn(cf.TEST_DB) as db:
            for nickname in ("scan.uno", "scan.due"):
                user_id = cf.create_auth_user(db)
                cf.pass_age_check(db, user_id)
                token = keys.token(user_id, lifetime=6 * 3600)
                r = await client.post(
                    "/v1/onboarding/profile",
                    json=onboarding_body(nickname),
                    headers=bearer(token),
                )
                if r.status_code != 201:
                    raise RuntimeError(f"onboarding {nickname}: {r.status_code} {r.text}")
                people.append((user_id, token))
            owner, owner_token = people[1]
            media = [str(cf.ready_upload(db, owner))]
            r = await client.post(
                "/v1/posts",
                json={"style": "old-money", "media": media, "caption": "Fit di prova"},
                headers=bearer(owner_token),
            )
            r.raise_for_status()
            post_id = r.json()["id"]
    await asyncio.to_thread(Path("scan-post.txt").write_text, post_id)
    await asyncio.to_thread(Path("scan-token.txt").write_text, people[0][1])
    print(f"API di scansione su http://127.0.0.1:{port} (token in scan-token.txt)", flush=True)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", server_header=False)
    )
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000))
