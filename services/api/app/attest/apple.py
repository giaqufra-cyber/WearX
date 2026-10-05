"""Verifica di App Attest (iOS), secondo la documentazione Apple "Validating apps that connect
to your server".

Attestazione (una volta per chiave, alla prima apertura dell'app sul telefono):
1. x5c: certificato della chiave + intermedio, firmati fino alla radice Apple App Attestation;
2. nonce = SHA256(authData || SHA256(sfida)) dentro l'estensione 1.2.840.113635.100.8.2;
3. key_id = SHA256(chiave pubblica del certificato);
4. authData: rpIdHash = SHA256("<TeamID>.<bundle id>"), contatore 0, aaguid di produzione
   ("appattest" + zeri) o di sviluppo ("appattestdevelop"), credentialId = key_id.
Asserzione (a ogni nuovo accesso): firma ECDSA del nonce con la chiave salvata, rpIdHash
uguale, contatore che cresce (una firma vecchia non si può riusare).
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import cbor2
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

NONCE_OID = x509.ObjectIdentifier("1.2.840.113635.100.8.2")
AAGUID_PRODUCTION = b"appattest" + b"\x00" * 7
AAGUID_DEVELOPMENT = b"appattestdevelop"
ROOT_PEM = Path(__file__).with_name("apple_app_attest_root.pem")


class AttestationError(Exception):
    """Prova di integrità non valida (il motivo resta nei log, mai all'app)."""


@dataclass(frozen=True, slots=True)
class AttestedKey:
    key_id: str
    public_key: bytes  # SubjectPublicKeyInfo DER
    environment: str  # "production" | "development"


@dataclass(frozen=True, slots=True)
class AuthData:
    rp_id_hash: bytes
    counter: int
    aaguid: bytes
    credential_id: bytes


@lru_cache
def apple_root() -> x509.Certificate:
    return x509.load_pem_x509_certificate(ROOT_PEM.read_bytes())


def app_id(team_id: str, bundle_id: str) -> str:
    return f"{team_id}.{bundle_id}"


def _b64(value: str) -> bytes:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), validate=False)
    except ValueError as exc:
        raise AttestationError("base64 non valido") from exc


def _cbor(raw: bytes) -> dict[str, Any]:
    try:
        decoded = cbor2.loads(raw)
    except (cbor2.CBORDecodeError, ValueError, TypeError) as exc:
        raise AttestationError("CBOR non valido") from exc
    if not isinstance(decoded, dict):
        raise AttestationError("CBOR non è una mappa")
    return decoded


def parse_auth_data(data: bytes, *, attested: bool) -> AuthData:
    if len(data) < 37:
        raise AttestationError("authData troppo corto")
    rp_id_hash, counter = data[:32], int.from_bytes(data[33:37], "big")
    if not attested:
        return AuthData(rp_id_hash, counter, b"", b"")
    if len(data) < 55:
        raise AttestationError("authData senza credenziale")
    aaguid = data[37:53]
    length = int.from_bytes(data[53:55], "big")
    credential_id = data[55 : 55 + length]
    if len(credential_id) != length:
        raise AttestationError("credentialId troncato")
    return AuthData(rp_id_hash, counter, aaguid, credential_id)


def _verify_signed_by(cert: x509.Certificate, issuer: x509.Certificate, now: datetime) -> None:
    if not (cert.not_valid_before_utc <= now <= cert.not_valid_after_utc):
        raise AttestationError("certificato scaduto o non ancora valido")
    if cert.issuer != issuer.subject:
        raise AttestationError("catena dei certificati non coerente")
    key = issuer.public_key()
    if not isinstance(key, ec.EllipticCurvePublicKey) or cert.signature_hash_algorithm is None:
        raise AttestationError("algoritmo di firma inatteso")
    try:
        key.verify(
            cert.signature, cert.tbs_certificate_bytes, ec.ECDSA(cert.signature_hash_algorithm)
        )
    except InvalidSignature as exc:
        raise AttestationError("firma della catena non valida") from exc


