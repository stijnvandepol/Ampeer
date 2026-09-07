"""The only place an untrusted body becomes something this app acts on."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import Consent, User
from accounts.nl import CONSENT_TEXT_VERSION, NL


def password_error_messages(error: DjangoValidationError) -> list[str]:
    """Django's validator messages, with the one that its Dutch catalogue
    cannot translate corrected by hand.

    Lifted out of `RegisterSerializer.validate_password` so the reset route
    translates a refusal with the same words as registration: two copies of
    this mapping would be two places the sentence can drift. The reason the
    mapping exists at all is in that method's docstring.
    """
    messages: list[str] = []
    for sub_error in error.error_list:
        if sub_error.code == "password_too_short" and sub_error.params:
            messages.append(NL["password_too_short"] % sub_error.params)
        else:
            messages.extend(sub_error.messages)
    return messages


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

    #: The version whose text the visitor actually read, sent back so it can be
    #: compared with the one `Consent.record` is about to stamp. Required here:
    #: a registration with no version is a form that showed a sentence from
    #: somewhere else, or none at all.
    text_version = serializers.CharField()

    def validate_text_version(self, value: str) -> str:
        if value != CONSENT_TEXT_VERSION:
            raise serializers.ValidationError(NL["consent_text_stale"])
        return value

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

        The mapping itself lives in `password_error_messages` above, because
        `ResetConfirmView` needs the same words.
        """
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(password_error_messages(error)) from error
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

    #: Not required, and that asymmetry is article 7(3) rather than a
    #: convenience: a withdrawal may never be harder than a grant, so the field
    #: is ignored entirely when the action is WITHDRAWN.
    text_version = serializers.CharField(required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["action"] != Consent.GRANTED:
            return attrs
        if attrs.get("text_version") != CONSENT_TEXT_VERSION:
            # Absent and wrong, answered by one comparison. Either way the
            # client did not send the version it displayed, and the reader's
            # next move is the same: reload the page.
            raise serializers.ValidationError({"text_version": NL["consent_text_stale"]})
        return attrs


class ResetRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """One field, and the view answers the same whatever it is."""

    email = serializers.EmailField(error_messages={"invalid": NL["email_invalid"]})


class TokenSerializer(serializers.Serializer[dict[str, Any]]):
    """The token off a link. A missing or empty one reads as an invalid one:
    the difference between "you sent nothing" and "you sent something old" is
    a difference only somebody probing the route would learn from."""

    token = serializers.CharField(
        trim_whitespace=False,
        error_messages={
            "required": NL["token_invalid"],
            "blank": NL["token_invalid"],
            "null": NL["token_invalid"],
        },
    )


class ResetConfirmSerializer(TokenSerializer):
    #: Not validated here: the validators need the user, and the user is
    #: only known once the token has been looked up under its lock. See
    #: recovery.confirm_password_reset.
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, error_messages={"required": NL["password_required"]}
    )
