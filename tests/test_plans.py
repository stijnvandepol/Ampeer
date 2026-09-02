"""The plans are this project's record of what it set out to build.

Nothing checked that the record still matches the tree. A plan names the files
each task creates, and those names are how somebody picks up unfinished work or
audits finished work. A rename leaves them pointing at nothing, and a plan is
prose, so nothing fails: the reader goes looking, finds no such file, and cannot
tell whether the thing moved, was never built, or was deleted on purpose.

Only paths are checked. Whether a task was carried out the way it was written is
not mechanically knowable, and a test that implied otherwise would be a worse
guarantee than none.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANS_DIR = REPO_ROOT / "docs" / "superpowers" / "plans"
PLANS = sorted(PLANS_DIR.glob("*.md"))

#: The first segment of a path written from the root of this repository.
#:
#: Read from the tree rather than listed, so a directory added later needs no
#: edit here. It is what separates `frontend/src/lib/api.ts`, which is a whole
#: path, from `berekenen/page.tsx`, which is not.
TOP_LEVEL = frozenset(
    path.name for path in REPO_ROOT.iterdir() if path.is_dir() and not path.name.startswith("__")
)

_FILES_LINE = re.compile(r"^\s*-\s*(?:Create|Modify|Test):\s*(.+)$", re.MULTILINE)
_QUOTED = re.compile(r"`([^`]+)`")

#: A parenthetical on a Files line says which part of a file a task touches:
#:
#:     - Modify: `ampeer_sim/types.py` (the `TariffSet` dataclass)
#:
#: which quotes a symbol, not a path. Dropped before the paths are read, because
#: a scan that reported TariffSet as a missing file would be noise a reader
#: learns to skip, and a check people skip is not a check.
_PARENTHETICAL = re.compile(r"\([^)]*\)")

#: The spec a plan implements, from the header the plan template requires.
_SPEC = re.compile(r"^\*\*Spec:\*\*\s*`?([^`\n]+?)`?\s*$", re.MULTILINE)


def _named_paths(plan: Path) -> list[tuple[str, ...]]:
    """Every path a plan names, as the readings each one allows.

    Getting this right took three attempts and the first two are worth keeping
    in view, because both are the failure this suite exists to prevent.

    The first pattern ended in a backtick group, so it captured the first path
    on a line and stopped. A Files line usually names several, and the scan
    reported 98 paths where there are 172. A check that silently reads part of
    its input is the thing being guarded against, and it does not stop being
    that when the check is mine.

    The second read every quoted token as a path from the repository root. But
    the plans write a directory once and then list what goes in it:

        - Create: `frontend/src/app/layout.tsx`, `page.tsx`, `advies/page.tsx`

    so fourteen files that are all present came back missing.

    What is left is genuinely ambiguous, and this returns both readings rather
    than picking one. On the line above, `advies/page.tsx` is a sibling. On

        - Modify: `.github/workflows/ci.yml`, `scripts/setup_rulesets.sh`, `.gitignore`

    the last one is not a sibling of scripts/, it is the root .gitignore. These
    are notes written for a person, and no rule decides both. Accepting either
    reading is a deliberate weakening: it cannot say which file a line meant. It
    can still say that a name matches nothing at all, which is what a rename
    leaves behind and the only failure this test claims to catch.
    """
    found: list[tuple[str, ...]] = []
    for line in _FILES_LINE.findall(plan.read_text(encoding="utf-8")):
        directory = ""
        for raw in _QUOTED.findall(_PARENTHETICAL.sub("", line)):
            token = raw.split(":")[0].strip()
            if not token:
                continue
            if token.split("/")[0] in TOP_LEVEL:
                found.append((token,))
                directory = token.rsplit("/", 1)[0] + "/" if "/" in token else token
            else:
                found.append(tuple(dict.fromkeys([directory + token, token])))
    return found


def _exists(candidates: tuple[str, ...]) -> bool:
    """Whether any reading of the name is in the tree.

    A plan may write `frontend/tests/lib/*.test.ts` where a task produces
    several files whose names it cannot fix in advance. One match satisfies the
    pattern, which is what the plan was claiming.
    """
    for path in candidates:
        if "*" in path:
            if any(REPO_ROOT.glob(path)):
                return True
        elif (REPO_ROOT / path).exists():
            return True
    return False


@pytest.mark.parametrize("plan", PLANS, ids=lambda plan: plan.name)
def test_every_file_a_plan_names_exists(plan: Path) -> None:
    """Measured on 2026-08-22: six plans make 172 references to 150 distinct
    names and every one of them is in the tree, so all six are delivered.

    The twenty-two named twice are files one plan creates and another modifies,
    which is the seam between two plans and where a rename does the most damage.

    This changes nothing today, which is the usual shape of a guard here. What
    changes is that the day one of them stops being true, it stops being true
    out loud.
    """
    missing = sorted({names[0] for names in _named_paths(plan) if not _exists(names)})
    assert not missing, (
        f"{plan.name} names files that are not in the tree:\n"
        + "\n".join(f"  {path}" for path in missing)
        + "\nEither the work is not done, or something was renamed and the plan "
        "still points at where it used to be."
    )


@pytest.mark.parametrize("plan", PLANS, ids=lambda plan: plan.name)
def test_every_plan_names_a_spec_that_exists(plan: Path) -> None:
    """A plan argues from its spec, so the two have to travel together.

    Without the spec a plan is a list of steps with no record of why they are
    those steps, and that record is the thing this project keeps in writing so
    a decision can be reread and reversed.
    """
    match = _SPEC.search(plan.read_text(encoding="utf-8"))
    assert match, f"{plan.name} has no **Spec:** header, so it argues from nothing"
    spec = match.group(1).strip()
    assert (REPO_ROOT / spec).is_file(), f"{plan.name} implements {spec}, which is not in the tree"


def test_the_scan_actually_reads_the_plans() -> None:
    """The half that keeps the two above from passing over an empty reading.

    Both are statements about every member of a set the scan builds itself, so a
    pattern that stopped matching, a directory that moved, or a Files block
    written in another shape would leave them green over nothing at all.

    The counts are floors against the 172 and 150 measured today, not the
    numbers themselves, so reworking a plan does not have to touch this test.
    """
    assert len(PLANS) >= 6, f"only found {[plan.name for plan in PLANS]} under {PLANS_DIR}"
    named = [names for plan in PLANS for names in _named_paths(plan)]
    assert len(named) >= 150, f"only {len(named)} references found across the plans"
    assert len({names[0] for names in named}) >= 130, (
        "the scan is reading far fewer names than it did"
    )
    assert ("ampeer_sim/types.py",) in named, (
        "the simulation core plan no longer names the module it is built around, "
        "which would be a bigger change than a rename"
    )
    assert TOP_LEVEL >= {"ampeer_sim", "backend", "frontend", "tests"}, (
        f"the top level of this repository reads as {sorted(TOP_LEVEL)}, so the rule "
        "that separates a whole path from a sibling is not deciding anything"
    )
