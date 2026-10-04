"""Immagini di prova generate al volo (nessun file binario nel repository)."""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

GPS_IFD = 0x8825
ORIENTATION = 0x0112


def photo(
    width: int = 1600,
    height: int = 2000,
    *,
    fmt: str = "JPEG",
    orientation: int | None = None,
    gps: bool = False,
    mode: str = "RGB",
    seed: int = 0,
) -> bytes:
    """Foto finta: metà sinistra rossa, metà destra blu (per verificare la rotazione)."""
    image = Image.new("RGB", (width, height), (200, 30, 30))
    draw = ImageDraw.Draw(image)
    draw.rectangle([width // 2, 0, width, height], fill=(30, 30, 200))
    draw.ellipse(
        [width // 4, height // 4, width // 4 + 200 + seed * 37, height // 4 + 300],
        fill=(240, 220, 40),
    )
    if mode != "RGB":
        image = image.convert(mode)
    exif = Image.Exif()
    if orientation:
        exif[ORIENTATION] = orientation
    if gps:
        exif[0x010F] = "Apple"
        exif[0x0110] = "iPhone 15 Pro"
        gps_ifd = exif.get_ifd(GPS_IFD)
        gps_ifd[1] = "N"
        gps_ifd[2] = (46.0, 4.0, 12.0)  # Trento
        gps_ifd[3] = "E"
        gps_ifd[4] = (11.0, 7.0, 15.0)
    out = io.BytesIO()
    kwargs = {"exif": exif} if (orientation or gps) else {}
    image.save(out, format=fmt, **kwargs)
    return out.getvalue()


def has_metadata(webp: bytes) -> bool:
    with Image.open(io.BytesIO(webp)) as image:
        return bool(image.getexif()) or "icc_profile" in image.info or "xmp" in image.info
