"""Minimal HERE Flexible Polyline decoder.

Implements the algorithm from the official heremaps/flexible-polyline library
(https://github.com/heremaps/flexible-polyline), MIT licensed. Only the 2D
case is supported here; the third dimension (if present) is skipped.
"""
from __future__ import annotations

FORMAT_VERSION = 1

# maps (ord(char) - 45) -> 6-bit value; -1 means invalid character
_DECODING_TABLE = [
    62, -1, -1, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, -1, -1, -1, -1, -1, -1, -1,
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21,
    22, 23, 24, 25, -1, -1, -1, -1, 63, -1, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35,
    36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51,
]


def _decode_char(char: str) -> int:
    value = _DECODING_TABLE[ord(char) - 45]
    if value < 0:
        raise ValueError("Invalid encoding")
    return value


def _to_signed(value: int) -> int:
    if value & 1:
        value = ~value
    value >>= 1
    return value


def _decode_unsigned_values(encoded: str):
    result = shift = 0
    for char in encoded:
        value = _decode_char(char)
        result |= (value & 0x1F) << shift
        if (value & 0x20) == 0:
            yield result
            result = shift = 0
        else:
            shift += 5
    if shift > 0:
        raise ValueError("Invalid encoding")


def decode_polyline(encoded: str) -> list[list[float]]:
    """Decode a HERE flexible polyline into a list of [lng, lat]."""
    last_lat = last_lng = 0
    decoder = _decode_unsigned_values(encoded)

    version = next(decoder)
    if version != FORMAT_VERSION:
        raise ValueError("Invalid format version")

    value = next(decoder)
    precision = value & 15
    value >>= 4
    third_dim = value & 7
    # third_dim_precision = (value >> 3) & 15  (unused for 2D)

    factor = 10.0 ** precision
    coords: list[list[float]] = []

    while True:
        try:
            last_lat += _to_signed(next(decoder))
        except StopIteration:
            break
        try:
            last_lng += _to_signed(next(decoder))
        except StopIteration:
            raise ValueError("Invalid encoding. Premature ending reached")
        if third_dim:
            next(decoder)  # skip the z component
        coords.append([last_lng / factor, last_lat / factor])

    return coords
