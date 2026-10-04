"""Elaborazione di una foto caricata. Funzione pura e sincrona (CPU): il worker la esegue
in un thread. Non scrive nulla: restituisce le varianti pronte o il motivo del rifiuto.

Sicurezza e privacy:
- si legge prima solo l'intestazione: immagini enormi ("decompression bomb") rifiutate
  senza decodificarle;
- si accettano solo JPEG, PNG e WebP, riconosciuti dal contenuto e non dal nome;
- le varianti sono ricodificate da zero: EXIF (GPS, modello del telefono, data), XMP e
  profili colore NON passano. L'orientamento EXIF viene applicato prima di buttarlo.
"""

from __future__ import annotations

import hashlib
import io
import warnings
from dataclasses import dataclass
from typing import Literal

from PIL import Image, ImageCms, ImageOps, UnidentifiedImageError

from app.media.blurhash import encode as blurhash_encode

ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})
MAX_PIXELS = 40_000_000  # 40 megapixel: più di qualsiasi foto da telefono
MIN_SIDE = 320
MIN_ASPECT, MAX_ASPECT = 0.5, 2.0  # da 1:2 (verticale) a 2:1 (orizzontale)
VARIANT_WIDTHS = (1080, 640, 320)
WEBP_QUALITY = 82

# Limite anche per Pillow: oltre il doppio solleva un errore prima di decodificare.
Image.MAX_IMAGE_PIXELS = MAX_PIXELS

RejectReason = Literal[
    "not_an_image", "unsupported_format", "too_many_pixels", "too_small", "bad_aspect_ratio"
]


@dataclass(frozen=True, slots=True)
class Processed:
    width: int
    height: int
    blurhash: str
    sha256: bytes
    phash: int
    # larghezza -> WebP
    variants: dict[int, bytes]


@dataclass(frozen=True, slots=True)
class Rejected:
    reason: RejectReason


def _to_srgb(image: Image.Image) -> Image.Image:
    icc = image.info.get("icc_profile")
    if not icc:
        return image
    try:
        source = ImageCms.ImageCmsProfile(io.BytesIO(icc))
        target = ImageCms.createProfile("sRGB")
        mode = "RGBA" if image.mode == "RGBA" else "RGB"
        converted = ImageCms.profileToProfile(image, source, target, outputMode=mode)
        return converted if converted is not None else image
    except (ImageCms.PyCMSError, OSError, ValueError):
        return image  # profilo illeggibile: si tiene l'immagine com'è


def _normalize_mode(image: Image.Image) -> Image.Image:
    if image.mode in ("RGB", "RGBA"):
        return image
    has_alpha = image.mode in ("LA", "PA") or (image.mode == "P" and "transparency" in image.info)
    return image.convert("RGBA" if has_alpha else "RGB")


def dhash(image: Image.Image) -> int:
    """Hash percettivo a 64 bit (dHash): foto quasi uguali -> hash vicini (distanza di Hamming).
    Serve a ritrovare copie e ripubblicazioni (moderazione, seduta 16). Con segno, per bigint."""
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = small.tobytes()
    value = 0
    for row in range(8):
        for col in range(8):
            left = pixels[row * 9 + col]
            right = pixels[row * 9 + col + 1]
            value = (value << 1) | int(left > right)
    return value - (1 << 64) if value >= (1 << 63) else value


def hamming(a: int, b: int) -> int:
    return bin((a ^ b) & ((1 << 64) - 1)).count("1")


def process_image(data: bytes) -> Processed | Rejected:
    digest = hashlib.sha256(data).digest()
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            source = Image.open(io.BytesIO(data))
            if source.format not in ALLOWED_FORMATS:
                return Rejected("unsupported_format")
            width, height = source.size
            if width * height > MAX_PIXELS:
                return Rejected("too_many_pixels")
            if getattr(source, "n_frames", 1) > 1:
                source.seek(0)  # animazioni: si tiene solo il primo fotogramma
            source.load()
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        return Rejected("too_many_pixels")
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        return Rejected("not_an_image")

    image = ImageOps.exif_transpose(source) or source
    image = _normalize_mode(_to_srgb(image))
    width, height = image.size
    if min(width, height) < MIN_SIDE:
        return Rejected("too_small")
    if not MIN_ASPECT <= width / height <= MAX_ASPECT:
        return Rejected("bad_aspect_ratio")

    variants: dict[int, bytes] = {}
    for target in VARIANT_WIDTHS:
        w = min(target, width)
        if w in variants:
            continue
        h = max(1, round(height * w / width))
        resized = image if w == width else image.resize((w, h), Image.Resampling.LANCZOS)
        out = io.BytesIO()
        # Ricodifica senza exif/icc/xmp: i metadati dell'originale non arrivano mai online.
        resized.save(out, format="WEBP", quality=WEBP_QUALITY, method=4)
        variants[w] = out.getvalue()

    thumb = image.convert("RGB")
    thumb.thumbnail((32, 32))
    x, y = (4, 3) if width >= height else (3, 4)
    hash_text = blurhash_encode(thumb.tobytes(), thumb.width, thumb.height, x, y)

    return Processed(
        width=width,
        height=height,
        blurhash=hash_text,
        sha256=digest,
        phash=dhash(image),
        variants=variants,
    )
