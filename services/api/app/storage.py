"""Archivio delle foto (compatibile S3). Bucket privato: niente è pubblico per default.

- Caricamento: POST firmato direttamente dal telefono all'archivio (l'API non fa da tramite),
  con limiti di dimensione e tipo scritti nella firma.
- Lettura: URL firmati a scadenza breve.
Le chiamate boto3 sono sincrone: girano in un thread per non bloccare l'API.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from urllib.parse import quote, urlsplit

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class PresignedUpload:
    url: str
    fields: dict[str, str]


class ObjectStore:
    def __init__(self, settings: Settings) -> None:
        self.bucket = settings.storage_bucket
        common: dict[str, Any] = {
            "region_name": settings.storage_region,
            "aws_access_key_id": settings.storage_access_key,
            "aws_secret_access_key": settings.storage_secret_key.get_secret_value(),
            "config": Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        }
        self._client = boto3.client("s3", endpoint_url=settings.storage_endpoint_url, **common)
        public = settings.storage_public_url or settings.storage_endpoint_url
        self._public = boto3.client("s3", endpoint_url=public, **common)
        # Firma veloce degli URL di lettura (vedi signed_read_url).
        self._read_signer = (
            _ReadSigner(
                public,
                settings.storage_bucket,
                settings.storage_region,
                settings.storage_access_key,
                settings.storage_secret_key.get_secret_value(),
            )
            if public
            else None
        )
        self._read_cache: dict[tuple[str, int, int], str] = {}

    # ---- firme (nessuna chiamata di rete) ----

    def presign_upload(
        self, key: str, content_type: str, max_bytes: int, expires: int
    ) -> PresignedUpload:
        post = self._public.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=expires,
        )
        return PresignedUpload(url=post["url"], fields=dict(post["fields"]))

    def signed_url(self, key: str, expires: int) -> str:
        url: str = self._public.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires
        )
        return url

    def signed_read_url(self, key: str, ttl: int, now: float | None = None) -> tuple[str, int]:
        """URL di lettura firmato "a finestre": (url, scadenza in secondi epoch).

        Tutti quelli che chiedono la stessa foto nello stesso quarto d'ora ricevono lo stesso URL
        (firmato all'inizio della finestra, vale ancora almeno 3/4 della durata). Così la firma si
        calcola una volta sola (era il 20% del tempo del feed nel test di carico, seduta 24) e
        l'app e la CDN riusano la foto già scaricata invece di riscaricarla con un URL nuovo.
        """
        window = max(ttl // 4, 1)
        moment = int(time.time() if now is None else now)
        start = moment - moment % window
        cache_key = (key, ttl, start)
        url = self._read_cache.get(cache_key)
        if url is None:
            if len(self._read_cache) > 50_000:  # vecchie finestre: si ricomincia
                self._read_cache.clear()
            url = (
                self._read_signer.sign(key, ttl, start)
                if self._read_signer
                else self.signed_url(key, ttl)
            )
            self._read_cache[cache_key] = url
        return url, start + ttl

    # ---- operazioni (rete, in un thread) ----

    async def size(self, key: str) -> int | None:
        def run() -> int | None:
            try:
                head = self._client.head_object(Bucket=self.bucket, Key=key)
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                    return None
                raise
            return int(head["ContentLength"])

        return await asyncio.to_thread(run)

    async def get(self, key: str, max_bytes: int) -> bytes:
        def run() -> bytes:
            body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
            # Mai più del limite in memoria, anche se l'oggetto è più grande.
            data: bytes = body.read(max_bytes + 1)
            body.close()
            return data

        return await asyncio.to_thread(run)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            CacheControl="private, max-age=31536000, immutable",
        )

    async def delete(self, *keys: str) -> None:
        if not keys:
            return
        await asyncio.to_thread(
            self._client.delete_objects,
            Bucket=self.bucket,
            Delete={"Objects": [{"Key": k} for k in keys], "Quiet": True},
        )

    async def ensure_bucket(self) -> None:
        """Solo sviluppo/test: crea il bucket se manca."""

        def run() -> None:
            try:
                self._client.head_bucket(Bucket=self.bucket)
            except ClientError:
                self._client.create_bucket(Bucket=self.bucket)

        await asyncio.to_thread(run)


class _ReadSigner:
    """Firma AWS SigV4 "in query" per GET, come botocore ma senza il suo giro di eventi.

    Stesso risultato di generate_presigned_url("get_object") con indirizzi "path" (verificato
    nei test), ma con una data di firma scelta da noi e circa 50 volte più veloce.
    """

    def __init__(self, endpoint: str, bucket: str, region: str, access: str, secret: str) -> None:
        parts = urlsplit(endpoint)
        default = {"https": 443, "http": 80}.get(parts.scheme)
        self._host = parts.hostname or ""
        if parts.port and parts.port != default:
            self._host += f":{parts.port}"
        self._base = f"{parts.scheme}://{self._host}"
        self._prefix = parts.path.rstrip("/") + "/" + bucket + "/"
        self._region = region
        self._access = access
        self._secret = secret.encode()
        self._keys: dict[str, bytes] = {}

    def _signing_key(self, day: str) -> bytes:
        key = self._keys.get(day)
        if key is None:
            k = hmac.digest(b"AWS4" + self._secret, day.encode(), "sha256")
            for part in (self._region, "s3", "aws4_request"):
                k = hmac.digest(k, part.encode(), "sha256")
            self._keys = {day: k}  # una al giorno basta
            key = k
        return key

    def sign(self, key: str, ttl: int, signed_at: int) -> str:
        stamp = datetime.fromtimestamp(signed_at, UTC).strftime("%Y%m%dT%H%M%SZ")
        day = stamp[:8]
        scope = f"{day}/{self._region}/s3/aws4_request"
        path = quote(self._prefix + key, safe="/~")
        params = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": f"{self._access}/{scope}",
            "X-Amz-Date": stamp,
            "X-Amz-Expires": str(ttl),
            "X-Amz-SignedHeaders": "host",
        }
        query = "&".join(
            f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(params.items())
        )
        canonical = f"GET\n{path}\n{query}\nhost:{self._host}\n\nhost\nUNSIGNED-PAYLOAD"
        to_sign = (
            f"AWS4-HMAC-SHA256\n{stamp}\n{scope}\n" + hashlib.sha256(canonical.encode()).hexdigest()
        )
        signature = hmac.new(self._signing_key(day), to_sign.encode(), "sha256").hexdigest()
        return f"{self._base}{path}?{query}&X-Amz-Signature={signature}"


_override: ObjectStore | None = None


@lru_cache
def _default_store() -> ObjectStore:
    return ObjectStore(get_settings())


def get_store() -> ObjectStore:
    return _override or _default_store()


def set_store(store: ObjectStore | None) -> None:
    """Per i test: sostituisce l'archivio."""
    global _override
    _override = store
