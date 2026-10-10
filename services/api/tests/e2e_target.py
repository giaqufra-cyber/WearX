"""Ambiente completo per i test end-to-end (seduta 24): tutto WearX su questo computer.

- Auth finta compatibile con Supabase su http://localhost:54321 (registrazione con codice,
  accesso con password, rinnovo, uscita, utente, JWKS). Il codice di conferma è sempre 123456.
- API vera su http://localhost:8000 (database di test nuovo, Redis di test, archivio finto).
- Worker in background nello stesso processo (elaborazione delle foto).
- App web esportata (apps/mobile/dist-e2e) su http://localhost:8081.
- Persone e fit di prova; comandi di servizio per i test su /__e2e/* (porta 54321).

Solo per i test: niente di tutto questo esiste in un ambiente vero.

    uv run python -m tests.e2e_target
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import secrets
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import uvicorn

# Indirizzo con cui il telefono vede questo computer: "localhost" per il browser, "10.0.2.2" per
# l'emulatore Android (seduta 25, Maestro in CI). Vale per l'API e per le foto; l'accesso finto
# di Supabase resta "localhost" come emittente dei token (l'API lo confronta così).
PUBLIC_HOST = os.environ.get("E2E_PUBLIC_HOST", "localhost")
os.environ.setdefault("WEARX_SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("WEARX_PUBLIC_API_URL", f"http://{PUBLIC_HOST}:8000")
os.environ.setdefault(
    "WEARX_ADMIN_ORIGINS", json.dumps(["http://localhost:8081", "http://localhost:3000"])
)

import tests.conftest as cf  # noqa: E402 - dopo le variabili d'ambiente qui sopra

AUTH_PORT, API_PORT, APP_PORT = 54321, 8000, 8081
OTP = "123456"
ISSUER = f"http://localhost:{AUTH_PORT}/auth/v1"
APP_DIST = Path(__file__).resolve().parents[3] / "apps" / "mobile" / "dist-e2e"

# Persone di prova (password note ai test).
PEOPLE = [
    {"nickname": "giulia.e2e", "email": "giulia@e2e.test", "password": "Fit-di-prova-2026!"},
    {"nickname": "marco.e2e", "email": "marco@e2e.test", "password": "Fit-di-prova-2026!"},
    {"nickname": "anna.e2e", "email": "anna@e2e.test", "password": "Fit-di-prova-2026!"},
]


# ---------- Auth finta (forma delle risposte di Supabase Auth / GoTrue) ----------


class FakeAuth:
    def __init__(self) -> None:
        from cryptography.hazmat.primitives.asymmetric import ec

        self.key = ec.generate_private_key(ec.SECP256R1())
        self.users: dict[str, dict[str, Any]] = {}  # email -> utente
        self.refresh: dict[str, str] = {}  # refresh token -> email

    def jwks(self) -> dict[str, Any]:
        import jwt

        jwk = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self.key.public_key()))
        jwk.update(kid="e2e", alg="ES256", use="sig")
        return {"keys": [jwk]}

    def user_json(self, user: dict[str, Any]) -> dict[str, Any]:
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        confirmed = now if user["confirmed"] else None
        return {
            "id": user["id"],
            "aud": "authenticated",
            "role": "authenticated",
            "email": user["email"],
            "phone": "",
            "email_confirmed_at": confirmed,
            "confirmed_at": confirmed,
            "last_sign_in_at": now,
            "app_metadata": {"provider": "email", "providers": ["email"]},
            "user_metadata": user.get("metadata", {}),
            "identities": [],
            "created_at": now,
            "updated_at": now,
            "is_anonymous": False,
        }

    def session(self, user: dict[str, Any], aal: str = "aal1") -> dict[str, Any]:
        import jwt

        now = int(time.time())
        token = jwt.encode(
            {
                "sub": user["id"],
                "iss": ISSUER,
                "aud": "authenticated",
                "role": "authenticated",
                "email": user["email"],
                "iat": now,
                "exp": now + 3600,
                "session_id": str(uuid.uuid4()),
                "aal": aal,
                "is_anonymous": False,
            },
            self.key,
            algorithm="ES256",
            headers={"kid": "e2e"},
        )
        refresh = secrets.token_urlsafe(24)
        self.refresh[refresh] = user["email"]
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": 3600,
            "expires_at": now + 3600,
            "refresh_token": refresh,
            "user": self.user_json(user),
        }

    def create(self, email: str, password: str, metadata: dict[str, Any] | None = None) -> dict:
        with cf.admin_conn(cf.TEST_DB) as db:
            user_id = cf.create_auth_user(db)
        user = {
            "id": str(user_id),
            "email": email,
            "password": password,
            "confirmed": False,
            "metadata": metadata or {},
        }
        self.users[email] = user
        return user


def auth_app(auth: FakeAuth, control: dict[str, Any]) -> Any:
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse, Response
    from starlette.routing import Route

    def error(status: int, code: str, msg: str) -> JSONResponse:
        return JSONResponse({"code": status, "error_code": code, "msg": msg}, status_code=status)

    def bearer_user(request: Request) -> dict[str, Any] | None:
        import jwt

        header = request.headers.get("authorization", "")
        try:
            claims = jwt.decode(
                header.removeprefix("Bearer "),
                auth.key.public_key(),
                algorithms=["ES256"],
                audience="authenticated",
            )
        except jwt.PyJWTError:
            return None
        return next((u for u in auth.users.values() if u["id"] == claims["sub"]), None)

    async def jwks(_: Request) -> Response:
        return JSONResponse(auth.jwks())

    async def signup(request: Request) -> Response:
        body = await request.json()
        email = str(body.get("email", "")).lower()
        if email in auth.users and auth.users[email]["confirmed"]:
            # Come Supabase: nessun indizio che l'email esista già.
            return JSONResponse(auth.user_json(auth.users[email]) | {"identities": []})
        user = auth.create(email, str(body.get("password", "")), body.get("data") or {})
        return JSONResponse(auth.user_json(user))

    async def verify(request: Request) -> Response:
        body = await request.json()
        user = auth.users.get(str(body.get("email", "")).lower())
        if user is None or body.get("token") != OTP:
            return error(403, "otp_expired", "Token has expired or is invalid")
        user["confirmed"] = True
        return JSONResponse(auth.session(user))

    async def token(request: Request) -> Response:
        body = await request.json()
        grant = request.query_params.get("grant_type")
        if grant == "password":
            user = auth.users.get(str(body.get("email", "")).lower())
            if user is None or user["password"] != body.get("password"):
                return error(400, "invalid_credentials", "Invalid login credentials")
            if not user["confirmed"]:
                return error(400, "email_not_confirmed", "Email not confirmed")
            return JSONResponse(auth.session(user))
        if grant == "refresh_token":
            email = auth.refresh.pop(str(body.get("refresh_token")), None)
            if email is None:
                return error(400, "refresh_token_not_found", "Invalid Refresh Token")
            return JSONResponse(auth.session(auth.users[email]))
        return error(400, "unsupported_grant_type", "unsupported")

    async def user_endpoint(request: Request) -> Response:
        user = bearer_user(request)
        if user is None:
            return error(401, "bad_jwt", "invalid JWT")
        if request.method == "PUT":
            body = await request.json()
            if "password" in body:
                user["password"] = body["password"]
        return JSONResponse(auth.user_json(user))

    async def ok(_: Request) -> Response:
        return JSONResponse({})

    async def logout(_: Request) -> Response:
        return Response(status_code=204)

    # ---- comandi per i test ----
    async def publish(_: Request) -> Response:
        from app.db import session_scope
        from app.votes import publish_stats

        async with session_scope() as session:
            count = await publish_stats(session)
        return JSONResponse({"published": count})

    async def state(_: Request) -> Response:
        return JSONResponse(control)

    async def staff_token(_: Request) -> Response:
        staff = auth.users[PEOPLE[2]["email"]]
        return JSONResponse({"access_token": auth.session(staff, aal="aal2")["access_token"]})

    routes = [
        Route("/auth/v1/.well-known/jwks.json", jwks),
        Route("/auth/v1/signup", signup, methods=["POST"]),
        Route("/auth/v1/verify", verify, methods=["POST"]),
        Route("/auth/v1/token", token, methods=["POST"]),
        Route("/auth/v1/user", user_endpoint, methods=["GET", "PUT"]),
        Route("/auth/v1/logout", logout, methods=["POST"]),
        Route("/auth/v1/recover", ok, methods=["POST"]),
        Route("/auth/v1/resend", ok, methods=["POST"]),
        Route("/__e2e/publish", publish, methods=["POST"]),
        Route("/__e2e/state", state),
        Route("/__e2e/staff-token", staff_token, methods=["POST"]),
    ]
    middleware = [
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["*"],
        )
    ]
    return Starlette(routes=routes, middleware=middleware)


def static_app(dist: Path = APP_DIST) -> Any:
    """L'app web esportata, con ritorno a index.html per gli indirizzi dell'app (SPA)."""
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import FileResponse, Response
    from starlette.routing import Route

    async def serve(request: Request) -> Response:
        rel = request.path_params.get("path", "")
        target = (dist / rel).resolve()
        if dist in target.parents and target.is_file():
            return FileResponse(target)
        html = dist / (rel.rstrip("/") + ".html")
        if rel and html.is_file():
            return FileResponse(html)
        return FileResponse(dist / "index.html")

    return Starlette(routes=[Route("/", serve), Route("/{path:path}", serve)])


# ---------- Avvio ----------


async def put_photo(store: Any, upload_id: uuid.UUID, color: tuple[int, int, int]) -> None:
    from PIL import Image

    from app.media.keys import variant_key

    for width in (320, 640, 1080):
        image = Image.new("RGB", (width, round(width * 1.25)), color)
        buf = io.BytesIO()
        image.save(buf, "WEBP", quality=70)
        await store.put(variant_key(upload_id, width), buf.getvalue(), "image/webp")


async def seed(auth: FakeAuth, client: Any, store: Any) -> dict[str, Any]:
    from tests.test_accounts import onboarding_body

    control: dict[str, Any] = {"people": {}}
    for person in PEOPLE:
        user = auth.create(person["email"], person["password"])
        user["confirmed"] = True
        with cf.admin_conn(cf.TEST_DB) as db:
            cf.pass_age_check(db, uuid.UUID(user["id"]))
            db.execute(
                "update app.profiles set created_at = now() - interval '30 days' where id = %s",
                (user["id"],),
            )
        token = auth.session(user)["access_token"]
        r = await client.post(
            "/v1/onboarding/profile",
            json=onboarding_body(person["nickname"], styles=["old-money", "streetwear"]),
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code != 201:
            raise RuntimeError(f"onboarding {person['nickname']}: {r.status_code} {r.text}")
        with cf.admin_conn(cf.TEST_DB) as db:
            db.execute(
                "update app.profiles set created_at = now() - interval '30 days' where id = %s",
                (user["id"],),
            )
        control["people"][person["nickname"]] = {"id": user["id"], **person}

    giulia = auth.users[PEOPLE[0]["email"]]
    giulia_token = auth.session(giulia)["access_token"]
    posts = []
    palette = [(122, 98, 84), (58, 72, 96), (140, 120, 90)]
    for i, (caption, color) in enumerate(
        zip(
            ("Capodanno a Trento", "Vernissage in Brera", "Domenica al mercato"),
            palette,
            strict=True,
        )
    ):
        with cf.admin_conn(cf.TEST_DB) as db:
            upload_id = cf.ready_upload(db, uuid.UUID(giulia["id"]))
        await put_photo(store, upload_id, color)
        r = await client.post(
            "/v1/posts",
            json={
                "style": "old-money",
                "media": [str(upload_id)],
                "caption": caption,
                "items": [{"brand": "Atelier", "name": f"Cappotto {i + 1}", "price_cents": 18900}],
            },
            headers={"Authorization": f"Bearer {giulia_token}"},
        )
        r.raise_for_status()
        posts.append(r.json()["id"])
    control["posts"] = posts
    with cf.admin_conn(cf.TEST_DB) as db:
        db.execute(
            "insert into app.staff (user_id, role) values (%s, 'admin')",
            (control["people"]["anna.e2e"]["id"],),
        )
    return control


@dataclass
class Booted:
    """Ambiente acceso: accesso finto in ascolto, database con i dati di prova, worker avviato."""

    api: Any
    auth_asgi: Any
    auth: FakeAuth
    control: dict[str, Any]
    store: Any
    settings: Any
    s3_port: int
    servers: list[Any]
    tasks: list[asyncio.Task[Any]]


SeedFn = Callable[[FakeAuth, Any, Any], Awaitable[dict[str, Any]]]


async def boot(
    storage_public_url: str | None = None,
    seed_fn: SeedFn | None = None,
    worker_functions: list[Any] | None = None,
) -> Booted:
    """Database nuovo, archivio finto, accesso finto (porta 54321), dati di prova, worker.

    Non avvia l'API su una porta: lo fa chi chiama (test end-to-end o demo, tests/demo_target.py).
    """
    from arq.connections import RedisSettings
    from arq.worker import Worker
    from moto.server import ThreadedMotoServer

    from tests.scan_target import prepare_database

    prepare_database()

    s3_port = cf._free_port()
    ThreadedMotoServer(ip_address="127.0.0.1", port=s3_port, verbose=False).start()
    os.environ["WEARX_STORAGE_ENDPOINT_URL"] = f"http://localhost:{s3_port}"
    os.environ["WEARX_STORAGE_PUBLIC_URL"] = storage_public_url or f"http://{PUBLIC_HOST}:{s3_port}"

    from app.config import get_settings
    from app.main import create_app
    from app.media.jobs import process_upload
    from app.storage import ObjectStore, set_store

    get_settings.cache_clear()
    settings = get_settings()
    store = ObjectStore(settings)
    await store.ensure_bucket()
    set_store(store)
    # Il browser carica le foto direttamente nell'archivio: serve CORS sul bucket.
    import boto3

    boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key.get_secret_value(),
        region_name=settings.storage_region,
    ).put_bucket_cors(
        Bucket=settings.storage_bucket,
        CORSConfiguration={
            "CORSRules": [
                {
                    "AllowedOrigins": ["*"],
                    "AllowedMethods": ["GET", "PUT", "HEAD"],
                    "AllowedHeaders": ["*"],
                    "ExposeHeaders": ["ETag"],
                }
            ]
        },
    )

    auth = FakeAuth()
    control: dict[str, Any] = {}
    auth_asgi = auth_app(auth, control)
    servers = [
        uvicorn.Server(uvicorn.Config(auth_asgi, port=AUTH_PORT, log_level="warning")),
    ]
    tasks = [asyncio.create_task(servers[0].serve())]
    while not servers[0].started:  # noqa: ASYNC110 - attesa dell'avvio, solo test
        await asyncio.sleep(0.05)

    api = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=api), base_url="http://e2e"
    ) as c:
        control.update(await (seed_fn or seed)(auth, c, store))

    worker = Worker(
        functions=worker_functions or [process_upload],
        redis_settings=RedisSettings.from_dsn(settings.redis_url),
        handle_signals=False,
        poll_delay=0.2,
    )
    tasks.append(asyncio.create_task(worker.async_run()))
    return Booted(api, auth_asgi, auth, control, store, settings, s3_port, servers, tasks)


async def serve(app: Any, port: int, booted: Booted) -> uvicorn.Server:
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", server_header=False)
    )
    booted.servers.append(server)
    booted.tasks.append(asyncio.create_task(server.serve()))
    return server


async def main() -> None:
    if not (APP_DIST / "index.html").is_file():
        sys.exit(f"Manca l'app web esportata in {APP_DIST} (vedi e2e/README.md)")
    booted = await boot()
    await serve(booted.api, API_PORT, booted)
    await serve(static_app(), APP_PORT, booted)
    while not all(s.started for s in booted.servers):  # noqa: ASYNC110 - attesa dell'avvio
        await asyncio.sleep(0.05)
    await asyncio.to_thread(Path("e2e-ready.json").write_text, json.dumps(booted.control))
    print("E2E pronto: app http://localhost:8081  API http://localhost:8000", flush=True)
    await asyncio.gather(*booted.tasks)


if __name__ == "__main__":
    asyncio.run(main())
