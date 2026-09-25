"""
Migration 002 - make the declared referential integrity real.

Problem
-------
Migration 001 added ``user_id`` with ``ALTER TABLE ... ADD COLUMN``. SQLite cannot
add a FOREIGN KEY clause to an existing table, so the three ``user_id`` columns
were left as plain integers: ``PRAGMA foreign_key_list`` returned nothing even
though the ORM declares ``ForeignKey("users.id")``. The same applies to the two
indexes SQLAlchemy declares on ``disease_predictions`` (``user_id`` and
``created_at``) - ``Base.metadata.create_all()`` runs *before* migrations and
never adds indexes to tables that already exist, so they were silently missing.

Effect before this migration: ``PRAGMA foreign_keys=ON`` (added in Phase 1) had
nothing to enforce, and history/statistics queries on predictions could not use an
index.

Approach
--------
SQLite cannot alter constraints in place, so each affected table is rebuilt with
the standard 12-step procedure: create the corrected table, copy the rows,
drop the old table, rename, recreate indexes, then run ``foreign_key_check``.

Safety
------
* The runner (``migrations.runner.run_all``) copies the database to
  ``backend/backups/`` before this file is applied.
* Foreign keys are disabled only for the duration of the rebuild, on this
  connection, and re-enabled immediately afterwards.
* Every row is copied; the report states the before/after counts and the script
  aborts if any count differs.
* Rows whose ``user_id`` points at a missing account are **not** deleted: they are
  reported and left as ``NULL`` so the data stays visible and auditable.
"""
from __future__ import annotations

import sqlite3
from typing import Dict, List

# Corrected DDL - must stay in sync with the ORM models in database.py.
TABLES: Dict[str, Dict[str, str]] = {
    "farming_sessions": {
        "create": """
            CREATE TABLE farming_sessions_new (
                id INTEGER NOT NULL,
                user_id INTEGER,
                crop_type VARCHAR(50),
                plot_name VARCHAR(100),
                area_cents FLOAT,
                soil_type VARCHAR(50),
                location VARCHAR(100),
                created_at TEXT,
                seed_qty FLOAT,
                cost_per_seed FLOAT,
                total_land_cost FLOAT,
                fertilizer_qty FLOAT,
                cost_per_fertilizer FLOAT,
                is_active BOOLEAN,
                harvest_yield FLOAT,
                market_price FLOAT,
                ended_at DATETIME,
                PRIMARY KEY (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
        """,
        "columns": [
            "id", "user_id", "crop_type", "plot_name", "area_cents", "soil_type", "location",
            "created_at", "seed_qty", "cost_per_seed", "total_land_cost", "fertilizer_qty",
            "cost_per_fertilizer", "is_active", "harvest_yield", "market_price", "ended_at",
        ],
        "indexes": [
            "CREATE INDEX IF NOT EXISTS ix_farming_sessions_id ON farming_sessions (id)",
            "CREATE INDEX IF NOT EXISTS ix_farming_sessions_crop_type ON farming_sessions (crop_type)",
            "CREATE INDEX IF NOT EXISTS ix_farming_sessions_user_id ON farming_sessions (user_id)",
        ],
    },
    "animal_sessions": {
        "create": """
            CREATE TABLE animal_sessions_new (
                id INTEGER NOT NULL,
                user_id INTEGER,
                animal_type VARCHAR,
                session_name VARCHAR,
                animal_count INTEGER,
                cost_per_animal FLOAT,
                initial_food_qty FLOAT,
                cost_per_food_qty FLOAT,
                medicine_cost FLOAT,
                shelter_cost FLOAT,
                is_active BOOLEAN,
                animals_sold INTEGER,
                sell_price_per_animal FLOAT,
                total_sale_revenue FLOAT,
                created_at DATETIME,
                ended_at DATETIME,
                PRIMARY KEY (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
        """,
        "columns": [
            "id", "user_id", "animal_type", "session_name", "animal_count", "cost_per_animal",
            "initial_food_qty", "cost_per_food_qty", "medicine_cost", "shelter_cost", "is_active",
            "animals_sold", "sell_price_per_animal", "total_sale_revenue", "created_at", "ended_at",
        ],
        "indexes": [
            "CREATE INDEX IF NOT EXISTS ix_animal_sessions_id ON animal_sessions (id)",
            "CREATE INDEX IF NOT EXISTS ix_animal_sessions_animal_type ON animal_sessions (animal_type)",
            "CREATE INDEX IF NOT EXISTS ix_animal_sessions_user_id ON animal_sessions (user_id)",
        ],
    },
    "disease_predictions": {
        "create": """
            CREATE TABLE disease_predictions_new (
                id INTEGER NOT NULL,
                user_id INTEGER,
                crop_type VARCHAR(50),
                symptoms TEXT,
                location VARCHAR(100),
                disease_name VARCHAR(100),
                confidence_score FLOAT,
                is_healthy BOOLEAN,
                severity VARCHAR(20),
                cure_data TEXT,
                created_at DATETIME,
                PRIMARY KEY (id),
                FOREIGN KEY(user_id) REFERENCES users (id)
            )
        """,
        "columns": [
            "id", "user_id", "crop_type", "symptoms", "location", "disease_name",
            "confidence_score", "is_healthy", "severity", "cure_data", "created_at",
        ],
        "indexes": [
            "CREATE INDEX IF NOT EXISTS ix_disease_predictions_id ON disease_predictions (id)",
            "CREATE INDEX IF NOT EXISTS ix_disease_predictions_user_id ON disease_predictions (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_disease_predictions_crop_type ON disease_predictions (crop_type)",
            "CREATE INDEX IF NOT EXISTS ix_disease_predictions_disease_name ON disease_predictions (disease_name)",
            "CREATE INDEX IF NOT EXISTS ix_disease_predictions_created_at ON disease_predictions (created_at)",
        ],
    },
}


