"""The consent texts the frontend is built against, produced by the real table.

The same arrangement as advice_fixture.py one file over, for the one auth
response that touches no database: there is one function, it reads nl.py, and
both this generator and tests/test_frontend_contract.py go through it. A
fixture written by hand is a description of a response that may never have
existed, and for these two sentences that is worse than usual: the whole
guarantee in chapter 5 of the design is that what a household reads and what
the Consent row records are one string.

Run as a script to rewrite the fixture:

    uv run --no-sync python tests/helpers/consent_texts_fixture.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE = REPO_ROOT / "frontend" / "tests" / "fixtures" / "consent-texts.json"

# backend/ is a Django project run from its own directory rather than a package
# anybody installs. Under pytest `pythonpath` in pyproject.toml puts it on the
# path; running this module as a script does not go through pytest.
if str(REPO_ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "backend"))

# Unlike advice_fixture.py one file over, this generator's payload comes off a
# real Django model (Consent.KINDS), not off ampeer_advice/ampeer_sim, which
# never import Django at all. `DJANGO_SETTINGS_MODULE` in pyproject.toml's
# `[tool.pytest.ini_options]` is read by pytest-django during pytest's own
# startup and by nothing else, so a bare `python` invocation never sees it.
# `setdefault`, not an assignment: a caller's own exported value, or pytest's,
# is never overridden.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ampeer.settings.test")


def build_consent_texts_payload() -> dict[str, Any]:
    """Exactly what ConsentTextsView answers, from the same two sources.

    `django.setup()` first and the `accounts` imports after, in that order and
    inside this function rather than at the module head: importing
    `accounts.models` before Django's app registry is populated is exactly the
    `AppRegistryNotReady` this call prevents, and `setup()` itself is cheap to
    repeat (Django's `Apps.populate` returns immediately once already
    populated), so this runs identically the first time, standalone, and every
    time pytest calls it with the registry already populated.
    """
    import django

    django.setup()

    from accounts.models import Consent
    from accounts.nl import CONSENT_TEXT_VERSION, NL

    return {
        "text_version": CONSENT_TEXT_VERSION,
        "texts": {kind: NL[f"CONSENT_{kind}"] for kind in sorted(Consent.KINDS)},
        "labels": {kind: NL[f"CONSENT_LABEL_{kind}"] for kind in sorted(Consent.KINDS)},
    }


def write_fixture() -> int:
    """Rewrite the committed fixture and report its size in bytes."""
    payload = build_consent_texts_payload()
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    # newline pinned to a line feed, for the reason advice_fixture.py gives:
    # on Windows the default writes carriage return pairs, pre-commit's
    # mixed-line-ending hook rewrites the file, and the commit fails.
    with FIXTURE.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return len(json.dumps(payload))


if __name__ == "__main__":
    print(f"wrote {write_fixture()} bytes to {FIXTURE}")
