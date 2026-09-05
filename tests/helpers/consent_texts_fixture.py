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


def build_consent_texts_payload() -> dict[str, Any]:
    """Exactly what ConsentTextsView answers, from the same two sources."""
    from accounts.models import Consent
    from accounts.nl import CONSENT_TEXT_VERSION, NL

    return {
        "text_version": CONSENT_TEXT_VERSION,
        "texts": {kind: NL[f"CONSENT_{kind}"] for kind in sorted(Consent.KINDS)},
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
