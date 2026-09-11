"""Dutch text for the account layer, keyed by an English id.

Same idea as `advice/nl.py` one app over, applied to a second vocabulary, and
the two never import each other. That file's rule applies to one category
here and not to the whole table: a validation message names a field and says
what is wrong with it, and addresses nobody. A message that said "vul uw
e-mailadres in" would be a sentence somebody is spoken to in, and then
docs/decisions.md entry 1 about the register applies. `email_taken`,
`email_invalid`, `credentials_invalid`, `password_required`, `csrf_failed`,
`consent_kind_unknown`, `consent_action_unknown`, `consent_text_stale`,
`token_invalid`, `throttled` and `throttled_unknown_wait` are this category. `consent_text_stale`
names the `text_version` field and says nothing about a typed value, only
that the page behind it is too old. `meter_token_invalid`, `meter_not_allowed`,
`meter_reading_invalid` and `meter_batch_too_large`, added with the meter
link, are this category too: each names what is wrong (the key, the account,
the reading, the batch) and addresses nobody.
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
instead of them, so it necessarily addresses them. `not_signed_in`,
`session_expired` and `forbidden` are this category, and "u bent niet
ingelogd" is correct Dutch for what it says rather than an exception to the
rule above.

The consent texts are a third category, and deliberately so: those are
sentences to a household, so they do use "u". They also carry a version,
because article 7(1) of the GDPR asks to be able to demonstrate what was
agreed to, and a reworded text with no version makes that impossible to
answer afterwards. The two `CONSENT_LABEL_` entries belong to this category
too since 2026-09-06: a label is the heading a row is shown under, it is read
together with its text, and decision 38 records the rule for editing one: a
label may narrow what it says only as far as the text still covers, and it
may never claim less than the row records. Both are under the same version
as the texts, so a label edit bumps it exactly as a text edit does.

A fourth category is the mail. `MAIL_RESET_SUBJECT`, `MAIL_RESET_BODY`,
`MAIL_VERIFY_SUBJECT` and `MAIL_VERIFY_BODY` are letters to a household, so
they address the reader with "u", and they carry no version because nothing
is recorded against them. Plain text with one placeholder, `%(link)s`, that
the sending command fills in. Written without accents on "een uur" and "een
keer", the way the first category writes them, because a mail client shows
plain text as it arrives.
"""

from __future__ import annotations

from typing import Final

#: Bumped whenever any CONSENT_ text or CONSENT_LABEL_ entry below is
#: reworded, never otherwise. The value is stored on every Consent row, so a
#: bump changes what new rows claim and leaves the old ones pointing at what
#: they actually agreed to. A label counts because label and text are read
#: together and recorded together; see decision 38 in docs/decisions.md.
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
    "forbidden": "u mag dit niet doen",
    "csrf_failed": "deze pagina stond te lang open, herlaad hem en probeer het opnieuw",
    "throttled": "te veel verzoeken achter elkaar; probeer het over %(seconds)d seconden opnieuw",
    "throttled_unknown_wait": "te veel verzoeken achter elkaar; probeer het straks opnieuw",
    "consent_text_stale": (
        "de toestemmingstekst is gewijzigd, herlaad de pagina en probeer het opnieuw"
    ),
    "consent_kind_unknown": "onbekende toestemming",
    "consent_action_unknown": "onbekende handeling",
    "token_invalid": "deze link is verlopen of al gebruikt; vraag een nieuwe aan",
    "meter_token_invalid": "deze sleutel hoort niet bij een actieve koppeling",
    "meter_not_allowed": (
        "koppelen kan pas met een bevestigd e-mailadres en toestemming voor de slimme meter"
    ),
    "meter_reading_invalid": (
        "een meting moet op een heel kwartier staan en kan niet negatief zijn"
    ),
    "meter_batch_too_large": "er kunnen ten hoogste honderd metingen per bericht mee",
    "consumption_correction": (
        "U gaf {typed} kWh per jaar op. Over de periode die uw meter heeft doorgegeven "
        "komen wij uit op {low} tot {high} kWh per jaar. Dat is meer verschil dan wij "
        "aan een ingetypt getal toerekenen, dus wij leggen het aan u voor in plaats van "
        "het zelf te veranderen."
    ),
    "consumption_correction_export_off": (
        "Wat u teruglevert komt niet goed overeen met wat wij voor uw installatie "
        "berekenen. Dat wijst eerder op de beschrijving van uw panelen, zoals het "
        "vermogen of de richting, dan op uw verbruik. Controleer die eerst."
    ),
    "consumption_correction_gone": (
        "Uw meter spreekt het opgegeven verbruik niet langer tegen, dus er valt nu "
        "niets te corrigeren."
    ),
    "advice_not_found": "dit advies bestaat niet of hoort niet bij uw account",
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
    "CONSENT_LABEL_METER_LINK": "Kwartiergegevens van uw slimme meter",
    "CONSENT_LABEL_LEAD_GENERATION": "Doorgeven aan een installateur",
    "MAIL_RESET_SUBJECT": "Uw wachtwoord bij Ampeer herstellen",
    "MAIL_RESET_BODY": (
        "U heeft gevraagd om een nieuw wachtwoord voor uw account bij Ampeer.\n"
        "\n"
        "Open deze link om een nieuw wachtwoord te kiezen. De link werkt een uur en kan een keer\n"
        "gebruikt worden:\n"
        "\n"
        "%(link)s\n"
        "\n"
        "Heeft u dit niet gevraagd, dan hoeft u niets te doen. Uw wachtwoord blijft zoals het was.\n"
        "\n"
        "Op dit bericht kunt u niet antwoorden.\n"
    ),
    "MAIL_VERIFY_SUBJECT": "Bevestig uw e-mailadres bij Ampeer",
    "MAIL_VERIFY_BODY": (
        "Met dit e-mailadres is een account bij Ampeer aangemaakt.\n"
        "\n"
        "Open deze link om te bevestigen dat dit adres van u is. De link werkt zeven dagen:\n"
        "\n"
        "%(link)s\n"
        "\n"
        "Heeft u geen account aangemaakt, dan heeft iemand anders uw adres ingevuld. U hoeft niets te\n"
        "doen: zonder bevestiging kan dat account geen slimme meter koppelen.\n"
        "\n"
        "Op dit bericht kunt u niet antwoorden.\n"
    ),
}
