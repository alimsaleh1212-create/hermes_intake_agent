"""Layering rule: route -> service -> repository -> database.

Only ``app/db`` may import SQLAlchemy, so routes and services can never touch a
session or write SQL.
"""

import ast
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
