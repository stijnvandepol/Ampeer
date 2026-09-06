"""Can the cache in production carry a lockout counter.

`AXES_HANDLER` is set to the cache handler so that no table with an
`ip_address` column ever exists, which is chapter 3.2 of the design. In
production that cache is `DatabaseCache` in Postgres, and Django does not
implement `incr` for it: `BaseCache.incr` reads and then writes, so two workers
that raise the same counter at the same moment lose one of the two.

That is measured here rather than assumed, and the question is deliberately not
"is it atomic". It is not. The question is whether the loss delays a lockout or
removes it, because only the second is a design fault. A counter that reaches
five after seven attempts instead of five still locks the account; a counter
that never reaches five does not.
"""

from __future__ import annotations

import threading

import pytest
from django.core.cache import caches
from django.db import connections
from django.test import override_settings

from ampeer.settings import base

#: Far past anything a real attacker gets through the rate limit in front of
#: this, and the point is to be far past it: if the property holds under an
#: absurd amount of contention it holds under a realistic amount.
CONCURRENT_WRITERS = 8
WRITES_PER_WORKER = 25

#: `AXES_FAILURE_LIMIT` in the settings. Written here as its own name rather
#: than imported, because this test has to keep meaning something if the
#: setting is raised, and the assertion below is about crossing a threshold
#: that a lockout uses, not about this particular number.
LOCKOUT_THRESHOLD = 5

DATABASE_CACHE = {
    "lockout": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        # Not the literal "ampeer_cache" a second time. base.py:114-117 warns
        # that two literals which must agree are one literal that eventually
        # will not, about this exact string and the migration that creates
        # the table it names.
        "LOCATION": base.AMPEER_CACHE_TABLE,
    }
}


def _bump(alias: str, key: str, times: int) -> None:
    """One worker's share of the increments, the way the cache handler does it."""
    cache = caches[alias]
    for _ in range(times):
        cache.set(key, (cache.get(key) or 0) + 1, 3600)
    for connection in connections.all():
        connection.close()


@pytest.mark.django_db(transaction=True)
@override_settings(CACHES=DATABASE_CACHE)
def test_the_database_cache_counts_a_sequential_run_exactly() -> None:
    """The half that has to be exact, and would make everything else moot."""
    caches["lockout"].delete("sequential")
    _bump("lockout", "sequential", CONCURRENT_WRITERS * WRITES_PER_WORKER)
    assert caches["lockout"].get("sequential") == CONCURRENT_WRITERS * WRITES_PER_WORKER


@pytest.mark.django_db(transaction=True)
@override_settings(CACHES=DATABASE_CACHE)
def test_a_lockout_threshold_is_still_crossed_under_contention() -> None:
    """What the design actually needs, and it is not exactness.

    The measured shortfall goes in docs/decisions.md rather than in an
    assertion, because it is a property of the machine and the moment. What is
    asserted is the pair of bounds that decide whether the cache handler is
    usable at all: the counter never overshoots, so nobody is locked out early,
    and it clears the threshold a lockout fires at, so nobody is not locked out.
    """
    total = CONCURRENT_WRITERS * WRITES_PER_WORKER
    caches["lockout"].delete("contended")
    workers = [
        threading.Thread(target=_bump, args=("lockout", "contended", WRITES_PER_WORKER))
        for _ in range(CONCURRENT_WRITERS)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    counted = caches["lockout"].get("contended")
    assert counted is not None, "the counter is gone entirely, which is not a race but a loss"
    assert counted <= total, (
        f"the counter reached {counted} out of {total} writes, which is more than were made. "
        "An overcounting lockout locks people out of their own accounts."
    )
    assert counted >= LOCKOUT_THRESHOLD, (
        f"{total} concurrent failed attempts moved the counter to {counted}, which is below "
        f"the {LOCKOUT_THRESHOLD} a lockout fires at. The cache handler cannot carry this "
        "counter and design chapter 3.2 has to be reopened."
    )
    print(
        f"\nMEASUREMENT 1: {counted} of {total} increments survived "
        f"{CONCURRENT_WRITERS} concurrent writers"
    )
