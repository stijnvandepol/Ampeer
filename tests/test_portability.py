"""The differences between this machine and the one that runs the pipeline.

Development happens on Windows and everything else happens on Linux. Two of the
differences are invisible here by construction: a filesystem that does not care
about case, and a git that does not carry the executable bit reliably. Both
produce a repository that works on the machine it was written on and fails on
the first checkout somewhere else.

That has always been true and it matters more now. The pipeline has been
unavailable since 2026-08-21 and every run is billed, so the first green run
after it comes back should not be spent discovering that a filename was typed
with the wrong capital.

Everything here is decided from the index rather than from the working tree,
because the working tree on Windows will happily answer a question about case
with the answer you hoped for.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Files whose contents can name another file.
_READABLE = (".py", ".ts", ".tsx", ".sh", ".yml", ".yaml", ".md", ".toml", ".json", ".conf")

#: A quoted path with at least one directory and an extension.
_PATH_LITERAL = re.compile(r"[\"'`]((?:[\w.\-]+/)+[\w.\-]+\.[a-z]{1,5})[\"'`]")


def _tracked() -> list[str]:
    """Every file git has, as git spells it.

    `git ls-files` and not a walk of the tree: the index is the thing that gets
    checked out on the runner, and it is the only place where the case of a
    name is recorded rather than merely displayed.
    """
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _case_collisions(names: list[str]) -> dict[str, list[str]]:
    """Names that differ only in case, grouped.

    A function over a list rather than a body inside the test, because the
    state it looks for cannot be created on this machine. Adding two such files
    requires a case sensitive filesystem, so the test below would be a check
    nobody had ever seen go red. Handed a list, it can be shown to work.
    """
    seen: dict[str, list[str]] = {}
    for name in names:
        seen.setdefault(name.lower(), []).append(name)
    return {key: found for key, found in seen.items() if len(found) > 1}


def test_the_collision_rule_recognises_a_collision() -> None:
    """Both branches of the check below, run rather than reasoned about.

    The example pair names nothing this repository has, and that is not
    decoration. The first version used docs/dpia.md against docs/DPIA.md, and
    the scan above read this file, found a literal whose lowercase form is a
    real tracked path, and reported it. A fixture that looks like the defect it
    describes gets found by the detector that describes it.
    """
    assert _case_collisions(["docs/imaginary.md", "docs/Imaginary.md"]) == {
        "docs/imaginary.md": ["docs/imaginary.md", "docs/Imaginary.md"]
    }
    assert _case_collisions(["docs/imaginary.md", "docs/other.md"]) == {}


def test_no_two_tracked_files_differ_only_in_case() -> None:
    """Two such files cannot both exist in a checkout on Windows or macOS.

    One overwrites the other and git reports the working tree as modified for
    reasons nobody can act on. It is a state that can only be created from
    Linux, and the fix once it is in history is not a rename.
    """
    collisions = _case_collisions(_tracked())
    assert not collisions, f"these differ only in case: {collisions}"


def test_every_path_literal_is_spelled_the_way_git_spells_it() -> None:
    """A capital in the wrong place works here and fails on the runner.

    Only literals that name a file this repository actually has are judged.
    A path that matches nothing tracked is a host path, a URL fragment or an
    example, and this says nothing about those. So the check has no false
    positives by construction: it reports a name only when the same name exists
    in the index under a different case, which is never intentional.

    Measured on 2026-08-22: 228 files scanned, nothing misspelled. That is the
    expected answer on a repository that has never been checked out on a case
    sensitive filesystem, and it is why this exists before that happens rather
    than after.
    """
    tracked = _tracked()
    exact = set(tracked)
    by_lower = {name.lower(): name for name in tracked}

    wrong = []
    for name in tracked:
        if not name.endswith(_READABLE):
            continue
        try:
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):  # pragma: no cover - not in this tree
            continue
        for reference in sorted(set(_PATH_LITERAL.findall(text))):
            if reference in exact:
                continue
            actual = by_lower.get(reference.lower())
            if actual is not None:
                wrong.append(f"{name}: {reference!r} is {actual!r} in the index")
    assert not wrong, "paths spelled with the wrong case:\n  " + "\n  ".join(wrong)


def test_the_scan_reads_the_repository() -> None:
    """The floor under the check above, which is a statement about a set.

    A pattern that stopped matching, a `git ls-files` that returned nothing, or
    a suffix list that excluded everything would leave it green over no
    literals at all.
    """
    tracked = _tracked()
    assert len(tracked) > 100, f"git reports only {len(tracked)} files"
    readable = [name for name in tracked if name.endswith(_READABLE)]
    assert len(readable) > 100, f"only {len(readable)} files would be read"
    found = {
        reference
        for name in readable
        for reference in _PATH_LITERAL.findall((REPO_ROOT / name).read_text(encoding="utf-8"))
    }
    assert len(found) > 40, f"only {len(found)} path literals found across the tree"
    assert any(reference in set(tracked) for reference in found), (
        "no literal anywhere names a file this repository has, so the comparison above "
        "is running against nothing"
    )


#: How a shell script in this repository is allowed to be started.
#:
#: Never through its own executable bit. git on Windows does not carry that bit
#: reliably and all five scripts sit in the index as 100644, so a checkout on
#: Linux produces files that cannot execute themselves. Every invocation names
#: an interpreter instead: `bash /srv/ampeer/backup_db.sh` in the systemd unit,
#: `bash scripts/gates.sh` in the operator README. infra/api.Dockerfile is the
#: one exception and it does not need one, because `COPY --chmod=0555` sets the
#: bit at build time rather than relying on the checkout.
_SELF_EXECUTING = re.compile(r"(?:^|\s)(\./[\w./\-]+\.sh)\b")
_EXEC_START = re.compile(r"^ExecStart(?:Post|Pre)?=([^\s]+)", re.MULTILINE)


@pytest.mark.parametrize(
    "name", sorted(name for name in _tracked() if name.endswith((".md", ".yml", ".service", ".sh")))
)
def test_no_shell_script_is_started_through_its_own_executable_bit(name: str) -> None:
    """The invariant the five scripts already follow, now written down.

    It holds today and nothing said so, which is how it would stop holding: an
    ExecStart pointed straight at a .sh, or a README that says `./scripts/x.sh`
    because that is what the author types on a machine where it works.
    """
    text = (REPO_ROOT / name).read_text(encoding="utf-8")
    relative = sorted(set(_SELF_EXECUTING.findall(text)))
    assert not relative, (
        f"{name} starts a script through its own executable bit: {relative}. "
        "The bit is not in the index, so this works only where somebody set it by "
        "hand. Name the interpreter instead."
    )
    direct = [target for target in _EXEC_START.findall(text) if target.endswith(".sh")]
    assert not direct, (
        f"{name} has an ExecStart pointing straight at {direct}, which needs an "
        "executable bit that the checkout does not provide"
    )
