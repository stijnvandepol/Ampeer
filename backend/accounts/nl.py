"""Dutch text for the account layer, keyed by an English id.

Same idea as `advice/nl.py` one app over, applied to a second vocabulary, and
the two never import each other. That file's rule applies to one category
here and not to the whole table: a validation message names a field and says
what is wrong with it, and addresses nobody. A message that said "vul uw
e-mailadres in" would be a sentence somebody is spoken to in, and then
docs/decisions.md entry 1 about the register applies. `email_taken`,
`email_invalid`, `credentials_invalid`, `password_required`, `csrf_failed`,
`consent_kind_unknown`, `consent_action_unknown`, `consent_text_stale`,
`throttled` and `throttled_unknown_wait` are this category. `consent_text_stale`
names the `text_version` field and says nothing about a typed value, only
that the page behind it is too old.
`password_too_short` is one of them too, and it is the first entry in this
table to carry a `%(...)` placeholder: the caller formats it with a value it
alone knows (the configured minimum length), so the string here stays a
template and not a hardcoded number. `throttled` is a second: it is phrased
the way `csrf_failed` is, an instruction addressed to nobody, and its
`%(seconds)d` is filled in with the same `wait` DRF used to build
`Retry-After`, never rounded a second, different way. `wait` can be `None`;
`throttled_unknown_wait` is a plain second sentence for that case rather
than one template trying to read naturally both with and without a number,
which would need a placeholder that is sometimes a digit and sometimes a
phrase.

A second category is not about a field at all: it tells the reader something
about their own session or sign-in state, and there is no field to name
instead of them, so it necessarily addresses them. `not_signed_in` and
`session_expired` are this category, and "u bent niet ingelogd" is correct
Dutch for what it says rather than an exception to the rule above.

The consent texts are a third category, and deliberately so: those are
sentences to a household, so they do use "u". They also carry a version,
because article 7(1) of the GDPR asks to be able to demonstrate what was
agreed to, and a reworded text with no version makes that impossible to
answer afterwards.
"""

from __future__ import annotations

from typing import Final

#: Bumped whenever any CONSENT_ text below is reworded, never otherwise. The
#: value is stored on every Consent row, so a bump changes what new rows claim
#: and leaves the old ones pointing at what they actually agreed to.
CONSENT_TEXT_VERSION: Final = "2026-09-04"

NL: Final[dict[str, str]] = {
    "email_taken": "er bestaat al een account met dit e-mailadres",
    "email_invalid": "geen geldig e-mailadres",
    "credentials_invalid": "e-mailadres of wachtwoord klopt niet",
    #: B105 matches this dict key's name, not a credential: the value is Dutch UI copy.
    "password_required": "wachtwoord ontbreekt",  # nosec B105
    #: `MinimumLengthValidator.get_error_message()` (in
    #: django.contrib.auth.password_validation) raises "...at least %d
    #: character(s)" with a bare, positional `%d`. Django's own shipped
    #: catalogue (django/contrib/auth/locale/nl/LC_MESSAGES/django.po:274-284)
    #: does contain a Dutch "too short" translation, but keyed to the
    #: differently formatted "...at least %(min_length)d character(s)" that
    #: only `get_help_text()` raises, on a path this validator never takes, so
    #: the message actually raised never matches a Dutch msgid in that
    #: catalogue. See accounts/serializers.py::RegisterSerializer.validate_password
    #: and the task 9 report for the full diagnosis.
    #: B105 matches this dict key's name, not a credential: the value is Dutch UI copy.
    "password_too_short": "wachtwoord moet minimaal %(min_length)d tekens bevatten",  # nosec B105
    "not_signed_in": "u bent niet ingelogd",
    "session_expired": "uw sessie is verlopen, log opnieuw in",
    "csrf_failed": "deze pagina stond te lang open, herlaad hem en probeer het opnieuw",
    "throttled": "te veel verzoeken achter elkaar; probeer het over %(seconds)d seconden opnieuw",
    "throttled_unknown_wait": "te veel verzoeken achter elkaar; probeer het straks opnieuw",
    "consent_text_stale": (
        "de toestemmingstekst is gewijzigd, herlaad de pagina en probeer het opnieuw"
    ),
    "consent_kind_unknown": "onbekende toestemming",
    "consent_action_unknown": "onbekende handeling",
    "CONSENT_METER_LINK": (
        "Ik geef Ampeer toestemming om de kwartiergegevens van mijn slimme meter te "
        "verwerken om mijn advies nauwkeuriger te maken. Ik kan deze toestemming op elk "
        "moment intrekken."
    ),
    "CONSENT_LEAD_GENERATION": (
        "Ik geef Ampeer toestemming om mijn gegevens door te geven aan een installateur "
        "als ik daar zelf om vraag. Dit is niet nodig om Ampeer te gebruiken en het "
        "verandert niets aan het advies dat ik krijg."
    ),
}
