"""The three endpoints, end to end, against a real database.

These are the only tests that run the whole thing: validation, the engine, the
cache, storage and rendering. The engine is real; only the two external sources
are replaced, and production is replaced by the offline table this project
already ships rather than by a stub, so what these tests exercise is what a
visitor gets when PVGIS is down.
"""

from __future__ import annotations

import base64
import json
import re
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from advice.models import AuditEvent, ProductionCache, StoredAdvice, token_digest
from advice.production import CachedProductionProvider
from advice.serializers import MAX_REPORTED_UNKNOWN_FIELDS
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


#: The five keys of the optional `year` object, written out rather than read
#: from the serializer that declares them. This is the API's side of a contract
#: another codebase builds against, and a contract test that reads both sides
#: from the same object agrees with whatever that object became.
YEAR_KEYS = {"own", "meter", "ceilings", "provenance", "quarters"}


def _the_same_year_run_independently() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ESTIMATE's household simulated here, without going through the service.

    Assembled from the same builders and the same offline providers the request
    uses, but composed in this file, so what it can catch is a wiring fault:
    the wrong flows carried out of `advise`, two series swapped on the way to
    the encoder, or the household that took the free advice being drawn instead
    of the one the visitor described. It is deliberately not a second
    implementation of the engine, which is what `tests/test_golden.py` is for.
    """
    from advice.assembly import build_household, build_pv_system, year_series
    from ampeer_sim.engine.run import simulate
    from ampeer_sim.production.model import production_series
    from ampeer_sim.profiles.compose import compose_consumption

    weather_year = settings.AMPEER_WEATHER_YEAR
    grid = YearGrid.for_year(settings.AMPEER_PROFILE_YEAR)
    household = build_household(ESTIMATE)
    system = build_pv_system(ESTIMATE)

    watts, temperature, _source = FallbackProvider(weather_year).hourly_series(
        household.postcode4, system.azimuth_deg, system.tilt_deg
    )
    production = production_series(watts, system, grid, weather_year=weather_year)
    consumption = compose_consumption(
        household,
        grid,
        FlatProfileProvider().fractions(grid.year, household.profile_category),
        temperature,
        weather_year=weather_year,
        production_kwh=production,
    )
    return year_series(simulate(consumption, production))


def test_an_estimate_carries_the_whole_year_and_says_where_it_came_from() -> None:
    """The field on the wire, from a real request over HTTP.

    Until 2026-08-27 nothing emitted this key: the format, the serializer and
    the refusal all existed and no producer handed them anything, so every
    check on it ran on an object a test had built. This is the request a
    visitor makes.
    """
    response = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")
    assert response.status_code == 201, response.data

    year = response.json()["year"]
    assert set(year) == YEAR_KEYS
    assert set(year["ceilings"]) == {"own", "export", "grid"}
    assert year["provenance"] == "SYNTHETIC"
    assert year["quarters"] == YearGrid.for_year(settings.AMPEER_PROFILE_YEAR).quarters

    # One byte per quarter per array, which is the sentence the frontend
    # allocates against. Read off the decoded bytes and not off the base64.
    assert len(base64.b64decode(year["own"])) == year["quarters"]
    assert len(base64.b64decode(year["meter"])) == year["quarters"]


def test_the_year_on_the_wire_is_this_household_and_not_a_different_one() -> None:
    """What the bytes add up to, against the engine run outside the service.

    The ceilings are the maxima of the three series, so they are the cheapest
    figure to compare and the one a wiring fault moves first: swapping export
    and offtake, or carrying out the counterfactual year the free routes are
    measured on, changes them by tens of percent.

    Not compared exactly, and the reason is a finding rather than a tolerance
    chosen for comfort. `compute_and_store` calls `run_advice` before it calls
    `advise`, and the first of those fills the production cache, which stores
    the series as float32 because PVGIS reports three significant digits.
    `advise` therefore reads the roof back through that round trip while the
    headline band beside it was computed on the float64 series, so the two
    halves of one answer already run on production series that differ in the
    eighth digit. Measured on 2026-08-27 on ESTIMATE: the export ceiling is
    0.4557944370301161 here and 0.45579442304417456 on the wire, a relative
    3e-8. The tolerance below is 1e-6, which is thirty times that and five
    orders of magnitude tighter than anything a wiring fault could hide in.
    """
    own, export, grid = _the_same_year_run_independently()
    served = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()["year"]

    assert served["ceilings"] == pytest.approx(
        {
            "own": float(own.max()),
            "export": float(export.max()),
            "grid": float(grid.max()),
        },
        rel=1e-6,
    )


def test_the_real_route_refuses_a_measured_series_rather_than_storing_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The privacy control, reached the way phase 2 will reach it.

    `advice.assembly.build_year` stamps SYNTHETIC because that is what phase
    0.5 can honestly say. In phase 2 the meter coupling is a second source and
    a builder that knows about it, and that builder is the thing patched in
    here: everything downstream of it is the code that ships today.

    What is asserted is the whole shape of the refusal, not only that
    something raised. The request fails; the row that was opened before the
    payload existed still holds an empty advice; and the token route, which
    filters nothing and is pinned elsewhere in this file to return what is
    stored verbatim, therefore has no measured series to hand to whoever the
    link reaches.
    """
    from advice.assembly import year_series
    from advice.series import MEASURED, MeasuredSeriesRefused, encode_year

    def measured(flows: Any) -> Any:
        return encode_year(*year_series(flows), provenance=MEASURED)

    monkeypatch.setattr("advice.service.build_year", measured)

    with pytest.raises(MeasuredSeriesRefused, match=MEASURED):
        APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json")

    stored = StoredAdvice.objects.get()
    assert stored.advice == {}, "a refused advice left something readable behind"
    fetched = APIClient().get(reverse("advice-detail", args=[stored.token]))
    assert fetched.status_code == 200
    assert "year" not in fetched.json()


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


