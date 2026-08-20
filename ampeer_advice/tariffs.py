"""National tariff values with a band, not a table per supplier.

Every figure here is a national value with an explicit low, mid and high, read
on a single date that is recorded beside it. There is deliberately no
per-supplier table.

The reason is the failure mode this whole project is built against. A
hand-maintained supplier table produces no error when it goes stale, only a
confident wrong number, and a household that acts on it has no way of telling.
A band cannot go stale silently in the same way: it carries its own spread, it
carries the date it was read, and the sensitivity analysis varies over it, so
the answer arrives with its uncertainty attached instead of without it. On top
of that the spread between suppliers is wide enough that a national mid with a
band informs a household more honestly than a point estimate that happens to
come from the wrong supplier.

The user may always override these with his own contract figures. These are the
values used when he does not.

Money is ``Decimal`` throughout, including the battery cost per kWh of
capacity, because it is a price and not an energy quantity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ampeer_sim.types import TariffSet

#: The date every value in this module was read from its source. A value that
#: changes without this date changing is a defect, and
#: ``tests/test_advice_tariffs.py`` fails on it.
SOURCED_ON = date(2026, 8, 20)

#: Bumped whenever any value above changes, for whatever reason. ``SOURCED_ON``
#: says when the sources were last read; this says when the numbers last moved.
#: Conflating the two forces a lie: a methodological correction is not a re-read,
#: and dating it as one would make the freshness of the table unverifiable.
#:
#: 1: first table, 2026-08-20.
#: 2: FEED_IN_COST.mid moved from 0.075 to 0.0625. The arithmetic midpoint of the
#:    observed charge range, paired with the midpoint of the compensation, gave a
#:    central net of -0.010 per kWh, which no supplier offers. The published net
#:    figures cluster at +0.0025, so the middle is now anchored on that. Sources
#:    unchanged.
VALUES_REVISION = 2

#: Levels accepted by :func:`scenario_2027_tariffs`, in order.
LEVELS = ("low", "mid", "high")


@dataclass(frozen=True)
class TariffBand:
    """A national value with a measured spread. All three in euro."""

    low: Decimal
    mid: Decimal
    high: Decimal

    def at(self, level: str) -> Decimal:
        """Return the value for ``level``, one of ``low``, ``mid`` or ``high``."""
        if level not in LEVELS:
            raise ValueError(f"level must be one of {LEVELS}, got {level!r}")
        value: Decimal = getattr(self, level)
        return value


#: All-in supply price in euro per kWh, energy plus energy tax plus VAT.
#: Source: energievergelijk and pure-energie overviews, read 2026-08-20.
SUPPLY_PRICE = TariffBand(low=Decimal("0.22"), mid=Decimal("0.26"), high=Decimal("0.30"))

#: Gross feed-in compensation on a fixed contract, euro per kWh, before feed-in
#: charges. The low end is the statutory floor: suppliers must pay at least 50
#: percent of the bare supply price until 2030. The high end is Eneco's
#: published 0.0766. Source: wettelijk minimum and supplier publications, read
#: 2026-08-20.
FEED_IN_GROSS_FIXED = TariffBand(low=Decimal("0.050"), mid=Decimal("0.065"), high=Decimal("0.077"))

#: The net figure published per supplier, euro per exported kWh, gross
#: compensation minus the feed-in charge. Directly observed rather than derived:
#: -0.0743 at Innova and GewoonEnergie, +0.0119 at Eneco, and most large
#: suppliers at +0.0025. Source: energievergelijk and keuze.nl overviews, read
#: 2026-08-20. Kept here because it is the quantity a household actually
#: experiences, and because it anchors the central case below.
PUBLISHED_NET_FEED_IN_MODE = Decimal("0.0025")

#: Feed-in charges in euro per exported kWh. Per kWh, not per year: the charge
#: falls hardest on the household with the largest array, which is the audience
#: this product is for. Source: keuze.nl overview per supplier, read 2026-08-20,
#: observed range 0.0446 to 0.115.
#:
#: The middle is 0.0625 rather than the arithmetic midpoint of that range. Taking
#: the midpoint of the charge independently of the midpoint of the compensation
#: produced a central net of -0.010 per kWh, a figure no supplier offers, while
#: the published net figures cluster at +0.0025. The middle is therefore anchored
#: so the net matches what is actually on offer: 0.065 - 0.0625 = 0.0025. The
#: observed range still sets the band, so the spread is unaffected and the
#: sensitivity analysis still reaches -0.076 to +0.047 per kWh.
#:
#: This correction moves the headline down. A central case that is more
#: pessimistic than the market makes the case for this product stronger, which
#: is exactly the direction an error must not be allowed to sit in.
FEED_IN_COST = TariffBand(low=Decimal("0.0446"), mid=Decimal("0.0625"), high=Decimal("0.115"))

#: Net feed-in compensation on a dynamic contract, euro per kWh. Net already:
#: suppliers of dynamic contracts settle at the hourly price and do not levy a
#: separate feed-in charge, so no cost is subtracted from this one. Source:
#: historical average hourly price over the solar hours, read 2026-08-20.
FEED_IN_NET_DYNAMIC = TariffBand(low=Decimal("0.05"), mid=Decimal("0.06"), high=Decimal("0.07"))

#: Installed home battery cost in euro per kWh of capacity, hardware plus
#: installation. Source: HuisAssist, 1KOMMA5 and thuisbatterijmagazine price
#: overviews, read 2026-08-20.
BATTERY_COST_PER_KWH = TariffBand(low=Decimal("450"), mid=Decimal("675"), high=Decimal("900"))


def net_feed_in_fixed(level: str = "mid") -> Decimal:
    """Net euro per exported kWh on a fixed contract: gross minus charges.

    This is the figure that corrects the project plan. The plan assumed 3 to 8
    cent per exported kWh, which is the gross compensation. After feed-in
    charges the net figure on a fixed contract is around zero and frequently
    negative, matching published net tariffs that run from -7.43 cent to +1.19
    cent. A model that cannot express a negative net feed-in has drifted back
    to the assumption the spec corrected.

    ``level`` selects the same position in both bands, so it names the position
    of the constituents and not the favourability of the outcome. At ``high``
    both the gross compensation and the charge are at their high end, and
    because the charge has the wider spread the net figure there is the most
    negative of the three. The sensitivity analysis varies the constituents
    independently for that reason.
    """
    return FEED_IN_GROSS_FIXED.at(level) - FEED_IN_COST.at(level)


def baseline_tariffs() -> TariffSet:
    """The situation before 2027: feed-in is netted against offtake.

    Standing charges are zero here and in :func:`scenario_2027_tariffs` on
    purpose. The headline figure is a difference between the two scenarios, so
    anything identical on both sides cancels. Leaving them out is not a
    simplification but a smaller surface for wrong assumptions: what remains
    are the three quantities that actually change between now and 2027.
    """
    return TariffSet(
        supply_price=SUPPLY_PRICE.mid,
        # Under net metering an exported kWh is worth an offtaken kWh, so the
        # feed-in price is the supply price by definition, not a separate rate.
        feed_in_price=SUPPLY_PRICE.mid,
        feed_in_cost_per_kwh=Decimal("0"),
        feed_in_fixed_cost_year=Decimal("0"),
        standing_charge_year=Decimal("0"),
        net_metering=True,
    )


def scenario_2027_tariffs(dynamic: bool = False, level: str = "mid") -> TariffSet:
    """The situation from 1 January 2027: no netting, and charges per exported kWh.

    On a fixed contract the household receives the gross compensation and pays
    the feed-in charge per exported kWh, which together can be negative. On a
    dynamic contract the compensation is already net of charges, so
    ``feed_in_cost_per_kwh`` stays zero and the whole difference between the
    two contract types shows up in the net figure.

    ``TariffSet.dynamic`` stays ``False`` even when ``dynamic=True``, because
    that flag means "price this against an hourly price series" and this module
    holds no such series. The dynamic contract is modelled here by its average
    net price over the solar hours. That is a coarser model, and it is the
    reason the dynamic figure is a band rather than a point.
    """
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}, got {level!r}")
    feed_in_price = FEED_IN_NET_DYNAMIC.at(level) if dynamic else FEED_IN_GROSS_FIXED.at(level)
    feed_in_cost = Decimal("0") if dynamic else FEED_IN_COST.at(level)
    return TariffSet(
        supply_price=SUPPLY_PRICE.at(level),
        feed_in_price=feed_in_price,
        feed_in_cost_per_kwh=feed_in_cost,
        feed_in_fixed_cost_year=Decimal("0"),
        standing_charge_year=Decimal("0"),
        net_metering=False,
    )


__all__ = [
    "BATTERY_COST_PER_KWH",
    "FEED_IN_COST",
    "FEED_IN_GROSS_FIXED",
    "FEED_IN_NET_DYNAMIC",
    "LEVELS",
    "PUBLISHED_NET_FEED_IN_MODE",
    "SOURCED_ON",
    "SUPPLY_PRICE",
    "VALUES_REVISION",
    "TariffBand",
    "baseline_tariffs",
    "net_feed_in_fixed",
    "scenario_2027_tariffs",
]
