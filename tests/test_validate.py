from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.validate import (
    REQUIRED_FIELDS,
    Deviation,
    FlatProfileProvider,
    check,
    load_statement,
    main,
)

STATEMENT: dict[str, Any] = {
    "postcode4": "5401",
    "annual_consumption_kwh": 3500.0,
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "daytime_occupancy": False,
    "measured_offtake_kwh": 2300.0,
    "measured_feed_in_kwh": 2100.0,
}


def _write(tmp_path: Path, payload: dict[str, Any]) -> Path:
    path = tmp_path / "statement.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_statement_reads_every_required_field(tmp_path: Path) -> None:
    statement = load_statement(_write(tmp_path, STATEMENT))
    assert statement.measured_offtake_kwh == pytest.approx(2_300.0)
    assert statement.postcode4 == "5401"


def test_load_statement_rejects_a_missing_field(tmp_path: Path) -> None:
    incomplete = {key: value for key, value in STATEMENT.items() if key != "measured_offtake_kwh"}
    with pytest.raises(ValueError, match="measured_offtake_kwh"):
        load_statement(_write(tmp_path, incomplete))


def test_deviation_reports_a_relative_error() -> None:
    deviation = Deviation(measured=2_000.0, modelled=2_200.0, label="offtake")
    assert deviation.relative_error == pytest.approx(0.10)
    assert not deviation.within(0.05)
    assert deviation.within(0.15)


def test_deviation_handles_a_zero_measurement() -> None:
    assert Deviation(measured=0.0, modelled=5.0, label="feed_in").relative_error == float("inf")
    assert Deviation(measured=0.0, modelled=0.0, label="feed_in").relative_error == 0.0


def test_check_reports_both_meter_directions(tmp_path: Path) -> None:
    deviations = check(
        load_statement(_write(tmp_path, STATEMENT)),
        profile_provider=FlatProfileProvider(),
        production_provider=FallbackProvider(2025),
        profile_year=2025,
        weather_year=2025,
    )
    assert [deviation.label for deviation in deviations] == ["offtake", "feed_in"]
    assert all(deviation.modelled > 0.0 for deviation in deviations)


def test_cli_exits_zero_when_the_model_is_close_enough(tmp_path: Path) -> None:
    path = _write(tmp_path, STATEMENT)
    assert main([str(path), "--tolerance", "1000", "--source", "offline"]) == 0


def test_cli_exits_one_when_the_model_is_too_far_off(tmp_path: Path) -> None:
    path = _write(tmp_path, STATEMENT)
    assert main([str(path), "--tolerance", "0.0001", "--source", "offline"]) == 1


def test_cli_warns_when_no_profile_file_is_given(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main([str(_write(tmp_path, STATEMENT)), "--tolerance", "1000", "--source", "offline"])
    assert "flat profile" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# What a statement cannot say, and what happens when it tries
# ---------------------------------------------------------------------------


def test_a_statement_describing_a_heat_pump_is_refused_rather_than_ignored(
    tmp_path: Path,
) -> None:
    """The field was dropped without a word, and the run looked clean.

    ``check`` has no way to model a heat pump: REQUIRED_FIELDS has no place for
    one and the Household it builds carries neither an EV nor a pump. Until
    2026-08-23 a statement that mentioned one was read as if it had not, the
    comparison ran, and the two lines of output described a household that is
    not the one on the statement.

    Measured with a flat profile on a household of 6969 kWh of which 3469 is a
    heat pump: offtake comes out 8.4 percent low and feed-in 23.2 percent low
    against a default tolerance of 10 percent. So the feed-in line reads OFF and
    somebody goes looking in the production model, which is not where the
    problem is. That is why this raises rather than warns.
    """
    with_pump = dict(STATEMENT, heat_pump_kwh=12_000.0)
    with pytest.raises(ValueError, match="does not use"):
        load_statement(_write(tmp_path, with_pump))


def test_a_misspelled_field_is_refused_too(tmp_path: Path) -> None:
    """The other half of the same silence, and the more likely one.

    A statement is a small file somebody writes by hand. "measured_feedin_kwh"
    used to be dropped as an unknown field while "measured_feed_in_kwh" came
    back missing, so the error named the absence and never the typo that caused
    it. Both halves are now reported.
    """
    typo = {key: value for key, value in STATEMENT.items() if key != "daytime_occupancy"}
    typo["daytime_occupancie"] = False
    with pytest.raises(ValueError) as raised:
        load_statement(_write(tmp_path, typo))
    message = str(raised.value)
    assert "daytime_occupancie" in message, (
        f"the message names the field that is absent and not the typo that caused it: {message}"
    )
    assert "daytime_occupancy" in message, f"the message no longer says what is missing: {message}"


def test_a_statement_holding_exactly_the_required_fields_still_loads(tmp_path: Path) -> None:
    """The floor, since the check above is a raise on a set difference.

    A guard comparing against the wrong set would refuse every statement, and
    the two tests above would both still pass.
    """
    statement = load_statement(_write(tmp_path, STATEMENT))
    assert statement.postcode4 == "5401"
    assert set(STATEMENT) == set(REQUIRED_FIELDS), (
        "the fixture no longer holds exactly the required fields, so it stopped being the "
        "case this floor is about"
    )


def test_the_cli_says_which_household_it_assumed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Printed on every run, because the tool cannot tell whether it applies.

    It has no field to read, which is the whole point: a household with a heat
    pump cannot say so, so the only honest moment to mention it is always.
    """
    main([str(_write(tmp_path, STATEMENT)), "--tolerance", "1000", "--source", "offline"])
    output = capsys.readouterr().out
    assert "no electric car and no heat pump" in output, (
        "the run no longer says which household it modelled"
    )
