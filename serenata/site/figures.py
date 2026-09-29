"""Numbers as a reader sees them, without a floating point in sight.

The flag record carries a rate as the two counts it came from so that no file
depends on a rounding decision (`serenata.classify.records`). The site holds the
same line for the same reason: a percentage printed on a page is computed with
integer arithmetic, so it is the same string on every machine and every run.
"""

from __future__ import annotations


def thousands(value: int) -> str:
    """``8132`` as ``8,132``."""
    return f"{value:,}"


def percent(part: int, whole: int, places: int = 1) -> str:
    """``part`` as a percentage of ``whole``, rounded half up, as a string.

    ``percent(4283, 8132)`` is ``"52.7"``. A zero whole has no percentage and
    raises rather than printing a number that means nothing.
    """
    if whole <= 0:
        raise ValueError("a percentage needs a positive whole")
    scale = 10**places
    scaled = (200 * part * scale + whole) // (2 * whole)
    if places == 0:
        return str(scaled)
    return f"{scaled // scale}.{scaled % scale:0{places}d}"


def ratio(part: int, whole: int, places: int = 3) -> str:
    """``part / whole`` as a decimal string between 0 and 1, truncated, no float.

    Used to size a bar in CSS (``calc(var(--r) * 78%)``), where a truncated
    third decimal is far below a pixel and an integer computation is one less
    place two machines could differ.
    """
    if whole <= 0 or part >= whole:
        return "1"
    scale = 10**places
    return f"0.{part * scale // whole:0{places}d}"
