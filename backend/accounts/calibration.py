"""Propose a corrected annual consumption from a household's own meter.

The orchestration only. The arithmetic is ``ampeer_sim.fit``, which knows
nothing about Django, and the rows are ``accounts.window``, which knows nothing
about the fit. This module is the one place that holds both, and it holds them
for exactly one question: does this household's meter contradict the annual
figure it typed.

Nothing here is stored. A proposal describes the meter as it is at the moment
it is asked for, not a property of the advice it accompanies, and the accepting
route recomputes it from the inputs that were stored rather than trusting a
figure written down earlier. That costs one more fit on a route nobody takes
twice, and it buys two things: the accepted figure is always the current one,
and the acceptance re-asks whether the meter still disagrees at all.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.utils import timezone

from accounts.models import MeterLink, User
from accounts.nl import NL
from accounts.window import build_window
from advice.assembly import build_household, build_pv_system
from advice.models import StoredAdvice
from advice.production import production_provider
from advice.profiles import profile_provider
from ampeer_sim.fit import ConsumptionFit, fit_annual_consumption
from ampeer_sim.timebase import YearGrid
from ampeer_sim.validate import DEFAULT_TOLERANCE_PERCENT

#: When the export the model produces is far enough from the meter's own that
#: the installation, rather than the consumption, is the thing described
#: wrongly. Borrowed from the validation tool rather than chosen here, so one
#: number decides what "far" means for both.
EXPORT_TOLERANCE = DEFAULT_TOLERANCE_PERCENT / 100.0


def propose_correction(user: User, data: dict[str, Any]) -> ConsumptionFit | None:
    """Return a fit worth telling this household about, or nothing.

    Nothing covers four different situations on purpose, because a household
    that has not linked a meter, one that linked it this morning, one whose
    meter cannot be reconciled at all, and one whose meter agrees with what
    they typed all deserve the same thing from this route: silence.
    """
    link = MeterLink.active_for(user)
    if link is None:
        return None

    grid = YearGrid.for_year(settings.AMPEER_PROFILE_YEAR)
    window = build_window(link, grid)
    if window is None:
        return None

    weather_year: int = settings.AMPEER_WEATHER_YEAR
    fit = fit_annual_consumption(
        household=build_household(data),
        pv_system=build_pv_system(data),
        grid=grid,
        window=window,
        profile_provider=profile_provider(),
        production_provider=production_provider(weather_year),
        weather_year=weather_year,
    )
    if fit is None or not fit.contradicts(float(data["annual_consumption_kwh"])):
        return None
    return fit


def as_payload(fit: ConsumptionFit, typed_kwh: float) -> dict[str, Any]:
    """The proposal as the account page receives it.

    The band travels with the figure rather than behind it. A single corrected
    number is exactly what this project refuses to put in front of a household,
    and here it would be worse than usual: the band is also the reason this
    proposal exists at all, since a typed figure inside it would have produced
    no proposal.
    """
    return {
        "typed_kwh": round(typed_kwh, 1),
        "p10_kwh": round(fit.p10_kwh, 1),
        "p50_kwh": round(fit.p50_kwh, 1),
        "p90_kwh": round(fit.p90_kwh, 1),
        "runs": fit.runs,
        "quarters_used": fit.quarters_used,
        # Every sentence the household reads is built here and not in the
        # browser. `frontend/e2e/language.spec.ts` enforces that boundary: a
        # line of interface text may name the shape of a figure, and it may
        # never be a sentence about the household's electricity. All three of
        # these are the second kind.
        "measured_over": NL["consumption_correction_measured_over"].format(
            quarters=fit.quarters_used, runs=fit.runs
        ),
        "accept_label": NL["consumption_correction_accept"].format(kwh=round(fit.p50_kwh)),
        "keep_own": NL["consumption_correction_keep"],
        "message": NL["consumption_correction"].format(
            typed=round(typed_kwh), low=round(fit.p10_kwh), high=round(fit.p90_kwh)
        ),
        # Present only when it has something to say. The fit matched import, so
        # a disagreeing export is the one thing in this answer that points at
        # the installation rather than at the consumption, and a household that
        # described its roof wrongly should hear that instead of accepting a
        # consumption figure carrying the error.
        "installation_note": (
            None
            if fit.export_deviation.within(EXPORT_TOLERANCE)
            else NL["consumption_correction_export_off"]
        ),
    }


def latest_check(user: User) -> tuple[StoredAdvice, ConsumptionFit] | None:
    """The correction worth showing beside this household's meter, if any.

    Read off their most recent advice rather than off a figure of its own,
    because a fit needs a described household: a roof, an orientation and
    whichever assets were declared. That description only exists as the inputs
    of an advice they already asked for.

    Filtered on the owner, and only among advices that have not expired. An
    advice whose ninety days ran out cannot be recomputed under its token
    either, so proposing a correction to it would offer a button that could
    not work.
    """
    stored = (
        StoredAdvice.objects.filter(owner=user, expires_at__gt=timezone.now())
        .order_by("-created_at")
        .first()
    )
    if stored is None:
        return None
    fit = propose_correction(user, dict(stored.inputs))
    return None if fit is None else (stored, fit)
