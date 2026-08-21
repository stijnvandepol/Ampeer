"""Who the rate limit is counting, without writing down who that is.

DRF's throttles key their counter on the caller's identity and store, against
that key, the timestamps of that caller's requests. With the identity left as
the address, one row of the counter reads

    :1:throttle_advice-read_203.0.113.7  ->  [1787314695.73]

which is "this address was here at these times". That is a visitor log, and it
is the exact pairing `AuditEvent` documents itself as refusing to make, two
tables away in the same database. It is also durable in a way nobody chose:
`DatabaseCache` deletes an expired row only when that same key is read again,
so a visitor who never returns leaves a row behind indefinitely.

The counter itself has to stay. A rate limit has to be per visitor and shared
across the three gunicorn workers, which is why prod.py puts the store in
Postgres rather than in a per-process dict. What does not have to stay is the
address: the throttle never reads the identity back, it only compares it, so a
value that is stable per visitor and means nothing to a reader does the whole
job.
"""

from __future__ import annotations

from django.utils.crypto import salted_hmac
from rest_framework.request import Request
from rest_framework.throttling import ScopedRateThrottle

#: A namespace, so this digest can never collide with another use of
#: SECRET_KEY. Django's own signing helpers take one for the same reason.
KEY_SALT = "ampeer.advice.throttling.HashedIdentScopedRateThrottle"

#: 128 bits of the digest, hex. Enough that two visitors sharing a counter is
#: not a thing to plan for, and short enough that the cache key stays well
#: under the 250 character limit Django warns about.
IDENT_DIGEST_CHARS = 32


class HashedIdentScopedRateThrottle(ScopedRateThrottle):
    """ScopedRateThrottle that counts per visitor without naming one.

    Keyed, not merely hashed. An IPv4 address is 32 bits, so a bare SHA-256 of
    one is reversible by trying all four billion of them, which is seconds of
    work on a laptop: an unkeyed digest in a database somebody can read is the
    address written down in a costume. `salted_hmac` keys on SECRET_KEY, which
    prod.py requires from the environment and never defaults, so a database
    dump on its own says nothing about who was where.

    The digest is not per process and not per period. Both would satisfy every
    privacy assertion and quietly break the limit: a per-process salt gives
    each of the three workers its own counter, which is the LocMemCache defect
    the store was moved into Postgres to remove, and a per-period salt hands
    out a fresh budget at every boundary.
    """

    def get_ident(self, request: Request) -> str:
        """The caller's identity, as something only this deployment can match.

        Overridden here rather than in `get_cache_key`, because both the scoped
        and the anonymous throttle build their key from this one method, so a
        later throttle class added beside this one inherits the property
        instead of having to remember it.
        """
        ident = super().get_ident(request)
        return salted_hmac(KEY_SALT, ident or "", algorithm="sha256").hexdigest()[
            :IDENT_DIGEST_CHARS
        ]
