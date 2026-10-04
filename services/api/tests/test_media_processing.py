"""Elaborazione delle foto: metadati via, rotazione applicata, varianti, rifiuti."""

from __future__ import annotations

import io

import blurhash
import pytest
from PIL import Image

from app.media.processing import (
    Processed,
    Rejected,
    dhash,
    hamming,
    process_image,
)
from tests.imagekit import GPS_IFD, has_metadata, photo


def _ok(data: bytes) -> Processed:
    result = process_image(data)
    assert isinstance(result, Processed), result
    return result


def test_l_originale_ha_davvero_il_gps():
    with Image.open(io.BytesIO(photo(gps=True))) as image:
        assert image.getexif().get_ifd(GPS_IFD)


def test_gps_e_dati_del_telefono_spariscono():
    result = _ok(photo(gps=True))
    for webp in result.variants.values():
        assert not has_metadata(webp)
        assert b"iPhone" not in webp
        assert b"Apple" not in webp


def test_varianti_webp_senza_ingrandire():
    result = _ok(photo(1600, 2000))
    assert sorted(result.variants) == [320, 640, 1080]
    for width, webp in result.variants.items():
        with Image.open(io.BytesIO(webp)) as image:
            assert image.format == "WEBP"
            assert image.width == width
            assert image.height == round(2000 * width / 1600)
    small = _ok(photo(700, 700))
    assert sorted(small.variants) == [320, 640, 700]  # mai più grande dell'originale


def test_orientamento_applicato():
    # Orientamento 6 = scattata col telefono ruotato: va girata di 90°.
    result = _ok(photo(1600, 1200, orientation=6))
    assert (result.width, result.height) == (1200, 1600)
    with Image.open(io.BytesIO(result.variants[1080])) as image:
        rgb = image.convert("RGB")
        top = rgb.getpixel((rgb.width // 2, 5))
        bottom = rgb.getpixel((rgb.width // 2, rgb.height - 5))
    # La metà sinistra (rossa) ora sta in alto, la destra (blu) in basso.
    assert top[0] > top[2] and bottom[2] > bottom[0]


def test_blurhash_hash_e_impronta():
    data = photo()
    result = _ok(data)
    import hashlib

    assert result.sha256 == hashlib.sha256(data).digest()
    assert blurhash.decode(result.blurhash, 4, 4)  # decodificabile
    assert len(result.blurhash) >= 20
    # Stessa foto ricompressa: impronta quasi uguale. Foto diversa: lontana.
    with Image.open(io.BytesIO(data)) as image:
        again = io.BytesIO()
        image.save(again, format="JPEG", quality=60)
    assert hamming(result.phash, _ok(again.getvalue()).phash) <= 6
    other = Image.new("RGB", (800, 800))
    for x in range(0, 800, 100):
        other.paste((x // 4, 255 - x // 4, 120), (x, 0, x + 50, 800))
    assert hamming(result.phash, dhash(other)) > 10
    assert -(2**63) <= result.phash < 2**63


@pytest.mark.parametrize("fmt", ["PNG", "WEBP"])
def test_altri_formati_ammessi(fmt):
    _ok(photo(800, 1000, fmt=fmt))


def test_png_trasparente_e_cmyk():
    _ok(photo(800, 800, fmt="PNG", mode="RGBA"))
    _ok(photo(800, 800, mode="CMYK"))


@pytest.mark.parametrize(
    "data,reason",
    [
        (b"ciao, non sono una foto", "not_an_image"),
        (b"\xff\xd8\xff\xe0" + b"\x00" * 200, "not_an_image"),  # JPEG finto
        (photo(800, 800)[:5000], "not_an_image"),  # troncata
        (photo(800, 800, fmt="GIF"), "unsupported_format"),
        (photo(800, 800, fmt="BMP"), "unsupported_format"),
        (photo(200, 200), "too_small"),
        (photo(2000, 600), "bad_aspect_ratio"),
        (photo(400, 1200), "bad_aspect_ratio"),
    ],
)
def test_rifiuti(data, reason):
    result = process_image(data)
    assert isinstance(result, Rejected)
    assert result.reason == reason


def test_bomba_di_decompressione_rifiutata_senza_decodificarla():
    # 9000x9000 = 81 megapixel, ma pochi KB di file: va fermata leggendo solo l'intestazione.
    image = Image.new("1", (9000, 9000))
    out = io.BytesIO()
    image.save(out, format="PNG")
    assert len(out.getvalue()) < 200_000
    result = process_image(out.getvalue())
    assert isinstance(result, Rejected) and result.reason == "too_many_pixels"


def test_blurhash_uguale_alla_libreria_di_riferimento():
    from app.media.blurhash import encode

    for seed, (w, h) in enumerate([(32, 24), (24, 32), (17, 9)]):
        with Image.open(io.BytesIO(photo(800, 600, seed=seed))) as source:
            image = source.convert("RGB").resize((w, h))
        for cx, cy in [(4, 3), (3, 4), (1, 1), (9, 9)]:
            # La libreria di riferimento chiude l'immagine che riceve: le si passa una copia.
            expected = blurhash.encode(image.copy(), x_components=cx, y_components=cy)
            assert encode(image.tobytes(), w, h, cx, cy) == expected
