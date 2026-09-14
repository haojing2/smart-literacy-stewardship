"""Deployment-time check that the database matches the application's Alembic head."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect

import app.models  # noqa: F401 - register all models used by Alembic metadata
from app.core.config import settings


REQUIRED_TABLES = {"resource_generation_run", "resource_generation_part"}


def main() -> int:
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    application_heads = set(ScriptDirectory.from_config(config).get_heads())

    engine = create_engine(settings.database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            database_heads = set(MigrationContext.configure(connection).get_current_heads())
            tables = set(inspect(connection).get_table_names())
    finally:
        engine.dispose()

    missing_tables = sorted(REQUIRED_TABLES - tables)
    if database_heads != application_heads or missing_tables:
        print("Database schema is behind application schema.", file=sys.stderr)
        print(f"Database revisions: {sorted(database_heads)}", file=sys.stderr)
        print(f"Application heads: {sorted(application_heads)}", file=sys.stderr)
        print(f"Missing required tables: {missing_tables}", file=sys.stderr)
        print("Run: alembic upgrade head", file=sys.stderr)
        return 1

    print(f"Database schema is current: {', '.join(sorted(database_heads))}")
    print("Required progressive generation tables are present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
