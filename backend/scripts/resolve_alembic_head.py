"""Resolve the single Alembic head without importing migration code.

Replaces scripts/resolve-alembic-head.py and updates the migration-directory
path to match the post-Phase-0 layout (backend/alembic/versions, not
services/api/alembic/versions).
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VERSIONS = REPO_ROOT / "backend" / "alembic" / "versions"


def literal_assignment(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        if isinstance(target, ast.Name) and target.id == name and value is not None:
            return ast.literal_eval(value)
    raise ValueError(f"migration is missing a literal {name} assignment")


def resolve_head(versions_dir: Path) -> str:
    revisions: set[str] = set()
    parents: set[str] = set()
    migration_files = sorted(versions_dir.glob("*.py"))
    if not migration_files:
        raise SystemExit(f"no Alembic migrations found in {versions_dir}")

    for migration_file in migration_files:
        try:
            tree = ast.parse(
                migration_file.read_text(encoding="utf-8"), migration_file.name
            )
            revision = literal_assignment(tree, "revision")
            down_revision = literal_assignment(tree, "down_revision")
        except (SyntaxError, ValueError) as exc:
            raise SystemExit(f"cannot inspect {migration_file}: {exc}") from exc
        if not isinstance(revision, str) or not revision:
            raise SystemExit(f"invalid revision in {migration_file}")
        if revision in revisions:
            raise SystemExit(f"duplicate Alembic revision: {revision}")
        revisions.add(revision)
        if isinstance(down_revision, str):
            parents.add(down_revision)
        elif isinstance(down_revision, (tuple, list)):
            if not all(isinstance(parent, str) for parent in down_revision):
                raise SystemExit(f"invalid down_revision in {migration_file}")
            parents.update(down_revision)
        elif down_revision is not None:
            raise SystemExit(f"invalid down_revision in {migration_file}")

    missing_parents = parents - revisions
    if missing_parents:
        raise SystemExit(f"missing Alembic parent revisions: {sorted(missing_parents)}")
    heads = sorted(revisions - parents)
    if len(heads) != 1:
        raise SystemExit(f"expected one Alembic head, found: {heads}")
    return heads[0]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--versions-dir",
        type=Path,
        default=DEFAULT_VERSIONS,
        help=f"Path to the Alembic versions directory (default: {DEFAULT_VERSIONS}).",
    )
    args = parser.parse_args(argv)
    print(resolve_head(args.versions_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
