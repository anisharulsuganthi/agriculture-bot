"""
Migration runner (Phase 1).

Design
------
* Versioned, ordered, idempotent migrations recorded in ``schema_migrations``.
* A timestamped copy of the database is written to ``backend/backups`` before the
  first pending migration runs, so nothing is ever lost.
* Each migration returns a report dict; the runner logs it and hands it back to
  the caller (``init_db()``), which returns it from application startup.
"""
from __future__ import annotations

import importlib
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:  # allow "python main.py" and pytest alike
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402  (path setup must happen first)
from app.logging_config import get_logger  # noqa: E402

logger = get_logger("migrations")

MIGRATION_TABLE = "schema_migrations"

# (version, module, human readable name)
MIGRATIONS: List[Tuple[int, str, str]] = [
    (1, "migrations.m001_phase1_schema", "Phase 1 schema + data fixes"),
    (2, "migrations.m002_referential_integrity", "Declare the foreign keys and indexes the ORM expects"),
    (3, "migrations.m003_farmer_profile", "Farmer profile fields for personalization"),
]


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(str(settings.database_path))


def ensure_migration_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MIGRATION_TABLE} (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL,
            report TEXT
        )
        """
    )
    conn.commit()


def applied_versions(conn: sqlite3.Connection) -> set[int]:
    ensure_migration_table(conn)
    rows = conn.execute(f"SELECT version FROM {MIGRATION_TABLE}").fetchall()
    return {int(row[0]) for row in rows}


def backup_database(tag: str = "pre_migration") -> Path | None:
    """
    Copy the database aside before a migration runs.

    The backup is written next to the database itself (``<db dir>/backups``) so a
    test database in a temporary directory never writes into the project tree,
    while the real database keeps its backups in ``backend/backups``.
    """
    source = settings.database_path
    if not source.exists():
        return None
    backup_dir = source.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = backup_dir / f"{source.stem}_{tag}_{stamp}.db"
    shutil.copy2(source, target)
    logger.info("Database backed up to %s", target)
    return target


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(str(row[1]).lower() == column.lower() for row in rows)


def add_column_if_missing(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> bool:
    """Add a column when absent. Returns True when the schema changed."""
    if column_exists(conn, table, column):
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    conn.commit()
    logger.info("Schema: added %s.%s", table, column)
    return True


def run_all() -> Dict[str, object]:
    """Apply pending migrations in order and return a report."""
    report: Dict[str, object] = {"applied": [], "skipped": [], "backup": None, "details": {}}

    with _connect() as conn:
        done = applied_versions(conn)

    pending = [(v, m, n) for (v, m, n) in MIGRATIONS if v not in done]
    if not pending:
        logger.debug("Migrations: database already at version %s", max(done) if done else 0)
        report["current_version"] = max(done) if done else 0
        return report

    backup = backup_database()
    report["backup"] = str(backup) if backup else None

    for version, module_path, name in pending:
        module = importlib.import_module(module_path)
        with _connect() as conn:
            try:
                detail = module.apply(conn)
                conn.execute(
                    f"INSERT OR REPLACE INTO {MIGRATION_TABLE} (version, name, applied_at, report) VALUES (?,?,?,?)",
                    (version, name, datetime.utcnow().isoformat(), str(detail)),
                )
                conn.commit()
                logger.info("Applied migration %s (%s)", version, name)
                report["applied"].append({"version": version, "name": name, "detail": detail})  # type: ignore[union-attr]
                report["details"][str(version)] = detail  # type: ignore[index]
            except Exception as exc:  # noqa: BLE001 - surface any failure loudly
                conn.rollback()
                logger.error("Migration %s failed: %s", version, exc)
                raise

    with _connect() as conn:
        report["current_version"] = max(applied_versions(conn))
    return report


def get_migration_callable(module_path: str) -> Callable:  # pragma: no cover - helper
    return importlib.import_module(module_path).apply
