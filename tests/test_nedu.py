from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from ampeer_sim.profiles.nedu import (
    NeduFileProvider,
    ProfileValidationError,
    expected_sum,
    scale_to_annual,
    validate_fractions,
)
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import ProfileCategory

FIXTURE = Path(__file__).parent / "fixtures" / "nedu_tiny.csv"


def test_provider_reads_the_requested_category_column() -> None:
    provider = NeduFileProvider(FIXTURE)
    fractions = provider.fractions(2025, ProfileCategory.E1A)
    assert np.allclose(fractions, [0.1, 0.2, 0.3, 0.4])


def test_provider_reads_a_second_category_from_the_same_file() -> None:
    provider = NeduFileProvider(FIXTURE)
    fractions = provider.fractions(2025, ProfileCategory.E1B)
    assert np.allclose(fractions, [0.5, 0.5, 0.5, 0.5])


def test_provider_rejects_a_year_the_file_does_not_hold() -> None:
    provider = NeduFileProvider(FIXTURE)
    with pytest.raises(ProfileValidationError, match="2026"):
        provider.fractions(2026, ProfileCategory.E1A)


def test_provider_rejects_a_category_the_file_does_not_hold() -> None:
    provider = NeduFileProvider(FIXTURE)
    with pytest.raises(ProfileValidationError, match="E1C"):
        provider.fractions(2025, ProfileCategory.E1C)


def test_expected_sum_is_one_for_e1a_and_two_for_dual_register_profiles() -> None:
    assert expected_sum(ProfileCategory.E1A) == pytest.approx(1.0)
    assert expected_sum(ProfileCategory.E1B) == pytest.approx(2.0)
    assert expected_sum(ProfileCategory.E1C) == pytest.approx(2.0)


def test_validate_accepts_a_sum_within_tolerance() -> None:
    grid = YearGrid.for_year(2025)
    fractions = np.full(grid.quarters, 1.0 / grid.quarters)
    fractions[0] += 5e-7
    validate_fractions(fractions, ProfileCategory.E1A, grid)


def test_validate_rejects_a_sum_outside_tolerance() -> None:
    grid = YearGrid.for_year(2025)
    fractions = np.full(grid.quarters, 1.05 / grid.quarters)
    with pytest.raises(ProfileValidationError, match="sum"):
        validate_fractions(fractions, ProfileCategory.E1A, grid)


def test_validate_rejects_a_wrong_length_series() -> None:
    grid = YearGrid.for_year(2025)
    with pytest.raises(ProfileValidationError, match="35040"):
        validate_fractions(np.zeros(10), ProfileCategory.E1A, grid)


def test_validate_accepts_a_leap_year_sum_above_the_nominal_value() -> None:
    grid = YearGrid.for_year(2024)
    fractions = np.full(grid.quarters, 1.0 / 35_040)  # sums to about 1.0027
    validate_fractions(fractions, ProfileCategory.E1A, grid)


def test_scaling_hits_the_annual_total_exactly() -> None:
    fractions = np.array([0.1, 0.2, 0.3, 0.4])
    scaled = scale_to_annual(fractions, 3_500.0, ProfileCategory.E1A)
    assert scaled.sum() == pytest.approx(3_500.0)
    assert scaled[3] == pytest.approx(1_400.0)


def test_scaling_a_dual_register_profile_also_hits_the_annual_total() -> None:
    fractions = np.full(4, 0.5)  # sums to 2, as E1B does
    scaled = scale_to_annual(fractions, 3_500.0, ProfileCategory.E1B)
    assert scaled.sum() == pytest.approx(3_500.0)


def test_scaling_an_empty_profile_is_rejected() -> None:
    with pytest.raises(ProfileValidationError, match="sum to"):
        scale_to_annual(np.zeros(4), 3_500.0, ProfileCategory.E1A)
