"""Where the ingested NEDU profile lands, asked of the tool that writes it."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INGEST = REPO_ROOT / "tools" / "ingest_profiles.py"

#: The f-string tools/ingest_profiles.py builds its destination from.
_DESTINATION = re.compile(r'destination\s*=\s*target_dir\s*/\s*f"([^"]+)"')


def nedu_profile_name(year: int) -> str:
    """The file name the ingest tool writes for a year.

    Derived rather than repeated, and this is not tidiness. Two tests gate
    themselves on whether this file is present, one with skipif and one with
    pytest.skip. A skip whose condition is an absence cannot tell "not
    downloaded yet" from "looking in the wrong place", so a copy of this name
    that drifted from the tool would turn both into tests that never run again,
    on any machine, quietly.

    Raises rather than falling back. A default here would be the same failure
    one level up: a name that resolves to nothing and a skip that looks
    ordinary.
    """
    match = _DESTINATION.search(INGEST.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(
            f"{INGEST.name} no longer builds its destination in a shape this can read; "
            "the tests that skip on this file would otherwise skip forever"
        )
    template = match.group(1)
    if "{year}" not in template:
        raise AssertionError(f"the destination {template!r} does not depend on the year")
    return template.replace("{year}", str(year))


def nedu_profile_path(year: int) -> Path:
    """The ingested profile for a year, where a developer machine keeps it.

    Gitignored, because the redistribution terms of the NEDU files are not
    confirmed. Only present on a machine that has run tools/ingest_profiles.py.
    """
    return REPO_ROOT / "data" / nedu_profile_name(year)
