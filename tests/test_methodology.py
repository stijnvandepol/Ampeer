"""The published methodology must describe the model that actually ships.

``docs/methodologie.md`` is the document Ampeer is judged on. Somebody who
disagrees with a number will read it, and if it describes a version of the model
that no longer exists, the honesty this whole project rests on is gone.

It went stale within a day of being written: four corrections landed in the code
and none of them reached the document. Nothing noticed, because a document
cannot fail a build. These tests are how it fails one.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from ampeer_advice import tariffs
from ampeer_advice.battery import MAX_ACCEPTABLE_PAYBACK_YEARS
from ampeer_sim.economics.sensitivity import VARIATIONS

METHODOLOGY = Path(__file__).resolve().parent.parent / "docs" / "methodologie.md"
TEXT = METHODOLOGY.read_text(encoding="utf-8")


def _dutch(value: Decimal) -> str:
    """Render a figure the way the document writes it, with a comma."""
    return str(value).replace(".", ",")


#: The label each band carries in the table in section 10. Reading the row
#: rather than searching the whole document matters: an earlier version of this
#: test only checked that the figure appeared somewhere, and the anchored middle
#: also appears in the paragraph that explains it, so the table could quietly
#: drift back to the arithmetic midpoint while the test stayed green.
TABLE_ROWS = {
    "SUPPLY_PRICE": "Stroomprijs per kWh, alles inbegrepen",
    "FEED_IN_GROSS_FIXED": "Bruto terugleververgoeding, vast contract",
    "FEED_IN_COST": "Terugleverkosten per teruggeleverde kWh",
    "FEED_IN_NET_DYNAMIC": "Netto terugleververgoeding, dynamisch contract",
    "BATTERY_COST_PER_KWH": "Thuisbatterij per kWh capaciteit, geplaatst",
}


def _table_values(label: str) -> tuple[str, str, str]:
    """The three figures on one row of the tariff table, as written."""
    match = re.search(rf"^\| {re.escape(label)} \|(.+)\|$", TEXT, re.MULTILINE)
    assert match, f"no table row for {label!r}"
    cells = [cell.strip() for cell in match.group(1).split("|") if cell.strip()]
    assert len(cells) == 3, f"{label!r} does not have three figures: {cells}"
    return cells[0], cells[1], cells[2]


@pytest.mark.parametrize("band_name", sorted(TABLE_ROWS))
def test_the_published_tariff_table_matches_the_code(band_name: str) -> None:
    """Every tariff the document prints must be the one the model uses.

    The middle of FEED_IN_COST is the one that moved: it is anchored so the net
    figure matches what suppliers publish rather than being the midpoint of its
    own range. This reads the row, so putting the arithmetic midpoint back in
    the table fails even though the anchored figure still appears in the prose.
    """
    band = getattr(tariffs, band_name)
    printed = _table_values(TABLE_ROWS[band_name])
    expected = (_dutch(band.low), _dutch(band.mid), _dutch(band.high))
    assert printed == expected, f"{band_name}: document says {printed}, code says {expected}"


def test_the_document_states_the_right_number_of_sensitivity_runs() -> None:
    """The band is the product's central honesty claim, so its size is a fact.

    The document said 81 while the code ran 243, because a fifth assumption was
    added without the text following. A reader checking the claim would have
    found a different number than the one they were told.
    """
    runs = 3 ** len(VARIATIONS)
    assert f"{runs} doorrekeningen" in TEXT, f"the document does not mention {runs} runs"
    assert "81 doorrekeningen" not in TEXT, "a stale run count survived in the document"


def test_the_document_states_the_right_number_of_varied_assumptions() -> None:
    spelled = {4: "vier", 5: "vijf", 6: "zes", 7: "zeven"}[len(VARIATIONS)]
    assert f"{spelled} aannames" in TEXT


def test_the_document_states_the_payback_limit_the_code_applies() -> None:
    assert MAX_ACCEPTABLE_PAYBACK_YEARS == Decimal("12")
    assert "twaalf jaar" in TEXT


def test_the_document_carries_no_em_dashes() -> None:
    """Project convention for every user-facing Dutch text."""
    assert "—" not in TEXT


def test_the_document_still_names_its_own_limitations() -> None:
    """The section a reader looks for when they distrust the answer.

    Losing it would be the single most damaging edit anyone could make to this
    file, and the easiest to make by accident while tidying.
    """
    assert "## 16. Wat wij niet weten" in TEXT
    for limitation in ("schaduw", "gemiddelde", "aangenomen"):
        assert limitation in TEXT, f"the limitations section no longer mentions {limitation}"


def test_every_section_is_numbered_consecutively() -> None:
    """A renumbering that skips or repeats is a merge accident, not a choice."""
    numbers = [int(match) for match in re.findall(r"^## (\d+)\.", TEXT, re.MULTILINE)]
    assert numbers == list(range(1, len(numbers) + 1)), numbers
