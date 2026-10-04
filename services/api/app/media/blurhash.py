"""Codifica BlurHash (https://blurha.sh): l'anteprima sfocata che l'app mostra mentre la foto
arriva. Implementazione propria, piccola e senza dipendenze, verificata nei test contro
la libreria di riferimento."""

from __future__ import annotations

import math

_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"


def _encode83(value: int, length: int) -> str:
    out = ""
    for i in range(1, length + 1):
        digit = (value // 83 ** (length - i)) % 83
        out += _CHARS[digit]
    return out


def _to_linear(value: int) -> float:
    v = value / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _to_srgb(value: float) -> int:
    v = max(0.0, min(1.0, value))
    if v <= 0.0031308:
        return int(v * 12.92 * 255 + 0.5)
    return int((1.055 * v ** (1 / 2.4) - 0.055) * 255 + 0.5)


def _sign_pow(value: float, exp: float) -> float:
    return math.copysign(abs(value) ** exp, value)


def encode(rgb: bytes, width: int, height: int, x_components: int, y_components: int) -> str:
    """`rgb`: pixel RGB a 8 bit, riga per riga (es. Image.tobytes() di un'immagine "RGB")."""
    if not (1 <= x_components <= 9 and 1 <= y_components <= 9):
        raise ValueError("componenti tra 1 e 9")
    if len(rgb) != width * height * 3:
        raise ValueError("dimensioni non coerenti con i pixel")
    linear = [_to_linear(b) for b in rgb]
    cos_x = [[math.cos(math.pi * i * x / width) for x in range(width)] for i in range(x_components)]
    cos_y = [
        [math.cos(math.pi * j * y / height) for y in range(height)] for j in range(y_components)
    ]

    factors: list[tuple[float, float, float]] = []
    for j in range(y_components):
        for i in range(x_components):
            norm = 1.0 if i == 0 and j == 0 else 2.0
            r = g = b = 0.0
            for y in range(height):
                cy = cos_y[j][y]
                row = y * width * 3
                for x in range(width):
                    basis = cos_x[i][x] * cy
                    p = row + x * 3
                    r += basis * linear[p]
                    g += basis * linear[p + 1]
                    b += basis * linear[p + 2]
            scale = norm / (width * height)
            factors.append((r * scale, g * scale, b * scale))

    dc, ac = factors[0], factors[1:]
    out = _encode83((x_components - 1) + (y_components - 1) * 9, 1)
    if ac:
        actual_max = max(abs(v) for f in ac for v in f)
        quantised = max(0, min(82, math.floor(actual_max * 166 - 0.5)))
        max_value = (quantised + 1) / 166
        out += _encode83(quantised, 1)
    else:
        max_value = 1.0
        out += _encode83(0, 1)
    out += _encode83((_to_srgb(dc[0]) << 16) + (_to_srgb(dc[1]) << 8) + _to_srgb(dc[2]), 4)

    def quant(v: float) -> int:
        return max(0, min(18, math.floor(_sign_pow(v / max_value, 0.5) * 9 + 9.5)))

    for r, g, b in ac:
        out += _encode83(quant(r) * 19 * 19 + quant(g) * 19 + quant(b), 2)
    return out
