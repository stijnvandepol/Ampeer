"""The wire format for a year of quarter-hour flows, and its proof.

Two arrays of one byte per quarter, base64 encoded.

  byte 1  what the household used of its own production, scaled to ``own``
  byte 2  the meter, seven bits of magnitude with the direction in the high bit

The second array holds one number because a quarter is never both directions at
once: there is a surplus or a shortfall. Measured on 2026-08-27 over a full
year, quarters holding both: 0. That is what buys the packing, and
``encode_year`` asserts it rather than assuming it, because the day it stops
being true the picture would silently show the wrong side of the meter.

The two directions carry their own ceiling. A shared one would spend the seven
bits on export, which peaks at 617 Wh a quarter against 190 Wh of offtake on
the same household, and leave offtake with a third of the resolution it could
have had for free.

The ceiling is the maximum and not a percentile. A percentile makes a prettier
plate and clips the brightest quarters; at p99 that was 181, 256 and 96 quarters
of 35040. The wire carries data and the renderer makes it legible, so the
clipping belongs in the renderer where it can be undone, not in the payload
where it cannot.

Verified round trip on 2026-08-27 against the unquantised series: worst single
quarter error equals exactly half a quantisation step on all three series,
annual totals within 0.003 percent, zero quarters returned on the wrong side of
the meter. Ninety one kilobytes raw, thirty nine gzipped.

Provenance is the part of this module that is not about bytes.

In phase 0.5 the series is SYNTHETIC: a national NEDU profile scaled to the
annual figure the visitor typed, plus modelled assets. It says nothing about
that household that the household did not type in. In phase 2 the identical
field carries a MEASURED series off their own meter, and a measured
quarter-hour consumption series says when somebody is home, which
``docs/dpia.md`` chapter 1 names as the verification that turns the risk
assessment around.

An advice is retrievable for ninety days through a token its holder can pass to
anyone. So the field carries where its numbers came from, and
``advice.serializers.year_field`` refuses to build a payload that pairs a
measured series with a shareable token. Built now it is three lines. Added in
phase 2 it needs a migration over every stored advice and leaves a gap between
the first measured series and the control over it.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass

import numpy as np

#: The high bit of the meter byte. Set means the quarter exported.
EXPORT_FLAG = 0x80

#: The seven bits under it, which is the magnitude either direction gets.
MAGNITUDE_MASK = 0x7F

#: The own-use byte spends all eight bits, because it has no direction to carry.
OWN_FULL_SCALE = 0xFF

#: Modelled from a national profile and what the visitor typed.
SYNTHETIC = "SYNTHETIC"

#: Read off this household's own meter. Nothing produces one today.
MEASURED = "MEASURED"

#: Everything the field may say about itself.
PROVENANCE: frozenset[str] = frozenset({SYNTHETIC, MEASURED})

#: What a payload retrievable through a shareable token may carry. The one
#: member is the whole control: a token is a bearer credential with a ninety
#: day life and no account behind it, so anything readable through it is
#: readable by whoever the link reaches.
SHAREABLE_PROVENANCE: frozenset[str] = frozenset({SYNTHETIC})

#: A common year and a leap year, at 96 quarters a day. Pinned as a pair rather
#: than derived, because this is the length a browser allocates for before it
#: has looked at the array, and a third value would be a bug in the grid rather
#: than a calendar this project has to serve.
QUARTERS_PER_YEAR: frozenset[int] = frozenset({365 * 96, 366 * 96})

#: The wire key the shareability rule is read from. It lives here, beside the
#: format, so that the serializer names it instead of spelling it again.
PROVENANCE_KEY = "provenance"


class MeasuredSeriesRefused(ValueError):
    """A measured series was about to be paired with a shareable token.

    A ValueError and not a validation error, because no request can cause it.
    Nothing a stranger posts chooses a provenance; only server code does, so
    this is a programming fault reaching the response path and it should read
    as one.
    """


@dataclass(frozen=True)
class EncodedYear:
    """One household's year, packed, with where its numbers came from.

    There is deliberately no method here that turns this into the wire dict.
    ``advice.serializers.year_field`` is the only thing that produces one, and
    it is the only thing that checks the provenance against the token the
    payload will be reachable by. A convenience ``as_dict`` beside the data
    would be a second exit with no check on it, which is how a control that
    costs three lines stops being reached.
    """

    own: str
    meter: str
    ceilings: dict[str, float]
    provenance: str
    quarters: int


def refuse_unless_shareable(provenance: str) -> None:
    """Raise unless this provenance may leave over a shareable token."""
    if provenance not in SHAREABLE_PROVENANCE:
        raise MeasuredSeriesRefused(
            f"a {provenance} series may not be served over a shareable token; "
            f"only {sorted(SHAREABLE_PROVENANCE)} may"
        )


def encode_year(
    own_kwh: np.ndarray,
    export_kwh: np.ndarray,
    grid_kwh: np.ndarray,
    provenance: str = SYNTHETIC,
) -> EncodedYear:
    """Pack a year of flows into two byte arrays.

    ``own_kwh`` is what the household used of its own production, ``export_kwh``
    what went to the grid and ``grid_kwh`` what came off it, all in kWh per
    quarter and all non-negative.
    """
    if provenance not in PROVENANCE:
        raise ValueError(f"unrecognised provenance {provenance!r}, expected {sorted(PROVENANCE)}")
    if not (own_kwh.shape == export_kwh.shape == grid_kwh.shape):
        raise ValueError("the three series must have the same length")
    if own_kwh.shape[0] not in QUARTERS_PER_YEAR:
        raise ValueError(
            f"{own_kwh.shape[0]} quarters is not a year; expected one of "
            f"{sorted(QUARTERS_PER_YEAR)}"
        )
    both = int(((export_kwh > 0) & (grid_kwh > 0)).sum())
    if both:
        raise ValueError(
            f"{both} quarters hold both directions at once; the packing here "
            "assumes a quarter is a surplus or a shortfall and not both"
        )

    ceilings = {
        "own": float(own_kwh.max()),
        "export": float(export_kwh.max()),
        "grid": float(grid_kwh.max()),
    }

    own_bytes = _scale(own_kwh, ceilings["own"], OWN_FULL_SCALE)

    exporting = export_kwh > 0
    magnitude = np.where(
        exporting,
        _scale(export_kwh, ceilings["export"], MAGNITUDE_MASK),
        _scale(grid_kwh, ceilings["grid"], MAGNITUDE_MASK),
    ).astype(np.uint8)
    meter_bytes = (magnitude | np.where(exporting, EXPORT_FLAG, 0)).astype(np.uint8)

    return EncodedYear(
        own=base64.b64encode(own_bytes.tobytes()).decode("ascii"),
        meter=base64.b64encode(meter_bytes.tobytes()).decode("ascii"),
        ceilings=ceilings,
        provenance=provenance,
        quarters=int(own_kwh.shape[0]),
    )


def _scale(series: np.ndarray, ceiling: float, full: int) -> np.ndarray:
    """Map [0, ceiling] onto [0, full], to the nearest step.

    A ceiling of zero is a household that never did this at all, which is a
    real answer rather than an error: a flat is capable of importing every
    quarter of the year and exporting none of them.
    """
    if ceiling <= 0.0:
        return np.zeros_like(series, dtype=np.uint8)
    return np.rint(np.clip(series / ceiling, 0.0, 1.0) * full).astype(np.uint8)


def decode_year(encoded: EncodedYear) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The inverse, so a round trip can be checked rather than believed.

    It lives beside the encoder and not in the test, because the browser holds
    the same three lines and a reader comparing the two should be reading one
    file. Return order matches the encoder's arguments: own, export, grid.
    """
    own_bytes = np.frombuffer(base64.b64decode(encoded.own), dtype=np.uint8)
    meter_bytes = np.frombuffer(base64.b64decode(encoded.meter), dtype=np.uint8)
    exporting = (meter_bytes & EXPORT_FLAG) > 0
    magnitude = (meter_bytes & MAGNITUDE_MASK).astype(float) / MAGNITUDE_MASK

    own = own_bytes.astype(float) / OWN_FULL_SCALE * encoded.ceilings["own"]
    export = np.where(exporting, magnitude * encoded.ceilings["export"], 0.0)
    grid = np.where(exporting, 0.0, magnitude * encoded.ceilings["grid"])
    return own, export, grid
