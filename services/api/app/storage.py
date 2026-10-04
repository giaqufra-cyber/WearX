"""Archivio delle foto (compatibile S3). Bucket privato: niente è pubblico per default.

- Caricamento: POST firmato direttamente dal telefono all'archivio (l'API non fa da tramite),
  con limiti di dimensione e tipo scritti nella firma.
- Lettura: URL firmati a scadenza breve.
Le chiamate boto3 sono sincrone: girano in un thread per non bloccare l'API.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

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
