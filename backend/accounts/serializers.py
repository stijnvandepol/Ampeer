"""The only place an untrusted body becomes something this app acts on."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import Consent, User
from accounts.nl import NL

#: The one Django validator message whose shipped Dutch translation does not
#: match the text it actually raises; see `RegisterSerializer.validate_password`.
#: `%(min_length)d` matches the parameter Django's own
#: `MinimumLengthValidator` raises its `ValidationError` with.
_PASSWORD_TOO_SHORT_NL = "wachtwoord moet minimaal %(min_length)d tekens bevatten"


class LoginSerializer(serializers.Serializer[dict[str, Any]]):
    email = serializers.EmailField(error_messages={"invalid": NL["email_invalid"]})
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, error_messages={"required": NL["password_required"]}
    )

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class RegisterSerializer(LoginSerializer):
    #: No default on either, so a body that leaves one out is a 400 and never a
    #: silent True. Not pre-ticked is a property of this line.
    consent_meter_link = serializers.BooleanField()
    consent_lead_generation = serializers.BooleanField()

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError(NL["email_taken"])
        return normalized

    def validate_password(self, value: str) -> str:
        """Django's own validators, whose messages arrive in Dutch from
        Django's translations because `USE_I18N` is on (Django's own default,
        confirmed unset and therefore `True` anywhere in this project's
        settings) and `LANGUAGE_CODE = "nl-nl"` is enough on its own: reading
        `django.utils.translation.get_language()` with no `LocaleMiddleware`
        installed and no language ever activated already returns `"nl-nl"`.
        Verified directly against `django.contrib.auth.password_validation` in
        the installed Django 5.2.17: `NumericPasswordValidator`,
        `CommonPasswordValidator` and `UserAttributeSimilarityValidator` all
        translate correctly this way.

        `MinimumLengthValidator` is the one exception, and the earlier
        docstring here (before this fix round) was wrong about why: it is not
        a settings problem. `MinimumLengthValidator.get_error_message()`
        formats "...at least %d character(s)" with a positional placeholder,
        but the Dutch catalogue Django ships
        (`django/contrib/auth/locale/nl/LC_MESSAGES/django.po`) only
        translates the differently worded "...at least %(min_length)d
        character(s)" message that `get_help_text()` uses on a path this
        validator never takes. That mismatch is inside Django's own bundled
        translation data in this installed version, not something
        `USE_I18N`, `LANGUAGE_CODE` or a middleware can fix, so this one code
        is corrected by hand.

        `_PASSWORD_TOO_SHORT_NL` belongs in `accounts/nl.py` by this
        project's own convention; it is a module-level constant here instead
        because `nl.py` is task 5's file and outside this fix round's
        ownership. See the task 9 report for the follow-up this leaves.
        """
        try:
            validate_password(value)
        except DjangoValidationError as error:
            messages: list[str] = []
            for sub_error in error.error_list:
                if sub_error.code == "password_too_short" and sub_error.params:
                    messages.append(_PASSWORD_TOO_SHORT_NL % sub_error.params)
                else:
                    messages.extend(sub_error.messages)
            raise serializers.ValidationError(messages) from error
        return value

    @property
    def granted_kinds(self) -> list[str]:
        """The consents that were said yes to. A no yields nothing at all."""
        data = self.validated_data
        pairs = [
            (Consent.METER_LINK, data["consent_meter_link"]),
            (Consent.LEAD_GENERATION, data["consent_lead_generation"]),
        ]
        return [kind for kind, given in pairs if given]