@pytest.mark.django_db
def test_ownership_adds_and_takes_nothing_away(client: Any) -> None:
    """The property phase 2 will be under pressure to break.

    An advice that belongs to somebody stays readable on its token, and an
    advice that belongs to nobody keeps working exactly as it did. Ownership is
    an addition; it is not a filter on the route that already exists, and
    `StoredAdvice.get_live` is deliberately unchanged.
    """
    from accounts.models import User
    from advice.models import StoredAdvice

    anonymous = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={"token": "x"})
    owned = StoredAdvice.create(inputs={"postcode4": "5401"}, advice={"token": "y"})
    owned.owner = User.objects.create_user(
        email="iemand@voorbeeld.nl", password="een-lang-wachtwoord"
    )
    owned.save(update_fields=["owner"])

    assert anonymous.owner is None
    for stored in (anonymous, owned):
        response = client.get(f"/api/advice/{stored.token}/")
        assert response.status_code == 200, (
            f"an advice with owner={stored.owner_id} answers {response.status_code} on its token"
        )


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
        "token_sha256",
        "postcode4",
        "confidence",
        "engine_version",
        "advice_version",
    }


def test_the_audit_line_holds_a_digest_and_never_the_token_itself() -> None:
    """The token is not a reference to the advice, it is the only credential
    that opens it, and this table is deliberately undeletable. A plaintext
    token here would therefore outlive the ninety day purge as a permanent row
    holding a working link to a record that was supposed to be gone.

    The digest keeps what the log is for. Whoever legitimately holds the link
    can hash it and find the line.
    """
    created = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()
    context = AuditEvent.objects.get().context
    assert created["token"] not in json.dumps(context)
    assert context["token_sha256"] == token_digest(created["token"])


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


