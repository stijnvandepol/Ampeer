"""Structural guarantees that must hold for the whole package."""

from __future__ import annotations

import ast
import pathlib
from urllib.parse import urlsplit

import ampeer_advice
import ampeer_sim

PACKAGE_ROOTS = (
    pathlib.Path(ampeer_sim.__file__).parent,
    pathlib.Path(ampeer_advice.__file__).parent,
)

#: Django itself, the web framework on top of it, and every top level module
#: that only exists inside backend/.
FORBIDDEN_IN_PURE_PACKAGES = {"django", "rest_framework", "backend", "advice", "ampeer"}

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"


def _imported_module_names(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_packages_never_import_django_or_the_backend() -> None:
    """The pure packages must stay runnable without a database or a server.

    This is the one part of the system where a fault produces a plausible wrong
    number rather than an error message, so it has to be testable and
    validatable on its own.
    """
    offenders = [
        f"{path}: {sorted(_imported_module_names(path) & FORBIDDEN_IN_PURE_PACKAGES)}"
        for root in PACKAGE_ROOTS
        for path in root.rglob("*.py")
        if _imported_module_names(path) & FORBIDDEN_IN_PURE_PACKAGES
    ]
    assert offenders == [], f"pure packages must not import django or backend: {offenders}"


def test_the_backend_may_import_the_pure_packages() -> None:
    """The dependency runs one way, and this proves it actually runs at all.

    A one-directional rule tested only in the forbidding direction stays green
    when the arrow disappears entirely, so this asserts the arrow is there.
    """
    importers = {
        path.name
        for path in BACKEND_ROOT.rglob("*.py")
        if {"ampeer_sim", "ampeer_advice"} & _imported_module_names(path)
    }
    assert importers, "no file under backend/ imports the engine; the seam is missing"


def test_engine_version_is_declared() -> None:
    """The shape of the version only.

    What it is allowed to mean is pinned in tests/test_golden.py, which fails
    when a model constant or a golden answer moves without the version moving.
    """
    assert isinstance(ampeer_sim.ENGINE_VERSION, str)
    assert ampeer_sim.ENGINE_VERSION.count(".") == 2


# ---------------------------------------------------------------------------
# No outbound HTTP except to a fixed allowlist
# ---------------------------------------------------------------------------

#: Importing one of these means a module can open a connection it chose itself.
#:
#: Wider than the HTTP clients, because the rule is about reaching outward and
#: not about a protocol: a raw socket or an ftp client would carry a
#: user supplied destination just as well as requests would.
NETWORK_CLIENTS = frozenset(
    {
        "requests",
        "httpx",
        "aiohttp",
        "urllib",
        "urllib3",
        "http",
        "socket",
        "ftplib",
        "telnetlib",
        "smtplib",
        "xmlrpc",
    }
)

#: The only module allowed to reach outside this machine, and where it may go.
#:
#: CLAUDE.md permits three external sources, PVGIS, ENTSO-E and KNMI. Only PVGIS
#: is fetched today, so only its host is here. The allowlist is one constant in
#: one module rather than a settings entry, because a configuration layer that
#: exactly one caller reads is a layer that hides where the value comes from.
#: A second source is what makes that question real, and adding one means
#: adding it here on purpose.
OUTBOUND_MODULE = "ampeer_sim/production/pvgis.py"
ALLOWED_HOSTS = frozenset({"re.jrc.ec.europa.eu"})


def _python_sources() -> list[pathlib.Path]:
    """Every Python file in the two pure packages and in the Django project."""
    return sorted(
        path
        for root in (*PACKAGE_ROOTS, BACKEND_ROOT)
        for path in root.rglob("*.py")
        if "__pycache__" not in path.parts
    )


#: Whether an AST node is a string literal that starts a URL.
#:
#: A predicate over the node and not over its value, so mypy narrows it. The
#: first version asked `getattr(node, "value", None)`, which type checks against
#: anything because getattr returns Any, and that is the shape of check this
#: repository keeps removing.
def _is_url_literal(node: ast.AST | None) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(("http://", "https://"))
    )


