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
        """Django's own validators, whose messages arrive in Dutch from Django's
        translations because LANGUAGE_CODE is nl-nl. That keeps four sentences
        out of nl.py without putting any Dutch in the logic."""
        try:
            validate_password(value)
        except DjangoValidationError as error:
            raise serializers.ValidationError(list(error.messages)) from error
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