@pytest.mark.perf
def test_an_advice_arrives_within_a_second_once_production_is_cached() -> None:
    """Definition of done. The first request pays for the production series;
    every one after it is what a visitor actually experiences.

    Marked `perf`, so it runs in its own uninstrumented invocation rather than
    inside the coverage run. Coverage makes this request about three times
    slower, which measured the budget against the profiler instead of against
    the promise, and left the check flipping between runs on one commit. The
    budget itself is unchanged: relaxing it was never the repair.
    """
    client = APIClient()
    client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    started = time.perf_counter()
    response = client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    elapsed = time.perf_counter() - started
    assert response.status_code == 201
    assert elapsed < CACHED_REQUEST_BUDGET_S, f"a cached advice took {elapsed:.3f}s"


def test_a_rotating_forwarded_for_header_does_not_buy_a_new_rate_limit() -> None:
    """The bypass this endpoint had, as a test.

    DRF's ScopedRateThrottle builds its key from `get_ident`, and with
    NUM_PROXIES unset that method returns the entire client supplied
    X-Forwarded-For header. Every request with a different header was therefore
    a different client: measured on 2026-08-21, forty requests this way
    produced zero 429s. This test fails if NUM_PROXIES is removed from the
    settings again, which is the only reason it is worth having.
    """
    client = APIClient()
    codes = [
        client.post(
            reverse("advice-estimate"),
            ESTIMATE,
            format="json",
            HTTP_X_FORWARDED_FOR=f"203.0.113.{index}",
        ).status_code
        for index in range(21)
    ]
    assert codes[:20] == [201] * 20, codes
    assert codes[20] == 429, "a spoofed header bought a fresh rate limit"


#: What Firefox and Chrome send on a plain navigation. It asks for HTML first
#: and accepts anything at q=0.8, which is what makes a JSON only API answer it
#: rather than refuse it.
BROWSER_ACCEPT = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
)


def test_a_browser_opening_a_shared_link_gets_json_and_not_a_500() -> None:
    """The core flow of this product is a link that somebody shares, and a link
    is opened in a browser. DRF's default renderer list holds
    BrowsableAPIRenderer, which renders a Django template, and TEMPLATES is
    empty, so Accept: text/html raised TemplateDoesNotExist and every such
    visit answered 500."""
    token = APIClient().post(reverse("advice-estimate"), ESTIMATE, format="json").json()["token"]
    response = APIClient().get(reverse("advice-detail", args=[token]), HTTP_ACCEPT=BROWSER_ACCEPT)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("application/json")
    assert response.json()["token"] == token


def test_a_browser_accept_header_on_a_computation_is_json_too() -> None:
    response = APIClient().post(
        reverse("advice-estimate"), ESTIMATE, format="json", HTTP_ACCEPT=BROWSER_ACCEPT
    )
    assert response.status_code == 201
    assert response["Content-Type"].startswith("application/json")


#: 200 kB of opening brackets. Well formed as far as the tokenizer is
#: concerned, and deep enough that json.load exhausts the interpreter's
#: recursion limit rather than reaching the end of the input.
DEEPLY_NESTED_BODY = b"[" * 200_000


def test_a_body_too_deeply_nested_to_parse_is_a_bad_request() -> None:
    """json.load raises RecursionError, and DRF's JSONParser catches only the
    errors it raises for malformed input, so this answered 500 instantly and
    from a 200 kB body. It is an ordinary bad request and it says so."""
    response = APIClient().post(
        reverse("advice-estimate"), DEEPLY_NESTED_BODY, content_type="application/json"
    )
    assert response.status_code == 400
    assert "genest" in json.dumps(response.json())


def test_a_body_that_is_merely_malformed_is_still_a_bad_request() -> None:
    """The parser above wraps DRF's, so the ordinary case has to keep working."""
    response = APIClient().post(
        reverse("advice-estimate"), b"{not json", content_type="application/json"
    )
    assert response.status_code == 400


def test_no_advice_response_may_be_written_down_by_anything_in_between() -> None:
    """Each of these describes one household's consumption and its bill. A
    shared proxy that kept a copy would hand the next caller on that address
    somebody else's figures, and the 400 is included because it echoes the
    rejected answers back."""
    client = APIClient()
    created = client.post(reverse("advice-estimate"), ESTIMATE, format="json")
    responses = [
        created,
        client.get(reverse("advice-detail", args=[created.json()["token"]])),
        client.get(reverse("advice-detail", args=["A" * 22])),
        client.post(reverse("advice-estimate"), ESTIMATE | {"postcode4": "0999"}, format="json"),
    ]
    assert [r.status_code for r in responses] == [201, 200, 404, 400]
    for response in responses:
        assert response["Cache-Control"] == "private, no-store", response.status_code


