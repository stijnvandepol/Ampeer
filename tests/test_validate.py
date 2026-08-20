from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.validate import (
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
