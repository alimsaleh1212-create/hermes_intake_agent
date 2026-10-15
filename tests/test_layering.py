"""Layering rule: route -> service -> repository -> database.

Only ``app/db`` may import SQLAlchemy, so routes and services can never touch a
session or write SQL.

``app/deps.py`` is the wiring layer: it gets every collaborator from an
``app/<concern>/factory.py`` and never builds the repository or the service itself.
"""

import ast
import re
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def test_only_the_db_package_imports_sqlalchemy() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in APP.rglob("*.py")
        if "db" not in path.relative_to(APP).parts[:1]
        and any(m.split(".")[0] == "sqlalchemy" for m in _imported_modules(path))
    ]

    assert offenders == []


def test_routes_do_not_import_the_db_package() -> None:
    offenders = [
        str(path.relative_to(APP))
        for path in (APP / "api").rglob("*.py")
        if any(m.startswith("app.db") for m in _imported_modules(path))
    ]

    assert offenders == []


def test_deps_gets_collaborators_only_from_factories() -> None:
    allowed = re.compile(r"^app\.(\w+\.factory|core\.config|schemas(\..+)?)$")

    offenders = [
        module
        for module in _imported_modules(APP / "deps.py")
        if module.split(".")[0] == "app" and not allowed.match(module)
    ]

    assert offenders == []


def test_deps_does_not_construct_the_repository_or_the_service() -> None:
    tree = ast.parse((APP / "deps.py").read_text())
    constructed = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }

    assert constructed.isdisjoint({"IntakeRepository", "IntakeService"})