def test_an_error_about_unknown_fields_does_not_repeat_the_whole_request_back() -> None:
    """Naming the offending field is why unknown fields are refused rather than
    dropped, but the list came from the caller: a megabyte of distinct keys was
    echoed back as roughly two and a half megabytes of JSON, so the endpoint
    amplified whatever it was sent. Ten names and a count."""
    unknown = {f"veld{index:03d}": 1 for index in range(50)}
    response = APIClient().post(reverse("advice-estimate"), ESTIMATE | unknown, format="json")
    assert response.status_code == 400
    body = response.json()
    named = [key for key in body if key.startswith("veld")]
    assert len(named) == MAX_REPORTED_UNKNOWN_FIELDS
    assert named == sorted(unknown)[:MAX_REPORTED_UNKNOWN_FIELDS]
    assert body[api_settings.NON_FIELD_ERRORS_KEY] == ["en nog 40 onbekende velden"]
    assert len(response.content) < len(json.dumps(unknown))


def test_a_short_list_of_unknown_fields_is_still_reported_in_full() -> None:
    """The cap must not cost the message it exists to protect. One typo has to
    come back as that one field name and nothing about a remainder."""
    response = APIClient().post(
        reverse("advice-estimate"), ESTIMATE | {"postcode": "5401"}, format="json"
    )
    assert response.json() == {"postcode": "onbekend veld"}


#: Anything with an @ between two runs of non-space that ends in a domain-like
#: suffix. Deliberately loose: this is a tripwire, not a validator, and a false
#: positive here is a question worth answering.
EMAIL_PATTERN = re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}")

#: A whole Dutch postcode: four digits and two letters, with or without the
#: space. Four digits alone is the deliberate limit; the two letters are what
#: turn a neighbourhood into a street.
FULL_POSTCODE_PATTERN = re.compile(r"\b[1-9][0-9]{3}\s?[A-Za-z]{2}\b")

#: No answer a visitor gives and no audit context value is prose. The longest
#: legitimate string in either is the 64 character token digest, and none of
#: them contains a space. A value that breaks either rule is free text, and
#: free text is how a name or an address would arrive in a JSON column that no
#: schema constrains.
MAX_ANSWER_LENGTH = 64


def _strings(value: object, path: str = "") -> Iterator[tuple[str, str]]:
    """Every string in a decoded JSON structure, with the path that reached it.

    Keys are walked as well as values: a smuggled field arrives as a key first,
    and an "email" key inside a JSONField is exactly the case a test over
    Model._meta.get_fields() cannot see.
    """
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}", str(key)
            yield from _strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{path}[{index}]")


def test_nothing_stored_anywhere_looks_like_a_person() -> None:
    """Section 11.3 of the design, over the values rather than the field list.

    The two older tests here walk `Model._meta.get_fields()`, which is fixed at
    import time and can therefore never contain `email` no matter what a
    request carries. This one walks what a request actually put in the row.

    The length and whitespace rules apply to `inputs` and to the audit context
    and not to `advice`, because advice sentences are prose by design and are
    written in ampeer_advice.nl rather than by a caller.
    """
    APIClient().post(reverse("advice-refine"), REFINE, format="json")
    stored = StoredAdvice.objects.get()
    context = AuditEvent.objects.get().context

    for label, blob in (("inputs", stored.inputs), ("advice", stored.advice), ("audit", context)):
        for path, text in _strings(blob):
            assert not EMAIL_PATTERN.search(text), f"{label}{path} looks like an email: {text!r}"
            assert not FULL_POSTCODE_PATTERN.search(text), (
                f"{label}{path} looks like a full postcode: {text!r}"
            )

    for label, blob in (("inputs", stored.inputs), ("audit", context)):
        for path, text in _strings(blob):
            assert not any(character.isspace() for character in text), (
                f"{label}{path} holds whitespace, so it is prose: {text!r}"
            )
            assert len(text) <= MAX_ANSWER_LENGTH, (
                f"{label}{path} is {len(text)} characters, so it is free text: {text!r}"
            )


