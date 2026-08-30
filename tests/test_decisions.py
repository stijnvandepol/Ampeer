"""The decision log has to keep pointing at the thing it describes.

`docs/decisions.md` is an index over choices whose arguments live in commit
messages. An index is only worth the trouble while its entries resolve, and the
way it stops resolving is a rename: the entry still reads like a guarantee, the
reader goes to the file, finds nothing, and cannot tell whether the decision was
reversed or the code moved.

What is checked is that each entry names a file that exists and a symbol that is
in it. Whether the decision described is still the one the code implements is
not mechanically knowable, and a test that implied otherwise would be a worse
guarantee than none.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DECISIONS = REPO_ROOT / "docs" / "decisions.md"
TEXT = DECISIONS.read_text(encoding="utf-8")

#: The fields every entry carries. Listed because the value of the log is that
#: each entry answers the same four questions, and an entry missing "To reverse"
#: is the one that quietly becomes a note rather than a decision.
REQUIRED_FIELDS = ("**Decided:**", "**Because:**", "**Lives in:**", "**To reverse:**")

#: What makes a backticked token on a Lives in line a path rather than a symbol.
#: pyproject.toml carries no slash, so a slash alone does not decide it.
#:
#: The frontend suffixes were added on 2026-08-30 with the first decision that
#: lives there. Without them a token like `frontend/src/app/globals.css` reads
#: as a SYMBOL, and the check then looks for that literal string inside the
#: other files the entry names, which is a failure with a misleading message
#: rather than the path check the entry was asking for. No existing entry named
#: such a file, so nothing was reclassified by adding them.
_PATH_SUFFIXES = (
    ".py",
    ".toml",
    ".yml",
    ".yaml",
    ".sh",
    ".md",
    ".json",
    ".ts",
    ".tsx",
    ".css",
)

_ENTRY = re.compile(r"^### \d+\. (.+)$", re.MULTILINE)
_QUOTED = re.compile(r"`([^`]+)`")


def _entries() -> list[tuple[str, str]]:
    """Each numbered decision, as its title and the text under it."""
    matches = list(_ENTRY.finditer(TEXT))
    end_of_list = TEXT.index("## What was not decided here")
    return [
        (
            match.group(1),
            TEXT[match.end() : (matches[i + 1].start() if i + 1 < len(matches) else end_of_list)],
        )
        for i, match in enumerate(matches)
    ]


def _lives_in(body: str) -> tuple[list[str], list[str]]:
    """The paths and the symbols an entry says carry it."""
    line = next(
        (line for line in body.splitlines() if line.startswith("**Lives in:**")),
        "",
    )
    # The field wraps, so read on until the blank line that ends the paragraph.
    lines = body.splitlines()
    if line:
        start = lines.index(line)
        collected = []
        for text in lines[start:]:
            if not text.strip():
                break
            collected.append(text)
        line = " ".join(collected)
    tokens = _QUOTED.findall(line)
    paths = [token for token in tokens if token.endswith(_PATH_SUFFIXES)]
    symbols = [token for token in tokens if not token.endswith(_PATH_SUFFIXES)]
    return paths, symbols


@pytest.mark.parametrize(("title", "body"), _entries(), ids=[title[:40] for title, _ in _entries()])
def test_every_decision_answers_the_same_four_questions(title: str, body: str) -> None:
    """An entry missing a field is the one that stops being reversible.

    "To reverse" is the field that matters most and the easiest to leave off,
    because it is the only one that costs anything to work out.
    """
    missing = [field for field in REQUIRED_FIELDS if field not in body]
    assert not missing, f"the entry {title!r} has no {', '.join(missing)}"


@pytest.mark.parametrize(("title", "body"), _entries(), ids=[title[:40] for title, _ in _entries()])
def test_every_decision_points_at_something_that_exists(title: str, body: str) -> None:
    """The file has to be there and the symbol has to be in it.

    Checking the symbol as well as the path is what makes this more than a
    spell check on filenames. An entry that says a decision lives in a constant
    is claiming that constant is what carries it, and a rename of the constant
    inside a file that still exists is exactly the drift a path check misses.
    """
    paths, symbols = _lives_in(body)
    assert paths, f"the entry {title!r} names no file"

    missing = [path for path in paths if not (REPO_ROOT / path).is_file()]
    assert not missing, f"{title!r} names files that are not in the tree: {missing}"

    contents = "\n".join((REPO_ROOT / path).read_text(encoding="utf-8") for path in paths)
    unfound = [symbol for symbol in symbols if symbol not in contents]
    assert not unfound, (
        f"{title!r} says it lives in {unfound}, which is in none of {paths}. Either the "
        "decision moved or it was reversed, and the entry has to say which."
    )


def test_the_log_is_read_rather_than_assumed() -> None:
    """The half that keeps the two above from passing over an empty reading.

    Both are parametrised over a list this file builds, and pytest reports zero
    parametrised cases as a pass. A heading style that changed, a renamed
    closing section, or a moved file would leave both green over nothing.
    """
    entries = _entries()
    assert len(entries) >= 8, f"only {len(entries)} decisions parsed out of {DECISIONS}"
    assert any("addressed as" in title for title, _ in entries), (
        "the form of address is no longer in the log, which would be a larger change "
        "than an edit to this file"
    )
    paths = {path for _, body in entries for path in _lives_in(body)[0]}
    assert len(paths) >= 6, f"the entries name only {sorted(paths)}"
