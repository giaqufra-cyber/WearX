"""Nomi degli oggetti nell'archivio."""

import uuid


def quarantine_key(upload_id: uuid.UUID) -> str:
    return f"quarantine/{upload_id}"


def variant_key(upload_id: uuid.UUID, width: int) -> str:
    return f"media/{upload_id}/{width}.webp"