@pytest.mark.django_db
class TestTheBrowserIsAllowedToReadTheAnswer:
    """CORS, tested with an Origin header, because that is the whole gap.

    This API had no CORS at all until 2026-08-21, and nothing noticed. The
    reason is worth keeping: Playwright stubs every advice route so it never
    talks to Django, and DRF's APIClient sends no Origin and enforces no
    same-origin policy, so every test here passed against a server that would
    have had its answers withheld by every real browser. A test that does not
    send an Origin cannot see a missing Access-Control-Allow-Origin.

    The visitor's symptom would have been "controleer uw verbinding" on a
    perfectly good connection, and the GET path is worse than the POST: it is a
    simple request, so it reaches the server, spends one of the visitor's 120
    reads an hour, computes an answer, and the browser drops it.
    """

    ALLOWED = "http://localhost:3000"

    def test_a_preflight_from_the_frontend_is_answered(self) -> None:
        """The POSTs send content-type: application/json, which is outside the
        CORS safelist, so a browser preflights them. An unanswered OPTIONS is a
        request that never happens."""
        response = APIClient().options(
            reverse("advice-estimate"),
            HTTP_ORIGIN=self.ALLOWED,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
        )
        assert response.status_code == 200, response.status_code
        assert response["access-control-allow-origin"] == self.ALLOWED
        assert "POST" in response["access-control-allow-methods"]
        assert "content-type" in response["access-control-allow-headers"].lower()

    def test_a_computed_advice_carries_the_header_the_browser_needs(self) -> None:
        response = APIClient().post(
            reverse("advice-estimate"), ESTIMATE, format="json", HTTP_ORIGIN=self.ALLOWED
        )
        assert response.status_code == 201, response.data
        assert response["access-control-allow-origin"] == self.ALLOWED

    def test_reading_a_stored_advice_carries_it_too(self) -> None:
        """The GET is a simple request, so without the header the work is done
        and then thrown away by the browser. That costs the visitor a read from
        their hourly budget and shows them nothing."""
        client = APIClient()
        token = client.post(reverse("advice-estimate"), ESTIMATE, format="json").json()["token"]
        response = client.get(reverse("advice-detail", args=[token]), HTTP_ORIGIN=self.ALLOWED)
        assert response.status_code == 200
        assert response["access-control-allow-origin"] == self.ALLOWED

    def test_a_page_nobody_allowed_gets_no_header(self) -> None:
        """The half that makes the other three mean something. A wildcard would
        pass every assertion above and let any page on the internet read a
        household's figures out of this API."""
        response = APIClient().post(
            reverse("advice-estimate"),
            ESTIMATE,
            format="json",
            HTTP_ORIGIN="https://ergens-anders.example",
        )
        assert "access-control-allow-origin" not in response

    def test_no_cookie_crosses_the_boundary(self) -> None:
        """There is no session on this API, so there is nothing to send. Saying
        so in a test means a later view cannot start relying on one quietly."""
        response = APIClient().post(
            reverse("advice-estimate"), ESTIMATE, format="json", HTTP_ORIGIN=self.ALLOWED
        )
        assert response.get("access-control-allow-credentials") != "true"


