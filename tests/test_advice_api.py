"""The three endpoints, end to end, against a real database.

These are the only tests that run the whole thing: validation, the engine, the
cache, storage and rendering. The engine is real; only the two external sources
are replaced, and production is replaced by the offline table this project
already ships rather than by a stub, so what these tests exercise is what a
visitor gets when PVGIS is down.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pytest
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
