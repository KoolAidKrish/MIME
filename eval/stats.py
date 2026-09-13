"""Small statistics helpers.

The module gives the exact significance level for a clean separation.
A clean separation means every sample of one config beats every sample of the other.
The one-sided Mann-Whitney U test measures this directly.
For small, fully separated samples the exact p-value is 1 / C(n1 + n2, n1).
The module needs no scipy.
"""
from __future__ import annotations

import math


def exact_separation_pvalue(n1: int, n2: int) -> float:
    """Return the one-sided p-value for a full, clean separation.

    The value assumes every sample of one group beats every sample of the other.
    Example: n1 = 5 and n2 = 4 gives 1 / C(9, 5) which is about 0.008.
    """
    if n1 <= 0 or n2 <= 0:
        return 1.0
    return 1.0 / math.comb(n1 + n2, n1)


def ranges_separate(a: list[float], b: list[float]) -> bool:
    """Return True when the two sample ranges do not overlap."""
    if not a or not b:
        return False
    return max(a) < min(b) or max(b) < min(a)