def _nonce_from_extension(cert: x509.Certificate) -> bytes:
    try:
        ext = cert.extensions.get_extension_for_oid(NONCE_OID).value
    except x509.ExtensionNotFound as exc:
        raise AttestationError("manca il nonce nel certificato") from exc
    raw = ext.value if isinstance(ext, x509.UnrecognizedExtension) else b""
    # SEQUENCE { [1] EXPLICIT { OCTET STRING (32 byte) } }: il nonce sono gli ultimi 32 byte,
    # preceduti dall'intestazione dell'OCTET STRING (04 20).
    if len(raw) < 34 or raw[-34:-32] != b"\x04\x20":
        raise AttestationError("estensione del nonce non valida")
    return raw[-32:]


def verify_attestation(
    *,
    attestation_b64: str,
    challenge: str,
    key_id: str,
    team_id: str,
    bundle_id: str,
    allow_development: bool,
    root: x509.Certificate | None = None,
    now: datetime | None = None,
) -> AttestedKey:
    current = now or datetime.now(UTC)
    obj = _cbor(_b64(attestation_b64))
    if obj.get("fmt") != "apple-appattest":
        raise AttestationError("formato inatteso")
    statement = obj.get("attStmt") or {}
    chain = statement.get("x5c") or []
    auth_raw = obj.get("authData")
    if len(chain) < 2 or not isinstance(auth_raw, bytes):
        raise AttestationError("attestazione incompleta")
    try:
        leaf = x509.load_der_x509_certificate(chain[0])
        intermediate = x509.load_der_x509_certificate(chain[1])
    except (ValueError, TypeError) as exc:
        raise AttestationError("certificati non leggibili") from exc
    anchor = root or apple_root()
    _verify_signed_by(intermediate, anchor, current)
    _verify_signed_by(leaf, intermediate, current)

    client_hash = hashlib.sha256(challenge.encode()).digest()
    nonce = hashlib.sha256(auth_raw + client_hash).digest()
    if _nonce_from_extension(leaf) != nonce:
        raise AttestationError("nonce diverso dalla sfida")

    public_key = leaf.public_key()
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise AttestationError("chiave non EC")
    point = public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    key_bytes = _b64(key_id)
    if hashlib.sha256(point).digest() != key_bytes:
        raise AttestationError("key_id non corrisponde alla chiave")

    auth = parse_auth_data(auth_raw, attested=True)
    if auth.rp_id_hash != hashlib.sha256(app_id(team_id, bundle_id).encode()).digest():
        raise AttestationError("app diversa (rpIdHash)")
    if auth.counter != 0:
        raise AttestationError("contatore iniziale non zero")
    if auth.aaguid == AAGUID_PRODUCTION:
        environment = "production"
    elif auth.aaguid == AAGUID_DEVELOPMENT and allow_development:
        environment = "development"
    else:
        raise AttestationError("ambiente App Attest non ammesso")
    if auth.credential_id != key_bytes:
        raise AttestationError("credentialId diverso da key_id")
    spki = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return AttestedKey(key_id=key_id, public_key=spki, environment=environment)


def verify_assertion(
    *,
    assertion_b64: str,
    challenge: str,
    public_key: bytes,
    previous_counter: int,
    team_id: str,
    bundle_id: str,
) -> int:
    """Restituisce il nuovo contatore della chiave."""
    obj = _cbor(_b64(assertion_b64))
    signature, auth_raw = obj.get("signature"), obj.get("authenticatorData")
    if not isinstance(signature, bytes) or not isinstance(auth_raw, bytes):
        raise AttestationError("asserzione incompleta")
    key = serialization.load_der_public_key(public_key)
    if not isinstance(key, ec.EllipticCurvePublicKey):
        raise AttestationError("chiave salvata non EC")
    nonce = hashlib.sha256(auth_raw + hashlib.sha256(challenge.encode()).digest()).digest()
    try:
        key.verify(signature, nonce, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise AttestationError("firma dell'asserzione non valida") from exc
    auth = parse_auth_data(auth_raw, attested=False)
    if auth.rp_id_hash != hashlib.sha256(app_id(team_id, bundle_id).encode()).digest():
        raise AttestationError("app diversa (rpIdHash)")
    if auth.counter <= previous_counter:
        raise AttestationError("contatore non crescente (asserzione riusata)")
    return auth.counter
