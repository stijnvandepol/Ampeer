"""The aggregate counters, and the properties that keep them harmless.

Phase 0 of this product exists to validate whether the question exists at all,
and until 2026-09-02 nothing measured that. These tests hold the smallest thing
that can measure it to the shape that makes it safe: a date, a name out of a
fixed list, and an integer, with nothing in the table that belongs to anybody.

Every test here needs a database. On a machine with no Postgres they error on
connection rather than fail, and they are decided in CI, which is the
arrangement scripts/gates.sh describes.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from advice.models import DailyCounter


@pytest.mark.django_db
def test_the_first_event_of_the_day_creates_a_row_and_the_second_adds_to_it() -> None:
    DailyCounter.bump(DailyCounter.FUNNEL_STARTED)
    DailyCounter.bump(DailyCounter.FUNNEL_STARTED)
    row = DailyCounter.objects.get(day=timezone.localdate(), name=DailyCounter.FUNNEL_STARTED)
    assert row.count == 2


@pytest.mark.django_db
def test_two_names_do_not_share_a_row() -> None:
    DailyCounter.bump(DailyCounter.FUNNEL_STARTED)
    DailyCounter.bump(DailyCounter.FUNNEL_SUBMITTED)
    assert DailyCounter.objects.count() == 2


@pytest.mark.django_db
def test_the_table_holds_no_column_that_could_belong_to_a_visitor() -> None:
    """The safety of this table is its shape, not a policy about its use.

    Read from the database rather than from the model, because a column added
    by a later migration is exactly the change this is here to catch.
    """
    DailyCounter.bump(DailyCounter.FUNNEL_STARTED)
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM advice_dailycounter LIMIT 1")
        columns = {column[0] for column in cursor.description}
    assert columns == {"id", "day", "name", "count"}, (
        f"advice_dailycounter has columns beyond a date, a name and a number: {sorted(columns)}"
    )


@pytest.mark.django_db
def test_the_endpoint_counts_a_known_name() -> None:
    response = APIClient().post(
        reverse("advice-count"), {"name": DailyCounter.FUNNEL_QUESTION_2}, format="json"
    )
    assert response.status_code == 204
    assert response.content == b""
    assert DailyCounter.objects.get(name=DailyCounter.FUNNEL_QUESTION_2).count == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        "verdict_consider_battery",
        "advice_generated",
        "confidence_indicative",
        "something_invented",
        "",
    ],
)
def test_the_endpoint_refuses_a_name_it_does_not_publish(name: str) -> None:
    """Including every server-written name.

    The outcome distribution is the one number a product built on "nu geen
    batterij is a valid outcome" would be tempted to flatter, so it is written
    by the server from what it decided and cannot be moved from outside. A
    caller sending `verdict_consider_battery` must be refused exactly as one
    sending nonsense is.
    """
    response = APIClient().post(reverse("advice-count"), {"name": name}, format="json")
    assert response.status_code == 400
    assert not DailyCounter.objects.filter(name=name).exists()


@pytest.mark.django_db
def test_a_name_that_is_not_a_string_is_refused_rather_than_crashing() -> None:
    for payload in ({"name": 1}, {"name": None}, {"name": ["a"]}, {}):
        response = APIClient().post(reverse("advice-count"), payload, format="json")
        assert response.status_code == 400, payload
    assert not DailyCounter.objects.exists()


def test_no_client_name_overlaps_a_server_prefix() -> None:
    """The two sets are what keeps the outcome numbers unforgeable.

    Needs no database: it is a property of the two lists. If a funnel name ever
    started with a server prefix, the endpoint above would accept a name the
    server also writes, and the distribution would stop being evidence.
    """
    for name in DailyCounter.CLIENT_NAMES:
        assert not name.startswith(DailyCounter.SERVER_PREFIXES), (
            f"{name} is accepted from the browser and collides with a server prefix"
        )
    assert DailyCounter.ADVICE_GENERATED not in DailyCounter.CLIENT_NAMES
