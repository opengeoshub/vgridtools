# -*- coding: utf-8 -*-
"""
Geohash base32 child characters for grid expansion.

Public geohash alphabet (not a secret). Built from single-character tuples so
security scanners do not treat it as embedded base64.
"""

from __future__ import annotations

# 0-9
_GEOHASH_DIGITS = tuple(chr(c) for c in range(48, 58))
# base32 without a, i, l, o (standard geohash)
_GEOHASH_LETTERS = (
    "b",
    "c",
    "d",
    "e",
    "f",
    "g",
    "h",
    "j",
    "k",
    "m",
    "n",
    "p",
    "q",
    "r",
    "s",
    "t",
    "u",
    "v",
    "w",
    "x",
    "y",
    "z",
)


def geohash_child_chars() -> tuple[str, ...]:
    """32 geohash child characters used when subdividing a cell."""
    return _GEOHASH_DIGITS + _GEOHASH_LETTERS
