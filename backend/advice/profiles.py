"""Which consumption profile this deployment uses.

There is exactly one, and there is deliberately no fallback. Every other
external source in this system degrades gracefully: PVGIS falls back to an
offline table built from nine measured years. A consumption profile has no such
table, because nobody has measured one that we may redistribute, and inventing
a shape would put a made-up number at the centre of every answer while every
test stayed green.

So a deployment without the NEDU file refuses to answer. That is worse service
and better honesty, and it keeps the licensing question visible instead of
letting a plausible curve paper over it.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings

from ampeer_sim.profiles.nedu import NeduFileProvider
from ampeer_sim.providers import ProfileProvider


def profile_provider() -> ProfileProvider:
    configured = getattr(settings, "AMPEER_NEDU_PROFILE_PATH", None)
    if not configured:
        raise RuntimeError(
            "AMPEER_NEDU_PROFILE_PATH is not set; refusing to answer with an "
            "invented consumption profile"
        )
    path = Path(configured)
    if not path.exists():
        raise RuntimeError(f"AMPEER_NEDU_PROFILE_PATH does not exist: {path}")
    return NeduFileProvider(path)
