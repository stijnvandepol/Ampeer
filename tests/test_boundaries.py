"""Structural guarantees that must hold for the whole package."""

from __future__ import annotations

import ast
import pathlib

import ampeer_advice
import ampeer_sim

PACKAGE_ROOTS = (
    pathlib.Path(ampeer_sim.__file__).parent,
    pathlib.Path(ampeer_advice.__file__).parent,
)

#: Django itself, the web framework on top of it, and every top level module
#: that only exists inside backend/.
FORBIDDEN_IN_PURE_PACKAGES = {"django", "rest_framework", "backend", "advice", "ampeer"}

BACKEND_ROOT = pathlib.Path(__file__).resolve().parent.parent / "backend"


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
