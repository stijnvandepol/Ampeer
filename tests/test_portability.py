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

A third difference is not about files at all: parts of this suite skip
depending on where they run, and a skip is invisible in a green run. That is
guarded at the bottom of this file.

Everything here is decided from the index rather than from the working tree,
because the working tree on Windows will happily answer a question about case
with the answer you hoped for.
"""

from __future__ import annotations

import json
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


# ---------------------------------------------------------------------------
# The half of the case problem that has no file extension
# ---------------------------------------------------------------------------

FRONTEND = REPO_ROOT / "frontend"

#: How TypeScript turns a module specifier into a file, in the order it tries.
#:
#: The check above cannot see any of this. It reads quoted paths that end in an
#: extension, and an import does not have one: `@/components/band/HeadlineBand`
#: is a path with five capitals in it and no `.tsx`. That is the shape the case
#: bug takes in a Next.js project, where directories are lowercase and component
#: files are not, and it is the expensive shape: it survives a build here and
#: stops `next build` on the runner.
_TS_CANDIDATES = ("", ".ts", ".tsx", "/index.ts", "/index.tsx")

_IMPORT = re.compile(r"""(?:from|import)\s+["']([^"']+)["']""")


def _tsconfig() -> dict[str, object]:
    """frontend/tsconfig.json, with its comment lines dropped.

    Only whole comment lines. A regex over `//` anywhere would cut a URL in
    half, and being wrong about the config that decides where imports point is
    worse than not reading it.
    """
    raw = (FRONTEND / "tsconfig.json").read_text(encoding="utf-8")
    stripped = "\n".join(line for line in raw.splitlines() if not line.lstrip().startswith("//"))
    parsed: dict[str, object] = json.loads(stripped)
    return parsed


def _alias_target() -> str:
    """What `@/` means, taken from tsconfig rather than written down again."""
    options = _tsconfig().get("compilerOptions", {})
    assert isinstance(options, dict)
    paths = options.get("paths", {})
    assert isinstance(paths, dict), "tsconfig declares no paths, so @/ resolves to nothing"
    target = paths.get("@/*")
    assert isinstance(target, list) and target, f"@/* maps to {target!r}"
    return str(target[0]).removeprefix("./").removesuffix("*").rstrip("/")


def _internal_imports() -> list[tuple[str, str, str]]:
    """Every import that names a file in this repository, already resolved.

    Returns (importer, specifier, path from the repository root). A specifier
    that is neither relative nor aliased is a package, and says nothing about
    this tree.
    """
    alias = _alias_target()
    found: list[tuple[str, str, str]] = []
    for name in _tracked():
        if not name.endswith((".ts", ".tsx")):
            continue
        source = REPO_ROOT / name
        for specifier in sorted(set(_IMPORT.findall(source.read_text(encoding="utf-8")))):
            if specifier.startswith("@/"):
                target = f"frontend/{alias}/{specifier[2:]}"
            elif specifier.startswith("."):
                target = (source.parent / specifier).resolve().relative_to(REPO_ROOT).as_posix()
            else:
                continue
            found.append((name, specifier, target))
    return found


def test_every_typescript_import_is_spelled_the_way_git_spells_it() -> None:
    """A capital in an import works here and stops the build on the runner.

    Measured on 2026-08-22: 124 internal imports across the frontend, all
    spelled exactly. That is the answer expected of a tree that has only ever
    been built on a filesystem which cannot tell the difference, and it is why
    this is written before the first build somewhere that can.

    An import resolving to nothing at all is not reported here. That is a
    broken import, tsc says so already and says it better, and repeating a
    stronger check with a weaker one is how a suite grows noise.
    """
    exact = set(_tracked())
    by_lower = {name.lower(): name for name in exact}

    wrong = []
    for importer, specifier, target in _internal_imports():
        if any(target + suffix in exact for suffix in _TS_CANDIDATES):
            continue
        near = [
            by_lower[(target + suffix).lower()]
            for suffix in _TS_CANDIDATES
            if (target + suffix).lower() in by_lower
        ]
        if near:
            wrong.append(f"{importer}: imports {specifier!r}, which git spells {near[0]!r}")
    assert not wrong, "imports spelled with the wrong case:\n  " + "\n  ".join(wrong)


def test_the_import_scan_resolves_something() -> None:
    """The floor, since the check above is a statement about a set it builds.

    An alias read wrongly, a pattern that stopped matching or a resolution that
    landed outside the tree would all leave it green over nothing.
    """
    imports = _internal_imports()
    assert len(imports) >= 100, f"only {len(imports)} internal imports resolved"
    exact = set(_tracked())
    resolved = [
        target
        for _, _, target in imports
        if any(target + suffix in exact for suffix in _TS_CANDIDATES)
    ]
    assert len(resolved) == len(imports), (
        f"{len(imports) - len(resolved)} imports resolve to no file at all, so either "
        "the alias is being read wrongly or the frontend does not build"
    )


def test_the_alias_means_the_same_directory_everywhere_it_is_declared() -> None:
    """`@/` is defined twice, in two languages, and both have to agree.

    frontend/tsconfig.json decides where tsc and next look. frontend/
    vitest.config.ts decides where the unit tests look, and it is a separate
    declaration because vitest does not read tsconfig paths. If they drift, a
    module resolves to one file under test and another in the build, and the
    failure arrives as a type error in a file nobody edited.

    Nothing compared them. This is the same shape as a threshold and the timer
    it is measured against: two settings in two files, each with a comment, and
    no assertion between them.
    """
    alias = _alias_target()
    vitest = (FRONTEND / "vitest.config.ts").read_text(encoding="utf-8")
    match = re.search(
        r"""alias:\s*\{\s*["']@["']:\s*[^(]*\(\s*new URL\(\s*["']\./([^"']+)["']""", vitest
    )
    assert match, (
        "frontend/vitest.config.ts no longer declares the @ alias in a shape this can "
        "read; if it stopped declaring one at all, every aliased import in a test "
        "resolves as a package"
    )
    assert match.group(1).rstrip("/") == alias, (
        f"tsconfig maps @/ to {alias!r} and vitest maps it to {match.group(1)!r}, so a "
        "module resolves to a different file under test than in the build"
    )


# ---------------------------------------------------------------------------
# What a green run did not run
# ---------------------------------------------------------------------------

#: Every reason this suite is allowed to skip a test, and what it costs.
#:
#: A skip is invisible in a green run. "983 passed" says nothing about the
#: three tests that did not, and until 2026-08-22 the three that did not here
#: were the ones asserting a backup file is 0600 inside a 0700 directory, which
#: is a claim docs/dpia.md makes in its risk table. They had never run on this
#: machine, and nobody could have known from the output.
#:
#: Measured that day by running the suite in a Linux container beside the one
#: here. Windows skipped three and ran 983; Linux skipped two and ran 984; the
#: union is 986 and neither environment runs all of it. The two Linux skips are
#: the NEDU profile tests, whose data file is deliberately not committed, so
#: those never run in CI either.
#:
#: Pinned so that a new skip is an edit here, in front of a reviewer, rather
#: than a line that quietly subtracts a test from every run afterwards.
ALLOWED_SKIPS = {
    "run tools/ingest_profiles.py first": "the ingested profile is not committed",
    "the NEDU profile file is not committed; see infra/README.md": (
        "same file, and this one also skips in CI"
    ),
    "this filesystem does not carry POSIX modes; the host and CI do": (
        "Windows only; these are the backup permission tests and they run on Linux"
    ),
    "the deploy job no longer falls back, so the README should say so": (
        "a behaviour check that turns itself off when the behaviour goes"
    ),
    "the API now supplies the install year, so the caveat no longer applies": (
        "the document would have to change, and the test says so instead of failing"
    ),
    "the API now supplies meter data, so PRECISE is reachable": (
        "same shape, for the confidence ceiling"
    ),
    "no quarter-hour table; chapter 1's original weighing stands": (
        "same shape again, for the DPIA: the correction is only owed while "
        "QuarterReading exists, and a phase that dropped the table would make "
        "the document's original article 35 reasoning right again"
    ),
}

_SKIP_REASON = re.compile(r'(?:pytest\.skip\(|reason=)"([^"]+)"')


def _skip_reasons() -> dict[str, list[str]]:
    """Every reason the suite can skip on, and where it is written."""
    found: dict[str, list[str]] = {}
    for path in sorted((REPO_ROOT / "tests").glob("test_*.py")):
        for reason in _SKIP_REASON.findall(path.read_text(encoding="utf-8")):
            found.setdefault(reason, []).append(path.name)
    return found


def test_every_skip_in_this_suite_is_one_that_was_argued_for() -> None:
    """A test that does not run is not a test that passed.

    Both directions. A reason not in the table is a test quietly subtracting
    itself from every run; a reason in the table that no longer exists is an
    entry vouching for a skip that is gone, which is how this table would rot
    into always passing.
    """
    reasons = _skip_reasons()
    unexplained = sorted(set(reasons) - set(ALLOWED_SKIPS))
    assert not unexplained, "these skips are not accounted for:\n  " + "\n  ".join(
        f"{reason!r} in {reasons[reason]}" for reason in unexplained
    )
    stale = sorted(set(ALLOWED_SKIPS) - set(reasons))
    assert not stale, (
        "these reasons are listed here and no test skips on them any more; remove the "
        f"entry rather than leaving it to vouch for nothing: {stale}"
    )


def test_the_skip_scan_finds_the_skips_that_are_there() -> None:
    """The floor, since the test above is a comparison between two sets.

    Both are empty if the pattern stops matching, and two empty sets are equal.
    """
    reasons = _skip_reasons()
    assert len(reasons) >= 5, f"only found {sorted(reasons)}"
    assert "this filesystem does not carry POSIX modes; the host and CI do" in reasons, (
        "the permission tests no longer name the reason they skip on Windows, which is "
        "the skip this whole check was written around"
    )


# ---------------------------------------------------------------------------
# What the site serves, and where its links go
# ---------------------------------------------------------------------------

PUBLIC = FRONTEND / "public"
APP = FRONTEND / "src" / "app"

#: An href to a path on this site, as written in a component.
_INTERNAL_HREF = re.compile(r'href="(/[a-zA-Z0-9/_-]*)"')


def _components() -> list[str]:
    """Every component this repository tracks, from git rather than the tree.

    A walk of frontend/ descends into node_modules before it can filter it out,
    which cost seventeen seconds in one of these tests. Git already knows what
    is ours, and this module says in its own opening that it decides from the
    index; walking the working tree was the one place here that did not.
    """
    return [name for name in _tracked() if name.startswith("frontend/") and name.endswith(".tsx")]


def _exported_routes() -> set[str]:
    """Every route `next build` writes, derived from the app directory.

    A directory holding a page.tsx is a route, and its path under app/ is the
    URL. Read from the tree rather than listed, so a page added later is a
    route this test knows about without anybody saying so. Directories starting
    with an underscore are Next's private convention and produce no route.
    """
    prefix = "frontend/src/app/"
    routes = set()
    for name in _tracked():
        if not (name.startswith(prefix) and name.endswith("/page.tsx")):
            continue
        relative = name[len(prefix) : -len("page.tsx")]
        if any(part.startswith("_") for part in relative.split("/") if part):
            continue
        routes.add(f"/{relative}")
    return routes


def test_every_internal_link_goes_somewhere_this_site_exports() -> None:
    """A static export answers a wrong path with a 404 and no other sign.

    There is no server to log it, no route resolver to raise, and the page it
    was written on renders perfectly. The only way to find out is to click it,
    which is why a header link to a page that stopped existing can sit in a
    build for a long time.

    Dynamic segments are not judged. /advies/ takes a token, and the link to
    an advice is built from a token in code rather than written as an href, so
    it does not appear here at all.
    """
    routes = _exported_routes()
    assert routes, f"no page.tsx found under {APP}, so this test read nothing"

    dangling = []
    for name in _components():
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        for href in sorted(set(_INTERNAL_HREF.findall(text))):
            if href not in routes:
                dangling.append(f"{name}: {href}")
    assert not dangling, (
        "these links point at paths this site does not export:\n  "
        + "\n  ".join(dangling)
        + f"\nExported: {sorted(routes)}"
    )


def test_the_route_scan_finds_the_pages_that_are_there() -> None:
    """The floor under the check above, which compares against a derived set.

    An empty route set would make every link dangling, so that direction fails
    loudly. The quiet direction is a set so large that nothing can dangle, or a
    scan that reads no component at all and finds no links to judge.
    """
    routes = _exported_routes()
    assert {"/", "/berekenen/", "/advies/", "/methodologie/"} <= routes, (
        f"the site no longer exports the four pages it was built around: {sorted(routes)}"
    )
    hrefs = {
        href
        for name in _components()
        for href in _INTERNAL_HREF.findall((REPO_ROOT / name).read_text(encoding="utf-8"))
    }
    assert len(hrefs) >= 3, f"only {sorted(hrefs)} found, so the comparison judges almost nothing"


def _unreferenced(served: list[str], haystack: str) -> list[str]:
    """Which of these files nothing asks for, by the name the site serves it at.

    A function over its inputs rather than a body inside the test, because the
    directory it judges does not exist today. A test that returned early on
    that would be a check nobody has ever seen work, and this file already
    holds one rule extracted for the same reason.
    """
    return [name for name in served if f"/{name}" not in haystack]


def test_the_rule_finds_a_file_nothing_asks_for() -> None:
    """Both branches, run rather than reasoned about."""
    assert _unreferenced(["vercel.svg", "logo.png"], 'src="/logo.png"') == ["vercel.svg"]
    assert _unreferenced(["logo.png"], 'src="/logo.png"') == []
    assert _unreferenced([], "") == []


def test_nothing_is_served_that_nothing_asks_for() -> None:
    """frontend/public is copied into the export exactly as it stands.

    It arrived from the Next.js template holding five SVGs. Four were
    decoration and two were somebody else's mark: next.svg and vercel.svg were
    fetchable at ampeer.nl and nothing in this repository ever referenced
    them. A product whose whole claim is that it is not selling anybody's
    product should not be serving another company's logo by accident.

    They are gone and the directory with them, since git does not keep an empty
    one and Next does not need it. What this keeps out is the next template
    leftover: anything put back has to be asked for by name.
    """
    served = [
        name[len("frontend/public/") :]
        for name in _tracked()
        if name.startswith("frontend/public/")
    ]
    haystack = "\n".join(
        (REPO_ROOT / name).read_text(encoding="utf-8", errors="ignore")
        for name in _tracked()
        if name.startswith("frontend/")
        and not name.startswith("frontend/public/")
        and name.endswith((".tsx", ".ts", ".css", ".json", ".html"))
    )
    unused = _unreferenced(served, haystack)
    assert not unused, (
        "these files are copied into the export and nothing references them:\n  "
        + "\n  ".join(unused)
        + "\nEither use them or delete them; a static export serves whatever is here."
    )
