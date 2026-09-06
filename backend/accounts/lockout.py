"""Who axes is counting, without writing down who that is.

django-axes counts failed attempts per caller and per account name, and by
default it writes both into `AccessAttempt` rows with an `ip_address` column.
The handler in the settings keeps those tables from existing at all; these two
callables keep the values that end up in the cache key from being an address or
an email address either. Removing the tables and leaving the addresses in the
keys would have taken away the address book and left the addresses.

The caller identity is not computed here, it is asked of the throttle that
already answers that question. Two definitions of "the same visitor" that must
agree are one definition that eventually will not, and this one also inherits
`NUM_PROXIES`, which is the setting that decides whether the answer means
anything at all.
"""

from __future__ import annotations

from django.http import HttpRequest
from django.utils.crypto import salted_hmac
from rest_framework.request import Request

from advice.throttling import HashedIdentScopedRateThrottle

#: A namespace for `username`'s digest only, so it can never collide with
#: another use of SECRET_KEY. `client_ip` below does not use it: it reuses
#: `HashedIdentScopedRateThrottle`'s own digest instead of salting a second
#: one, which is a deliberate deviation from an earlier reading of spec 9.3
#: that had both callables salt with this constant. Task 12 corrects that
#: chapter to say so instead of leaving the deviation unlabelled.
KEY_SALT = "ampeer.accounts.lockout"

#: 128 bits of the digest, hex, like advice/throttling.py.
DIGEST_CHARS = 32

_THROTTLE = HashedIdentScopedRateThrottle()


def client_ip(request: HttpRequest) -> str:
    """What axes counts a caller as: the digest the rate limit already uses.

    Deliberately not `axes.helpers.get_client_ip_address`. That function reads
    `AXES_CLIENT_IP_CALLABLE` and calls it, so calling it from here would
    recurse until the stack ran out.
    """
    return _THROTTLE.get_ident(Request(request))


def username(request: HttpRequest, credentials: dict[str, object] | None) -> str:
    """What axes counts an account as, without holding the address.

    Lowered before hashing, and that is load bearing rather than tidy: the
    address is stored lowered, so a login attempt in other capitals has to
    produce the same digest or five attempts against one account count as five
    against two.
    """
    # `None`, "" and a non-`str` value all fall through to the same `raw = ""`
    # and therefore the same digest: every attempt axes cannot read a username
    # from shares one lockout bucket. Intended, not a gap: counting them
    # together still counts them, where refusing to count them at all would not.
    raw = ""
    if credentials:
        value = credentials.get("username", credentials.get("email", ""))
        if isinstance(value, str):
            raw = value.strip().lower()
    return salted_hmac(KEY_SALT, raw, algorithm="sha256").hexdigest()[:DIGEST_CHARS]