@pytest.mark.django_db
class TestTheReadinessCheck:
    """A container with a bad profile mount used to start, report healthy, and
    fail every request.

    prod.py requires AMPEER_NEDU_PROFILE_PATH to be set, not for the file
    behind it to exist, and profile_provider() is only called when an advice is
    computed. So the process came up, the orchestrator was satisfied, and the
    product was a hundred percent broken while looking like it ran. The
    healthcheck has to open the thing a bad mount breaks.
    """

    def test_readiness_is_ok_when_the_profile_can_be_opened(self, tmp_path: Path) -> None:
        profile = tmp_path / "nedu.csv"
        profile.write_text("stub", encoding="utf-8")
        with override_settings(AMPEER_NEDU_PROFILE_PATH=str(profile)):
            response = APIClient().get(reverse("advice-health"))
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_readiness_fails_when_the_profile_is_not_there(self) -> None:
        with override_settings(AMPEER_NEDU_PROFILE_PATH="/does/not/exist.csv"):
            response = APIClient().get(reverse("advice-health"))
        assert response.status_code == 503

    def test_readiness_fails_when_the_path_was_never_set(self) -> None:
        with override_settings(AMPEER_NEDU_PROFILE_PATH=None):
            response = APIClient().get(reverse("advice-health"))
        assert response.status_code == 503

    def test_readiness_says_nothing_about_why(self) -> None:
        """A health endpoint is unauthenticated and reachable from anywhere the
        service is. The path on disk is not something it should hand out.

        The status code is asserted first and not as decoration. Without it
        this test passes against a view that answers 200 to everything, since
        an ok body holds no path either, and a test that cannot fail for the
        reason it exists is worse than no test.
        """
        with override_settings(AMPEER_NEDU_PROFILE_PATH="/srv/secret/place.csv"):
            response = APIClient().get(reverse("advice-health"))
        assert response.status_code == 503
        body = response.content.decode()
        assert "secret" not in body and "srv" not in body

    def test_readiness_computes_nothing_and_touches_no_database(
        self, django_assert_num_queries: Any
    ) -> None:
        """A healthcheck that runs every thirty seconds and does real work is a
        load generator with a nice name."""
        with django_assert_num_queries(0):
            APIClient().get(reverse("advice-health"))


#: A documentation address, used as the visitor's. It is the one that was read
#: out of a live throttle row on 2026-08-21:
#: `:1:throttle_advice-read_203.0.113.7` -> `[1787314695.73]`, which is "this
#: address was here at these times".
VISITOR_ADDRESS = "203.0.113.7"


def _throttle_for(scope: str) -> Any:
    """The throttle class that actually runs, from the settings.

    Instantiated through DEFAULT_THROTTLE_CLASSES rather than imported by name,
    so this fails if the setting is pointed back at a class that keys on the
    address.
    """
    # api_settings resolves the dotted paths in the setting into classes; the
    # stubs still describe the setting as it is written.
    throttle_classes: list[Any] = list(api_settings.DEFAULT_THROTTLE_CLASSES)
    (throttle_class,) = throttle_classes
    throttle = throttle_class()
    throttle.scope = scope
    return throttle


def _cache_key_for(address: str, scope: str = "advice-read") -> str:
    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    request = Request(APIRequestFactory().get("/", REMOTE_ADDR=address))
    key: str = _throttle_for(scope).get_cache_key(request, object())
    return key


def test_the_throttle_key_is_not_the_visitors_address() -> None:
    """The finding, at the one line that produces it.

    DRF's SimpleRateThrottle builds `throttle_<scope>_<ident>` and stores the
    timestamps of that ident's requests against it. With the ident left as the
    address, the counter is a visitor log: "this address was here at these
    times", which is the pairing AuditEvent documents itself as refusing to
    make, two tables away in the same database.
    """
    key = _cache_key_for(VISITOR_ADDRESS)
    assert VISITOR_ADDRESS not in key, key
    assert "203.0.113" not in key, key


def test_two_visitors_still_get_two_counters() -> None:
    """The half that makes the hash a fix rather than a way to switch the limit
    off. One bucket for everybody is not a rate limit, it is an outage."""
    assert _cache_key_for("203.0.113.7") != _cache_key_for("203.0.113.8")


