"""The prices on the product page, held against the model that priced them.

`frontend/src/components/gap/prices.ts` states what a kilowatt hour is worth
before and after 1 January 2027. Those figures are a copy of three bands in
`ampeer_advice/tariffs.py`, and a copy of a number is the thing this repository
distrusts most: the advice page's figures move when the model moves, because
they come over the wire, and a marketing page's do not move at all.

So they are read back out of the TypeScript and compared. A tariff that changes
in the engine and not on the page arrives as a red build rather than as a page
quoting last year's landscape at every visitor who arrives from a search.

Read with a regex rather than by executing anything. The alternative is a Node
process in the Python test suite, and the shape being read is four numbers in
two object literals, which a regex can do without pretending to be a parser.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from ampeer_advice.tariffs import FEED_IN_COST, FEED_IN_GROSS_FIXED, SUPPLY_PRICE

REPO_ROOT = Path(__file__).resolve().parent.parent
PRICES = REPO_ROOT / "frontend" / "src" / "components" / "gap" / "prices.ts"

#: Cents per euro. The page works in cents because that is how this is spoken
#: about in Dutch; the model works in euros because that is how it bills.
CENTS = Decimal("100")


def _band(name: str) -> tuple[Decimal, Decimal]:
    """The `low` and `high` of one exported band, in cents."""
    source = PRICES.read_text(encoding="utf-8")
    match = re.search(
        rf"export const {name}: PriceBand = \{{ low: (-?[\d.]+), high: (-?[\d.]+) \}};",
        source,
    )
    assert match is not None, f"{name} is no longer a literal PriceBand in {PRICES.name}"
    return Decimal(match.group(1)), Decimal(match.group(2))


def test_the_page_is_read_at_all() -> None:
    """The half that keeps every comparison below from passing over nothing.

    Both assertions here are about the file rather than about a number: a
    renamed constant or a reformatted literal makes the regex match nothing,
    and `_band` fails loudly rather than returning a default that happens to
    agree.
    """
    assert PRICES.is_file(), "the product page's prices module has moved"
    low, high = _band("SELF_USED_CENTS")
    assert low < high, "a band whose low is not below its high is not a band"


def test_a_kilowatt_hour_used_at_home_is_worth_the_supply_price() -> None:
    """What you save is what you did not have to buy.

    The page draws this as the band that barely moves in 2027, which is half
    of what the figure argues: the change is not that self consumption became
    more valuable, it is that export stopped being valuable.
    """
    low, high = _band("SELF_USED_CENTS")
    assert low == SUPPLY_PRICE.low * CENTS
    assert high == SUPPLY_PRICE.high * CENTS


def test_an_exported_kilowatt_hour_is_worth_the_same_while_saldering_lasts() -> None:
    """Not a simplification of the rule. It is the rule.

    Saldering subtracts exported kilowatt hours from imported ones and bills
    the difference, so an exported one is worth exactly the imported one it
    cancels. The figure draws the two as one band because they are one band,
    and if these two constants ever diverge the figure is claiming saldering
    does something it does not.
    """
    source = PRICES.read_text(encoding="utf-8")
    # The alias itself, not two literals that agree. Two numbers that happen to
    # match today can drift on any edit; an alias cannot, and the page's claim
    # is an identity rather than a coincidence.
    assert "export const EXPORTED_NOW_CENTS: PriceBand = SELF_USED_CENTS;" in source, (
        "the exported band while saldering lasts is no longer the same object as the "
        "self-used band, so the figure can now draw two different heights for what the "
        "rule says is one price"
    )


def test_the_2027_band_is_the_widest_spread_the_model_can_price() -> None:
    """Gross minus cost, at the two ends that are furthest apart.

    Not `net_feed_in_fixed` at the three named levels. That function pairs low
    gross with low cost, and the honest spread a household faces pairs the
    lowest gross with the highest cost and the other way round: 0,050 against
    0,115 and 0,077 against 0,0446. Chapter 11 of docs/methodologie.md quotes
    the same pair and notes it agrees with the published net figures.
    """
    low, high = _band("EXPORTED_2027_CENTS")
    worst = (FEED_IN_GROSS_FIXED.low - FEED_IN_COST.high) * CENTS
    best = (FEED_IN_GROSS_FIXED.high - FEED_IN_COST.low) * CENTS
    assert float(low) == pytest.approx(float(worst), abs=0.05), (
        f"the worst case is now {worst} cents and the page says {low}"
    )
    assert float(high) == pytest.approx(float(best), abs=0.05), (
        f"the best case is now {best} cents and the page says {high}"
    )


def test_the_bottom_of_the_2027_band_is_still_below_zero() -> None:
    """The fact the whole figure exists to carry.

    At the unfavourable end, exporting a kilowatt hour costs money rather than
    earning any. Nothing in the "3 tot 8 cent" a reader has seen elsewhere says
    that, because that is the gross figure with the costs still in front of it.
    The page draws a dashed rule at zero and lets the band cross it; the day
    this stops being true, that rule is drawing a crossing that does not
    happen.
    """
    low, _ = _band("EXPORTED_2027_CENTS")
    assert low < 0, "the 2027 band no longer crosses zero and the figure says it does"


def test_the_scale_holds_every_band_the_page_draws() -> None:
    """A band clipped by its own axis is a price the reader cannot see.

    `downOf` clamps, so a band outside the scale would be drawn flat against
    the top or the bottom edge and look like a value it is not, silently.
    """
    source = PRICES.read_text(encoding="utf-8")
    top = Decimal(re.search(r"SCALE_TOP_CENTS = (-?[\d.]+)", source).group(1))  # type: ignore[union-attr]
    bottom = Decimal(re.search(r"SCALE_BOTTOM_CENTS = (-?[\d.]+)", source).group(1))  # type: ignore[union-attr]
    for name in ("SELF_USED_CENTS", "EXPORTED_2027_CENTS"):
        low, high = _band(name)
        assert bottom <= low, f"{name} runs below the scale"
        assert high <= top, f"{name} runs above the scale"
