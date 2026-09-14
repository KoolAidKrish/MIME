"""Amount parsing.

The module reads a monetary amount from text.
It understands a dollar sign, thousands commas, a decimal, and a K, M, or B suffix.
So it reads both "$12,500,000" and the short form "$4.2M".
The regex extractors share this one parser, so they read amounts the same way.
"""
from __future__ import annotations

import re
from typing import Optional

# One number: optional sign and dollar sign, digits with commas, optional decimal,
# and an optional scale suffix (thousand, million, billion).
_NUMBER = re.compile(r"([-+]?\$?[\d,]+(?:\.\d+)?)\s*([KkMmBb])?")

_SCALE = {"k": 1_000.0, "m": 1_000_000.0, "b": 1_000_000_000.0}


def parse_amount(text: str) -> Optional[float]:
    """Return the first monetary amount in the text, or None when there is none.

    The suffix K, M, or B multiplies the number by a thousand, a million, or a billion.
    """
    match = _NUMBER.search(text)
    if not match:
        return None
    core = match.group(1).replace("$", "").replace(",", "")
    try:
        value = float(core)
    except ValueError:
        return None
    suffix = match.group(2)
    if suffix:
        value *= _SCALE[suffix.lower()]
    return value
