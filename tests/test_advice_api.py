"""The three endpoints, end to end, against a real database.

These are the only tests that run the whole thing: validation, the engine, the
cache, storage and rendering. The engine is real; only the two external sources
are replaced, and production is replaced by the offline table this project
already ships rather than by a stub, so what these tests exercise is what a
visitor gets when PVGIS is down.
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

import numpy as np
import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from advice.models import AuditEvent, ProductionCache, StoredAdvice
from advice.production import CachedProductionProvider
from ampeer_sim.production.pvgis import FallbackProvider
from ampeer_sim.providers import ProductionProvider, ProfileProvider
from ampeer_sim.timebase import YearGrid
from ampeer_sim.types import ProfileCategory

pytestmark = pytest.mark.django_db

ESTIMATE: dict[str, Any] = {
    "postcode4": "5401",
    "peak_power_wp": 3500,
    "azimuth_deg": 0,
    "tilt_deg": 35,
    "annual_consumption_kwh": 3500,
}

REFINE: dict[str, Any] = ESTIMATE | {
    "daytime_occupancy": True,
    "has_ev": False,
    "ev_behaviour": None,
    "has_heat_pump": False,
    "heat_demand_kwh": None,
    "dynamic_contract": False,
    "has_battery": False,
    "battery_capacity_kwh": None,
}

#: The budget from the definition of done, in seconds, for a request whose
#: production series is already cached. It is a promise about what a visitor
#: experiences, so it may be measured but never relaxed.
CACHED_REQUEST_BUDGET_S = 1.0


class FlatProfileProvider:
    """A consumption shape that is deliberately not a model of anything.

    It is acceptable here and nowhere else, because these tests assert the shape
    of a response and never a euro amount. The golden households and the
    calibration tests are where the numbers are judged, and they read the real
    NEDU series. The sum is 1.0, which is what E1A is validated against.
    """

    def fractions(self, year: int, category: ProfileCategory) -> np.ndarray:
        quarters = YearGrid.for_year(year).quarters
        return np.full(quarters, 1.0 / quarters)


@pytest.fixture(autouse=True)
def _offline_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    """No network call and no NEDU file, without changing the code path.

    The cache under test is the real one. Only what sits behind it changes, from
    PVGIS to the offline yield table built from nine measured years, which is
    what a visitor gets when PVGIS is down.
    """

    def _profiles() -> ProfileProvider:
        return FlatProfileProvider()

    def _production(weather_year: int) -> ProductionProvider:
        return CachedProductionProvider(FallbackProvider(weather_year), weather_year=weather_year)

    monkeypatch.setattr("advice.service.profile_provider", _profiles)
    monkeypatch.setattr("advice.service.production_provider", _production)


def test_an_estimate_returns_a_complete_advice() -> None:
    response = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert response.status_code == 201, response.data
    payload = response.json()
    assert payload["confidence"] == "INDICATIVE"
    assert set(payload["headline"]) == {"p10", "p50", "p90", "runs"}
    assert [route["route"] for route in payload["routes"]] == [
        "SHIFT_BEHAVIOUR",
        "SMART_CONTROL",
        "STORAGE",
    ]
    assert payload["token"]


def test_a_refine_is_called_good_and_an_estimate_is_not() -> None:
    """Four questions and nine questions must not produce the same label.

    This pins the count that ampeer_advice.confidence reads. Passing the number
    of serializer fields instead of the number of questions would make both of
    these GOOD, and nothing else in the system would notice.
    """
    estimate = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    refine = APIClient().post(reverse("advice-refine"), REFINE, format="json")
    assert estimate.json()["confidence"] == "INDICATIVE"
    assert refine.json()["confidence"] == "GOOD"


def test_a_stored_advice_comes_back_unchanged_through_its_link() -> None:
    created = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    fetched = APIClient().get(reverse("advice-detail", args=[created["token"]]))
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_two_requests_get_different_tokens() -> None:
    client = APIClient()
    first = client.post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    second = client.post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    assert first["token"] != second["token"]


def test_an_unknown_token_is_a_404() -> None:
    response = APIClient().get(reverse("advice-detail", args=["A" * 22]))
    assert response.status_code == 404


def test_a_token_of_the_wrong_shape_never_reaches_the_database() -> None:
    """The route matches 22 url-safe characters and nothing else, so a
    malformed token is a 404 from the router. A wide pattern would turn every
    stray path segment under this prefix into a database query."""
    assert APIClient().get("/api/advice/short/").status_code == 404


def test_an_expired_token_is_a_404_and_not_stale_content() -> None:
    created = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    StoredAdvice.objects.filter(token=created["token"]).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    response = APIClient().get(reverse("advice-detail", args=[created["token"]]))
    assert response.status_code == 404


def test_an_invalid_estimate_is_refused_with_the_field_named() -> None:
    response = APIClient().post(
        reverse("advice-estimate"), ESTIMATE | {"postcode4": "540111"}, format="json"
    )
    assert response.status_code == 400
    assert "postcode4" in response.json()


def test_a_four_digit_number_that_is_not_a_postcode_is_refused_at_the_endpoint() -> None:
    """Dutch postcodes start at 1000. Without this check the value reaches the
    production provider as a location that does not exist, and the offline table
    answers for a default centroid rather than reporting anything."""
    response = APIClient().post(
        reverse("advice-estimate"), ESTIMATE | {"postcode4": "0999"}, format="json"
    )
    assert response.status_code == 400
    assert "postcode4" in response.json()


def test_an_unknown_field_is_refused_at_the_endpoint() -> None:
    response = APIClient().post(
        reverse("advice-estimate"), ESTIMATE | {"email": "a@b.nl"}, format="json"
    )
    assert response.status_code == 400


def test_a_second_identical_request_does_not_fetch_production_twice() -> None:
    """Definition of done, proven at the endpoint rather than at the provider."""
    client = APIClient()
    client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert ProductionCache.objects.count() == 1
    client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert ProductionCache.objects.count() == 1


def test_every_generated_advice_writes_exactly_one_audit_line() -> None:
    APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert AuditEvent.objects.filter(event_type="ADVICE_GENERATED").count() == 1


def test_the_audit_line_holds_no_personal_detail() -> None:
    APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    context = AuditEvent.objects.get().context
    assert context["postcode4"] == "5401"
    assert set(context) == {
        "token",
        "postcode4",
        "confidence",
        "engine_version",
        "advice_version",
    }


def test_the_stored_input_holds_only_what_was_asked() -> None:
    created = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    stored = StoredAdvice.objects.get(token=created["token"])
    assert set(stored.inputs) == set(ESTIMATE)


def test_the_twenty_first_computation_in_an_hour_is_refused() -> None:
    """Twenty an hour is generous for a real visit and too little to occupy the
    machine. This is the only test that proves the limit is switched on."""
    client = APIClient()
    codes = [
        client.post(reverse("advice-estimate"), ESTIMATE, format="json").status_code
        for _ in range(21)
    ]
    assert codes[:20] == [201] * 20, codes
    assert codes[20] == 429


def test_reading_a_link_is_allowed_far_more_often_than_computing_one() -> None:
    client = APIClient()
    token = client.post(reverse("advice-estimate"), ESTIMATE, format="json").json()["token"]
    codes = [client.get(reverse("advice-detail", args=[token])).status_code for _ in range(30)]
    assert set(codes) == {200}, "sharing a link must not hit the compute limit"


def test_no_endpoint_sets_a_cookie() -> None:
    """There is no session, so there is nothing to fixate and nothing to steal."""
    response = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert not response.cookies


def test_an_advice_arrives_within_a_second_once_production_is_cached() -> None:
    """Definition of done. The first request pays for the production series;
    every one after it is what a visitor actually experiences."""
    client = APIClient()
    client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    started = time.perf_counter()
    response = client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    elapsed = time.perf_counter() - started
    assert response.status_code == 201
    assert elapsed < CACHED_REQUEST_BUDGET_S, f"a cached advice took {elapsed:.3f}s"