def test_the_same_visitor_gets_the_same_counter_in_every_worker() -> None:
    """Three gunicorn workers must agree on who this is.

    A salt generated when the module is imported would satisfy every assertion
    above and give each worker its own counter, which is the LocMemCache defect
    the store was moved into Postgres to remove, wearing a different hat. There
    is one process here, so reimporting the module is what stands in for a
    second worker starting.
    """
    import importlib

    from rest_framework.request import Request
    from rest_framework.test import APIRequestFactory

    first = _cache_key_for(VISITOR_ADDRESS)
    module = importlib.reload(importlib.import_module("advice.throttling"))
    other_worker = module.HashedIdentScopedRateThrottle()
    other_worker.scope = "advice-read"
    request = Request(APIRequestFactory().get("/", REMOTE_ADDR=VISITOR_ADDRESS))
    assert other_worker.get_cache_key(request, object()) == first


def test_the_identity_is_keyed_and_not_merely_hashed() -> None:
    """An IPv4 address is 32 bits.

    A bare digest of one is reversible by trying all four billion of them,
    which is seconds of work, so an unkeyed hash in a database somebody can
    read is the address written down in a costume. The key is SECRET_KEY, which
    prod.py requires from the environment and never defaults.
    """
    with override_settings(SECRET_KEY="a-different-deployments-key"):
        other = _cache_key_for(VISITOR_ADDRESS)
    assert other != _cache_key_for(VISITOR_ADDRESS)


def test_nothing_in_the_throttle_store_holds_the_address() -> None:
    """Read back out of the store rather than reasoned about.

    The test settings use LocMemCache and production uses Postgres, but the
    keys and the values written are the same in both, which is the whole reason
    a live row could be quoted at all. `_cache` is the entire store, keyed as
    the backend keys it.
    """
    import pickle

    from django.core.cache import cache

    client = APIClient()
    client.post(reverse("advice-estimate"), ESTIMATE, format="json", REMOTE_ADDR=VISITOR_ADDRESS)
    client.get(reverse("advice-detail", args=["A" * 22]), REMOTE_ADDR=VISITOR_ADDRESS)

    store = dict(cache._cache)  # type: ignore[attr-defined]
    assert store, "no throttle entry was written at all, so this proves nothing"
    for key, pickled in store.items():
        assert VISITOR_ADDRESS not in key, key
        assert VISITOR_ADDRESS not in str(pickle.loads(pickled)), key


def test_the_counter_still_lives_in_the_shared_cache() -> None:
    """Where it is, not merely that it works.

    A throttle that kept its history on the instance would pass the per-visitor
    test above inside one process and count nothing across three workers or
    across a deploy. This reads the count back out of the cache the settings
    configure, by the key the throttle itself produces, which is exactly what a
    second worker does.
    """
    from django.core.cache import cache

    client = APIClient()
    for _ in range(3):
        client.get(reverse("advice-detail", args=["A" * 22]), REMOTE_ADDR=VISITOR_ADDRESS)
    history = cache.get(_cache_key_for(VISITOR_ADDRESS))
    assert history is not None, "the throttle wrote nothing into the shared cache"
    assert len(history) == 3, history
    assert all(isinstance(stamp, float) for stamp in history), history


def test_the_rate_limit_is_still_counted_per_visitor() -> None:
    """End to end, through the endpoint, with two addresses.

    Hashing the identity must not merge visitors and must not stop counting.
    """
    client = APIClient()
    codes = [
        client.post(
            reverse("advice-estimate"), ESTIMATE, format="json", REMOTE_ADDR=VISITOR_ADDRESS
        ).status_code
        for _ in range(21)
    ]
    assert codes[:20] == [201] * 20, codes
    assert codes[20] == 429
    neighbour = client.post(
        reverse("advice-estimate"), ESTIMATE, format="json", REMOTE_ADDR="203.0.113.8"
    )
    assert neighbour.status_code == 201, "one visitor's traffic exhausted another's budget"


