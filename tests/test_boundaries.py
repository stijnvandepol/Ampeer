"""Structural guarantees that must hold for the whole package."""

from __future__ import annotations

import ast
import pathlib
import string
from urllib.parse import urlsplit

import pytest

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

#: Developer tooling. In scope for coverage in pyproject.toml and, until
#: 2026-08-23, out of scope here, while the failure message below said the
#: rule allows one file "and nothing else". It allows two.
TOOLS_ROOT = REPO_ROOT / "tools"


def _imported_module_names(path: pathlib.Path) -> set[str]:
    """Both the top-level name and the full dotted name of every import.

    The full name is what lets `django.core.mail` be forbidden below: until
    2026-09-06 only the first segment was kept, so Django's own mail API,
    which imports smtplib inside .venv where this scan never walks, was
    invisible to a rule written to be categorical.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
            names.add(node.module.split(".")[0])
            # `from django.core import mail` names the same module.
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
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
        #: Django's own mail API, by its dotted name: `from django.core.mail import
        #: send_mail` opens an SMTP connection from inside .venv, where this scan
        #: never walks. This project sends through accounts/mailer.py and nothing
        #: else, so the framework's own channel is forbidden outright.
        "django.core.mail",
    }
)

#: Every module allowed to open an outbound connection, and where each may go.
#:
#: Three. pvgis.py is reached by a web request; ingest_profiles.py is a build
#: time command somebody runs by hand; mailer.py runs under a systemd timer
#: and reaches the mail provider, which is the only destination a household's
#: data ever travels to from this machine. The allowlist is one constant in
#: one module rather than a settings entry, because a configuration layer
#: that exactly one caller reads is a layer that hides where the value comes
#: from. CLAUDE.md names these same destinations since 2026-09-06; before
#: that it named three sources of which one was never reached, and the gap
#: is recorded as answered in docs/decisions.md.
OUTBOUND_MODULES: dict[str, frozenset[str]] = {
    "ampeer_sim/production/pvgis.py": frozenset({"re.jrc.ec.europa.eu"}),
    "tools/ingest_profiles.py": frozenset({"energiedatawijzer.nl"}),
    "backend/accounts/mailer.py": frozenset({"api.resend.com"}),
}

#: The modules whose destination must be a bare constant at the call site.
#:
#: Two, and both are reached from a process nobody watches: pvgis.py by a web
#: request, mailer.py by a timer. ingest_profiles.py hands its URL down
#: through two functions before requests sees it, which the check below
#: cannot follow, so that file is held to a different and separately stated
#: argument.
STRICT_DESTINATION_MODULES = ("ampeer_sim/production/pvgis.py", "backend/accounts/mailer.py")

#: The one network client either of them may import.
#:
#: Named so the assertion below can compare the whole mapping rather than
#: only its keys. Comparing keys was tried on 2026-08-23 and is weaker than
#: what it replaced: adding `import socket` to a module that already imports
#: requests left the set of files unchanged and the test green, while that
#: module gained the ability to open a raw connection.
ALLOWED_CLIENT = "requests"


def _python_sources() -> list[pathlib.Path]:
    """Every Python file in the two pure packages and in the Django project."""
    return sorted(
        path
        for root in (*PACKAGE_ROOTS, BACKEND_ROOT, TOOLS_ROOT)
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


def test_only_these_modules_can_reach_outside_this_machine() -> None:
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
    expected = {module: [ALLOWED_CLIENT] for module in OUTBOUND_MODULES}
    assert reaching == expected, (
        "the set of modules that can open an outbound connection has changed:\n"
        + "\n".join(f"  {name}: {clients}" for name, clients in sorted(reaching.items()))
        + f"\nThe project rule allows {sorted(OUTBOUND_MODULES)} and nothing else, "
        f"each with {ALLOWED_CLIENT} and no other client. Meter data arrives by push "
        "so the backend never fetches, and that is what rules SSRF out as a category "
        "rather than case by case."
    )


@pytest.mark.parametrize("module", STRICT_DESTINATION_MODULES)
def test_the_module_that_speaks_http_never_assembles_its_url(module: str) -> None:
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

    Since 2026-09-06 the same three checks run over accounts/mailer.py.
    """
    path = REPO_ROOT / module
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    # An annotated assignment (RESEND_ENDPOINT: Final = ...) is a constant too;
    # pvgis.py writes its URL unannotated, mailer.py does not, and the check
    # has to see both.
    constants = {
        target.id
        for node in tree.body
        for target in (
            node.targets
            if isinstance(node, ast.Assign)
            else [node.target]
            if isinstance(node, ast.AnnAssign)
            else []
        )
        if isinstance(target, ast.Name) and target.id.isupper()
    }

    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _is_url_literal(node)
    ]
    assert literals, f"no URL literal found in {module}; this test read nothing"
    for url in literals:
        assert url.startswith("https://"), f"{url} is not https"
        host = urlsplit(url).hostname
        allowed = OUTBOUND_MODULES[module]
        assert host in allowed, (
            f"{module} points at {host}, which is not on the allowlist "
            f"{sorted(allowed)}. CLAUDE.md fixes the external sources in config; "
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
        f"no call in {module} carries a timeout, so either the request left "
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


TOOLS_OUTBOUND = "tools/ingest_profiles.py"


def test_the_ingest_tool_points_at_one_host_and_substitutes_only_a_year() -> None:
    """The second outbound module, held to an argument the other test cannot make.

    test_the_module_that_speaks_http_never_assembles_its_url requires the
    destination to be a bare module constant where requests sees it. This file
    cannot satisfy that and is not wrong for it: the URL is formatted once and
    handed down through two functions before requests is called, which an AST
    walk over one expression cannot follow.

    So the safety argument is made here instead, in four parts, and every part
    is checked rather than asserted in prose.

    The URL is one https literal on a one host allowlist. Nothing grows a URL
    out of a value by f-string or by concatenation. The single placeholder in it
    is the year. And argparse declares that year as an int, which is the part
    that carries the weight: a string from the command line could otherwise be
    substituted into the path, and the project rule is that user input supplies
    validated parameters and never pieces of the address.
    """
    path = REPO_ROOT / TOOLS_OUTBOUND
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    literals = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and _is_url_literal(node)
    ]
    assert literals, f"no URL literal found in {TOOLS_OUTBOUND}; this test read nothing"
    allowed = OUTBOUND_MODULES[TOOLS_OUTBOUND]
    for url in literals:
        assert url.startswith("https://"), f"{url} is not https"
        assert urlsplit(url).hostname in allowed, (
            f"{TOOLS_OUTBOUND} points at {urlsplit(url).hostname}, not on {sorted(allowed)}"
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
    assert not assembled, f"a URL is being built rather than named: {assembled}"

    fields = sorted(
        {
            name
            for url in literals
            for _, name, _, _ in string.Formatter().parse(url)
            if name is not None
        }
    )
    assert fields == ["year"], f"the URL substitutes {fields}, and only a year is argued for below"

    typed = [
        keyword.value.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "add_argument"
        and any(
            isinstance(argument, ast.Constant) and argument.value == "year"
            for argument in node.args
        )
        for keyword in node.keywords
        if keyword.arg == "type" and isinstance(keyword.value, ast.Name)
    ]
    assert typed == ["int"], (
        f"the year argument is declared with type={typed}, and int is what keeps a string "
        "from the command line out of the URL path"
    )
