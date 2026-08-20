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


def _imported_module_names(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_packages_never_import_django() -> None:
    offenders = [
        str(path)
        for root in PACKAGE_ROOTS
        for path in root.rglob("*.py")
        if "django" in _imported_module_names(path)
    ]
    assert offenders == [], f"pure packages must not import django: {offenders}"


def test_engine_version_is_declared() -> None:
    assert isinstance(ampeer_sim.ENGINE_VERSION, str)
    assert ampeer_sim.ENGINE_VERSION.count(".") == 2
