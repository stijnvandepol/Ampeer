"""The one place the halves are put together.

Nothing above this file knows what a Household is, and nothing below it knows
what an HTTP request is. That separation is why the simulation core can be
validated without a database and without a server, which matters because it is
the only part of this system where a fault produces a plausible wrong number
rather than an error message.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.conf import settings

from advice.assembly import (
    build_battery_spec,
    build_household,
    build_pv_system,
    build_tariffs,
    build_year,
)
from advice.models import AuditEvent, DailyCounter, StoredAdvice, token_digest
from advice.production import production_provider
from advice.profiles import profile_provider
from advice.rendering import render
from advice.serializers import year_field
from ampeer_advice.advise import advise
from ampeer_sim.simulate import run_advice
from ampeer_sim.timebase import YearGrid

if TYPE_CHECKING:  # pragma: no cover - typing only
    # Type only, so `advice` gains no runtime dependency on `accounts`.
    # The field is a ForeignKey to settings.AUTH_USER_MODEL and this is
    # what that resolves to; naming it here keeps the annotation honest
    # without the import existing when the module runs.
    from accounts.models import User


def compute_and_store(
    data: dict[str, Any],
    question_count: int,
    *,
    owner: User | None = None,
    consumption_measured: bool = False,
) -> dict[str, Any]:
    """Run the engine for one set of answers, store the result, log the event.

    ``question_count`` is the number of questions the form asked, not the number
    of values it produced. Round one asks four and yields five, because
    orientation and tilt are one question about one roof. Passing the value
    count would push every estimate over the GOOD threshold and delete the
    distinction the confidence label exists to make.
    """
    weather_year: int = settings.AMPEER_WEATHER_YEAR
    grid = YearGrid.for_year(settings.AMPEER_PROFILE_YEAR)
    profiles = profile_provider()
    production = production_provider(weather_year)

    household = build_household(data)
    system = build_pv_system(data)
    battery_spec = build_battery_spec(data)
    baseline, scenario, dynamic_scenario = build_tariffs(data)

    result = run_advice(
        household=household,
        pv_system=system,
        baseline=baseline,
        scenario=scenario,
        grid=grid,
        profile_provider=profiles,
        production_provider=production,
        battery_spec=battery_spec,
        weather_year=weather_year,
    )
    advice = advise(
        household=household,
        pv_system=system,
        scenario=scenario,
        grid=grid,
        profile_provider=profiles,
        production_provider=production,
        result=result,
        filled_fields=question_count,
        consumption_measured=consumption_measured,
        dynamic_contract=bool(data.get("dynamic_contract", False)),
        battery_spec=battery_spec,
        dynamic_scenario=dynamic_scenario,
        weather_year=weather_year,
    )

    # The row is created before the payload exists because the token is part of
    # the payload. Rendering first and storing afterwards would mean either a
    # second token or a response that does not carry the link it promises.
    stored = StoredAdvice.create(inputs=data, advice={})
    # The three steps the year takes, and each of them is a different question.
    #
    # `build_year` reads the engine's flows and stamps where they came from,
    # which is a fact about the input and not a parameter. `year_field` decides
    # whether a series with that stamp may leave at all, and it is asked here
    # rather than trusted: this row is opened by a bearer token with no account
    # behind it, so the answer for a measured series is no, and the default
    # says so without this call site having to remember it. `render` only
    # places the result under a key.
    #
    # The row exists by now, which is why the refusal is worth having on this
    # path rather than only in a unit test. If `year_field` ever raises here,
    # the request fails with the row still holding an empty advice, so nothing
    # a stranger could open was written down. That is the behaviour under test
    # in tests/test_advice_series.py.
    payload = render(
        advice,
        result,
        token=stored.token,
        year=year_field(build_year(advice.flows)),
        # What the visitor typed, so the response can say whether the year it
        # modelled is that figure or that figure plus a car and a heat pump.
        # See decision 26: the question now asks for consumption without them,
        # and this is what makes a visitor who entered their bill total anyway
        # able to notice.
        entered_consumption_kwh=float(data["annual_consumption_kwh"]),
        consumption_measured=consumption_measured,
    )
    stored.advice = payload
    # The owner arrives here and nowhere else. An anonymous advice keeps none,
    # which is what `StoredAdvice.get_live` is written to serve; an advice asked
    # for through a session gets one, and with it the CASCADE on account
    # deletion and the row in the article 15 export that both already existed
    # and had nothing to act on.
    stored.owner = owner
    stored.save(update_fields=["advice", "owner"])

    # Context without a personal detail: a digest of the token so the record
    # stays correlatable, and the postcode area so a later question about
    # coverage can be answered. No IP address: this log records what the service
    # did, not who visited.
    #
    # The digest and not the token. The token is not a reference to the advice,
    # it is the only credential that opens it, and this table is deliberately
    # undeletable, so a plaintext token here outlives the ninety day purge as a
    # permanent row holding a working link to a record that was supposed to be
    # gone. Hashing keeps everything the log is for: anyone holding a token can
    # hash it and find the line, and the line still says what the service did.
    AuditEvent.record(
        AuditEvent.ADVICE_GENERATED,
        token_sha256=token_digest(stored.token),
        postcode4=data["postcode4"],
        confidence=payload["confidence"],
        engine_version=payload["engine_version"],
        advice_version=payload["advice_version"],
    )
    _count_outcome(payload)
    return payload


def _count_outcome(payload: dict[str, Any]) -> None:
    """Aggregate counters for what this product actually told people.

    Written here rather than accepted from the browser, because this is the one
    distribution a product whose charter makes refusing a battery a valid and
    required outcome would be tempted to flatter, and a number a caller can move is not evidence of
    anything. Nothing recorded here can be traced to a visit: the counters are
    a date, a name and an integer, and every advice of the same shape on the
    same day is the same increment.

    The battery verdict is read out of the rules that fired rather than off a
    separate field, so it cannot disagree with the sentence the household was
    shown.
    """
    DailyCounter.bump(DailyCounter.ADVICE_GENERATED)
    DailyCounter.bump(f"confidence_{payload['confidence']}".lower())
    for route in payload.get("routes", ()):
        for rule in route.get("rules", ()):
            rule_id = rule.get("rule_id", "")
            if rule_id.startswith("BATTERY_") or rule_id == "CONSIDER_BATTERY":
                DailyCounter.bump(f"verdict_{rule_id}".lower())