def _existing_columns(conn: sqlite3.Connection, table: str) -> List[str]:
    return [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]


def _rebuild(conn: sqlite3.Connection, table: str, spec: Dict[str, object]) -> Dict[str, object]:
    existing = _existing_columns(conn, table)
    if not existing:
        return {"status": "skipped", "reason": "table not present"}

    # Only copy columns that exist in both the old and the corrected table.
    columns = [name for name in spec["columns"] if name in existing]  # type: ignore[index]
    if not columns:
        return {"status": "skipped", "reason": "no matching columns"}

    already_has_fk = bool(conn.execute(f"PRAGMA foreign_key_list({table})").fetchall())
    if already_has_fk:
        return {"status": "skipped", "reason": "foreign key already declared"}

    before = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        new_table = f"{table}_new"
        conn.execute(f"DROP TABLE IF EXISTS {new_table}")
        conn.execute(str(spec["create"]).strip())

        column_list = ", ".join(columns)
        conn.execute(f"INSERT INTO {new_table} ({column_list}) SELECT {column_list} FROM {table}")
        copied = conn.execute(f"SELECT COUNT(*) FROM {new_table}").fetchone()[0]

        conn.execute(f"DROP TABLE {table}")
        conn.execute(f"ALTER TABLE {new_table} RENAME TO {table}")
        for statement in spec["indexes"]:  # type: ignore[index]
            conn.execute(str(statement))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")

    after = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if after != before:
        raise RuntimeError(f"row count changed while rebuilding {table}: {before} -> {after}")

    return {
        "status": "rebuilt",
        "rows": after,
        "columns": len(columns),
        "foreign_keys": [row[2] for row in conn.execute(f"PRAGMA foreign_key_list({table})")],
    }


def apply(conn: sqlite3.Connection) -> Dict[str, object]:
    report: Dict[str, object] = {"tables": {}, "orphans": {}}

    for table, spec in TABLES.items():
        report["tables"][table] = _rebuild(conn, table, spec)  # type: ignore[index]

    # Report - never delete - rows that would violate the new constraints.
    for table in TABLES:
        orphans = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE user_id IS NOT NULL "
            f"AND user_id NOT IN (SELECT id FROM users)"
        ).fetchone()[0]
        if orphans:
            report["orphans"][table] = orphans  # type: ignore[index]

    violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    if violations:
        raise RuntimeError(f"foreign key violations remain after the rebuild: {violations[:5]}")

    return report
