"""The four things CLAUDE.md asks of an opt-in, each on its own.

Two separate opt-ins, neither pre-ticked, each with its own timestamp in the
database, and a withdrawal that is recorded. Written as four tests rather than
one, because a single test that checks all four passes for the wrong reason as
soon as three of them hold.
"""

from __future__ import annotations

import pytest

from accounts.models import Consent, User
from accounts.nl import CONSENT_TEXT_VERSION


@pytest.fixture
def _account() -> User:
    return User.objects.create_user(email="iemand@voorbeeld.nl", password="een-lang-wachtwoord")


@pytest.mark.django_db
def test_the_two_consents_are_independent(_account: User) -> None:
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    assert Consent.current(_account, Consent.METER_LINK) is True
    assert Consent.current(_account, Consent.LEAD_GENERATION) is False


@pytest.mark.django_db
def test_never_asked_is_not_granted(_account: User) -> None:
    """Absence is the answer, and no row is written for a refusal. WITHDRAWN for
    something never granted would be an untruth in a table kept as evidence."""
    assert Consent.current(_account, Consent.METER_LINK) is False
    assert Consent.objects.filter(user=_account).count() == 0


@pytest.mark.django_db
def test_a_withdrawal_is_a_row_and_not_an_erasure(_account: User) -> None:
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    Consent.record(_account, Consent.METER_LINK, Consent.WITHDRAWN)
    assert Consent.current(_account, Consent.METER_LINK) is False
    assert Consent.objects.filter(user=_account, kind=Consent.METER_LINK).count() == 2


@pytest.mark.django_db
def test_consent_can_be_given_again_after_a_withdrawal(_account: User) -> None:
    """The reason this is an event table and not two nullable columns: a column
    that is filled twice cannot say what happened in between."""
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    Consent.record(_account, Consent.METER_LINK, Consent.WITHDRAWN)
    Consent.record(_account, Consent.METER_LINK, Consent.GRANTED)
    assert Consent.current(_account, Consent.METER_LINK) is True
    assert Consent.objects.filter(user=_account).count() == 3


@pytest.mark.django_db
def test_every_row_carries_its_own_timestamp_and_the_text_it_agreed_to(_account: User) -> None:
    """Article 7(1) asks to be able to demonstrate what was agreed to, and that
    cannot be demonstrated if the text has been reworded since."""
    row = Consent.record(_account, Consent.LEAD_GENERATION, Consent.GRANTED)
    assert row.occurred_at is not None
    assert row.occurred_at.tzinfo is not None
    assert row.text_version == CONSENT_TEXT_VERSION


@pytest.mark.django_db
def test_an_unknown_kind_is_refused_rather_than_created(_account: User) -> None:
    """A name outside the list cannot open a new column of behaviour, which is
    the same rule DailyCounter.CLIENT_NAMES applies to the funnel counters."""
    with pytest.raises(ValueError):
        Consent.record(_account, "SELL_MY_DATA", Consent.GRANTED)


@pytest.mark.django_db
def test_an_unknown_action_is_refused_rather_than_created(_account: User) -> None:
    """The same refusal, for the other half of the pair: a known kind with an
    action outside GRANTED and WITHDRAWN cannot open a third state either."""
    with pytest.raises(ValueError):
        Consent.record(_account, Consent.METER_LINK, "MAYBE")


def test_nothing_that_computes_an_advice_can_see_a_consent() -> None:
    """CLAUDE.md's neutrality rule, made mechanical.

    That rule says any code letting the advice depend on a commercial relation
    is a bug. The obvious test computes one advice with lead consent granted and
    one without and demands they match byte for byte, and that test is worth less
    than it looks: it passes for as long as nobody has written the coupling yet,
    and it is a slow test of a negative.

    This is the same claim stated where it can actually fail. The advice engine
    and the advice app must not so much as mention the consent vocabulary, so
    the coupling cannot be written without turning this red in the same diff.
    The two pure packages are included because the rule is about the advice and
    not about which layer it was spoiled in.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    # Case-sensitive on purpose: that is what lets AuditEvent's own
    # CONSENT_GRANTED / CONSENT_WITHDRAWN constants (all caps) live inside
    # advice/models.py without tripping this scan, while a literal `Consent`
    # or `LEAD_GENERATION` reference would not. The lowercase reverse accessor
    # Django generates for a FK, `user.consents`, would slip past all three
    # words the same way. No such path is reachable today: the advice views
    # this scan protects never receive a `user` at all, so there is nothing
    # for `.consents` to be called on. A future view that does gain a user
    # would need its own check.
    forbidden = ("Consent", "LEAD_GENERATION", "consent_lead")
    offenders = [
        f"{path.relative_to(root)}: {word}"
        for folder in ("backend/advice", "ampeer_advice", "ampeer_sim")
        for path in (root / folder).rglob("*.py")
        for word in forbidden
        if word in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "the advice side of this codebase now knows what a household consented to:\n  "
        + "\n  ".join(offenders)
        + "\nCLAUDE.md calls that a bug rather than a feature, and it holds whether or "
        "not any money has changed hands yet."
    )
