"""Reading values out of shell scripts without running them."""

from __future__ import annotations

import re
from pathlib import Path


def shell_int(source: Path, name: str) -> int:
    """A bare ``NAME=value`` assignment in a shell script.

    Read rather than sourced, for the reason scripts/preflight_env.sh gives
    about the env file it parses: running a file to find out what is in it is a
    different act from reading it.

    Lives here rather than in one test module because two of them need it, and
    two regexes that decide the same thing drift apart in the direction that
    makes a test pass.
    """
    pattern = re.compile("^" + name + "=([0-9]+)$", re.MULTILINE)
    match = pattern.search(source.read_text(encoding="utf-8"))
    assert match, f"{source.name} no longer assigns {name}"
    return int(match.group(1))