class TestWhatAFiveHundredIsAllowedToWriteDown:
    """There was no LOGGING setting at all, so an unhandled exception in
    production produced no output anywhere.

    Django's default routes `django.request` errors to `mail_admins`, and its
    console handler carries `require_debug_true`. With DEBUG off that is a
    500 with no line in any log: measured on 2026-08-21, two 500s, zero lines.
    During an outage the whole evidence base is a status code in an access log.

    The obvious fix is the trap. Django's own message is
    `"Internal Server Error: %s" % request.path`, so a plain console handler
    writes `/api/advice/<token>/` into the container log on the first day, and
    the container log is the file nginx.conf and entrypoint-api.sh both go out
    of their way to keep the token out of.
    """

    @pytest.fixture
    def written(self) -> Iterator[Any]:
        """Whatever the configured handlers actually put on their stream."""
        import io
        import logging

        logger = logging.getLogger("django")
        # pytest attaches handlers of its own to every non-propagating logger,
        # so that caplog and the "Captured log" report keep working. They are
        # the test harness, not this service's log, and one of them formats
        # with pytest's own formatter: leaving them in would put the request
        # path into this stream and make the assertions below pass or fail on
        # pytest's behaviour rather than on the setting under test.
        handlers: list[logging.StreamHandler[Any]] = [
            handler
            for handler in logger.handlers
            if not type(handler).__module__.startswith("_pytest")
            and isinstance(handler, logging.StreamHandler)
        ]
        assert handlers, "the django logger has no handler: a 500 writes nothing"
        for handler in handlers:
            assert isinstance(handler, logging.StreamHandler), (
                f"{type(handler).__name__} is attached to the django logger, and this "
                "test can only read a stream. Django's own default puts AdminEmailHandler "
                "here, which sends the request path to whoever is in ADMINS."
            )
        stream = io.StringIO()
        originals = [(handler, handler.stream) for handler in handlers]
        for handler in handlers:
            handler.stream = stream
        try:
            yield stream
        finally:
            for handler, original in originals:
                handler.stream = original

    def _explode(self, monkeypatch: pytest.MonkeyPatch, message: str) -> None:
        def boom(token: str) -> None:
            raise RuntimeError(message)

        monkeypatch.setattr(StoredAdvice, "get_live", staticmethod(boom))

    def test_an_unhandled_error_is_recorded_at_all(
        self, monkeypatch: pytest.MonkeyPatch, written: Any
    ) -> None:
        self._explode(monkeypatch, "the database went away")
        response = APIClient(raise_request_exception=False).get(
            reverse("advice-detail", args=["A" * 22])
        )
        assert response.status_code == 500
        text = written.getvalue()
        assert text.strip(), "a 500 wrote nothing, anywhere"
        assert "RuntimeError" in text, text
        assert "test_advice_api.py" in text, text
        assert "line " in text, text

    def test_the_recorded_error_cannot_carry_the_token_or_the_address(
        self, monkeypatch: pytest.MonkeyPatch, written: Any
    ) -> None:
        """Three routes into the log line, all closed.

        Django's own message is the request path. The exception's message is
        whatever raised it, and a psycopg IntegrityError's message quotes the
        offending key verbatim. `record.args` carries the path a second time.
        """
        token = "TESTtokenTESTtoken0000"
        self._explode(monkeypatch, f"duplicate key (token)=({token}) from {VISITOR_ADDRESS}")
        response = APIClient(raise_request_exception=False).get(
            reverse("advice-detail", args=[token]), REMOTE_ADDR=VISITOR_ADDRESS
        )
        assert response.status_code == 500
        text = written.getvalue()
        assert text.strip(), "a 500 wrote nothing, anywhere"
        assert token not in text, text
        assert VISITOR_ADDRESS not in text, text
        assert "/api/advice/" not in text, text

    def test_a_refused_request_cannot_write_the_token_either(
        self, monkeypatch: pytest.MonkeyPatch, written: Any
    ) -> None:
        """`django.request` logs 4xx as well, with the same path in the message,
        and a 404 on a shared link is the most ordinary event on this service."""
        token = "TESTtokenTESTtoken0000"
        APIClient().get(reverse("advice-detail", args=[token]))
        assert token not in written.getvalue(), written.getvalue()
