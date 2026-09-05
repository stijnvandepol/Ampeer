"""The only place an untrusted body becomes something this app acts on."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import Consent, User
from accounts.nl import NL


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

        `MinimumLengthValidator` is the one exception, and it is not a
        settings problem. Django's shipped Dutch catalogue
        (`django/contrib/auth/locale/nl/LC_MESSAGES/django.po:274-284`) does
        contain a "too short" translation, keyed to the
        `"...at least %(min_length)d character(s)"` wording that
        `get_help_text()` raises. `get_error_message()`, the method
        `validate()` actually calls, formats a *different* string,
        `"...at least %d character(s)"` with a bare positional `%d`, which
        matches no msgid in that catalogue. That mismatch is inside Django's
        own bundled translation data in this installed version, not
        something `USE_I18N`, `LANGUAGE_CODE` or a middleware can fix, so
        `NL["password_too_short"]` corrects this one code by hand rather than
        passing `error.messages` straight through.
        """
        try:
            validate_password(value)
        except DjangoValidationError as error:
            messages: list[str] = []
            for sub_error in error.error_list:
                if sub_error.code == "password_too_short" and sub_error.params:
                    messages.append(NL["password_too_short"] % sub_error.params)
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


class ConsentSerializer(serializers.Serializer[dict[str, Any]]):
    """One consent, one action, and no field that names a user.

    The user comes off `request.user` and can therefore not be chosen by the
    caller. That is object level permissions expressed as an absence, which is
    stronger than a check: there is nothing to check because there is nothing to
    send.
    """

    kind = serializers.ChoiceField(
        choices=sorted(Consent.KINDS), error_messages={"invalid_choice": NL["consent_kind_unknown"]}
    )
    action = serializers.ChoiceField(
        choices=sorted(Consent.ACTIONS),
        error_messages={"invalid_choice": NL["consent_action_unknown"]},
    )