def test_only_one_module_can_reach_outside_this_machine() -> None:
    """The SSRF rule is categorical, so the guard has to be too.

    CLAUDE.md forbids outbound HTTP to a user supplied URL and allows exactly
    one exception: a fixed allowlist of external sources whose URLs are never
    assembled from user input. ampeer_sim/production/pvgis.py opens with a
    docstring saying it is the only module that performs outbound HTTP, which is
    true and which nothing could contradict, because a docstring cannot fail a
    build.

    That claim is what this test turns into a gate. The value is not in today's
    answer, which is one file. It is that a second file cannot join it quietly:
    a helper that fetches a tariff, a webhook, a health probe against a host
    from the environment, anything that opens a connection has to change this
    line and be argued for in the diff.

    An import and not a call. A module that imports requests can reach outward
    on any line, including one added later, so the import is where the boundary
    is decidable and where a reviewer can see it.
    """
    reaching = {
        path.relative_to(REPO_ROOT).as_posix(): sorted(
            _imported_module_names(path) & NETWORK_CLIENTS
        )
        for path in _python_sources()
        if _imported_module_names(path) & NETWORK_CLIENTS
    }
    assert reaching == {OUTBOUND_MODULE: ["requests"]}, (
        "the set of modules that can open an outbound connection has changed:\n"
        + "\n".join(f"  {name}: {clients}" for name, clients in sorted(reaching.items()))
        + f"\nThe project rule allows {OUTBOUND_MODULE} and nothing else. Meter data "
        "arrives by push so the backend never fetches, and that is what rules SSRF "
        "out as a category rather than case by case."
    )


def test_the_module_that_speaks_http_never_assembles_its_url() -> None:
    """The other half of the rule: the destination is fixed, not computed.

    Confining outbound traffic to one module says nothing about where that
    module points. The rule reads that user input supplies validated parameters
    and never parts of the URL itself, which is what makes a postcode safe to
    pass on: it reaches PVGIS as a query parameter, not as a piece of a host.

    Three things are checked, each of which would be a way to lose that.

    - Every URL literal is https and its host is on the allowlist, so a
      redirect target or a debug host cannot be dropped in.
    - No f-string and no concatenation starts from a URL literal, so nothing
      grows a URL out of a value.
    - Every call carrying a timeout, which is the shape of the outbound call in
      this module, is handed a module level constant rather than an expression.
      A parameter named url would be a Name too, and it is not a module
      constant, so it fails here.

    What this does not see is an outbound call written in this module without a
    timeout and without a literal. That residue is one file wide, and the test
    above is what keeps it one file wide.
    """
    path = REPO_ROOT / OUTBOUND_MODULE
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    constants = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name) and target.id.isupper()
    }

    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _is_url_literal(node)
    ]
    assert literals, f"no URL literal found in {OUTBOUND_MODULE}; this test read nothing"
    for url in literals:
        assert url.startswith("https://"), f"{url} is not https"
        host = urlsplit(url).hostname
        assert host in ALLOWED_HOSTS, (
            f"{OUTBOUND_MODULE} points at {host}, which is not on the allowlist "
            f"{sorted(ALLOWED_HOSTS)}. CLAUDE.md fixes the external sources in config; "
            "a new one is a decision, not a URL edit."
        )

    assembled = [
        ast.unparse(node)
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.JoinedStr)
            and bool(node.values)
            and _is_url_literal(node.values[0])
        )
        or (
            isinstance(node, ast.BinOp)
            and isinstance(node.op, ast.Add)
            and _is_url_literal(node.left)
        )
    ]
    assert not assembled, (
        "a URL is being built rather than named, which is how user input reaches "
        "the address instead of the query string:\n" + "\n".join(f"  {code}" for code in assembled)
    )

    outbound = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and any(kw.arg == "timeout" for kw in node.keywords)
    ]
    assert outbound, (
        f"no call in {OUTBOUND_MODULE} carries a timeout, so either the request left "
        "or this test stopped recognising it"
    )
    for call in outbound:
        target = call.args[0] if call.args else None
        assert isinstance(target, ast.Name) and target.id in constants, (
            f"{ast.unparse(call.func)} is called with "
            f"{ast.unparse(target) if target else 'no positional argument'}, which is not "
            "a module level constant. The destination of an outbound call has to be "
            "fixed in the source where a reviewer can see it."
        )
