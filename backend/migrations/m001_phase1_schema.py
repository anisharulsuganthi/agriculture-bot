"""
Migration 001 - Phase 1 schema + data-quality fixes.

Schema
    * disease_predictions.created_at   (new; needed for research analysis)
    * farming_sessions.ended_at        (new; harvest timestamp)
    * animal_sessions.ended_at         (new; close-out timestamp)
    * users.otp_attempts               (new; OTP brute-force protection)

Data (never destructive - only fills gaps / normalises values)
    * backfill disease_predictions.created_at for legacy rows
    * normalise crop_type through the canonical vocabulary (Tomato/tomato/potato)
    * assign orphaned rows (user_id IS NULL) to a real account so the original
      demo data stays visible instead of being filtered out of every dashboard

Nothing is deleted. A full database backup is written by the runner beforehand.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Dict

from app.crop_vocab import normalize_crop_type
from app.logging_config import get_logger
from migrations.runner import add_column_if_missing

logger = get_logger("migration.001")


def _resolve_legacy_owner(conn: sqlite3.Connection) -> tuple[int | None, str]:
    """Pick the account that should own orphaned legacy rows."""
    from app.config import settings

    wanted_email = (settings.legacy_data_owner_email or "").strip().lower()
    if wanted_email:
        row = conn.execute("SELECT id FROM users WHERE lower(email) = ?", (wanted_email,)).fetchone()
        if row:
            return int(row[0]), wanted_email
        logger.warning(
            "LEGACY_DATA_OWNER_EMAIL=%s does not exist; falling back to the lowest user id",
            wanted_email,
        )
    row = conn.execute("SELECT id, email FROM users ORDER BY id ASC LIMIT 1").fetchone()
    if not row:
        return None, ""
    return int(row[0]), str(row[1])


def _normalise_crops(conn: sqlite3.Connection) -> Dict[str, str]:
    """Rewrite non-canonical crop names; returns {old: new} for the report."""
    changes: Dict[str, str] = {}
    rows = conn.execute("SELECT DISTINCT crop_type FROM farming_sessions").fetchall()
    for (raw,) in rows:
        if raw is None:
            continue
        canonical = normalize_crop_type(raw)
        if canonical != raw:
            conn.execute("UPDATE farming_sessions SET crop_type = ? WHERE crop_type = ?", (canonical, raw))
            changes[str(raw)] = canonical
    return changes


def _normalise_animal_types(conn: sqlite3.Connection) -> Dict[str, str]:
    changes: Dict[str, str] = {}
    rows = conn.execute("SELECT DISTINCT animal_type FROM animal_sessions").fetchall()
    for (raw,) in rows:
        if raw is None:
            continue
        canonical = str(raw).strip().title()
        if canonical != raw:
            conn.execute("UPDATE animal_sessions SET animal_type = ? WHERE animal_type = ?", (canonical, raw))
            changes[str(raw)] = canonical
    return changes


def apply(conn: sqlite3.Connection) -> dict:
    report: dict = {"schema": [], "data": {}}

    # ---------------- schema ----------------
    if add_column_if_missing(conn, "disease_predictions", "created_at", "DATETIME"):
        report["schema"].append("disease_predictions.created_at")
    if add_column_if_missing(conn, "farming_sessions", "ended_at", "DATETIME"):
        report["schema"].append("farming_sessions.ended_at")
    if add_column_if_missing(conn, "animal_sessions", "ended_at", "DATETIME"):
        report["schema"].append("animal_sessions.ended_at")
    if add_column_if_missing(conn, "users", "otp_attempts", "INTEGER DEFAULT 0"):
        report["schema"].append("users.otp_attempts")

    # ---------------- data ----------------
    now = datetime.utcnow().isoformat(sep=" ")
    cur = conn.execute("UPDATE disease_predictions SET created_at = ? WHERE created_at IS NULL", (now,))
    report["data"]["predictions_timestamped"] = cur.rowcount

    crop_changes = _normalise_crops(conn)
    report["data"]["crop_type_normalised"] = crop_changes

    animal_changes = _normalise_animal_types(conn)
    report["data"]["animal_type_normalised"] = animal_changes

    owner_id, owner_email = _resolve_legacy_owner(conn)
    assigned = 0
    if owner_id is not None:
        for table in ("farming_sessions", "animal_sessions", "disease_predictions"):
            cur = conn.execute(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL", (owner_id,))
            assigned += max(cur.rowcount, 0)
        report["data"]["legacy_rows_reassigned"] = {"count": assigned, "owner_id": owner_id, "owner_email": owner_email}
        logger.info("Assigned %s orphaned legacy rows to user %s (%s)", assigned, owner_id, owner_email)
    else:
        report["data"]["legacy_rows_reassigned"] = {"count": 0, "reason": "no users exist yet"}

    conn.commit()
    return report
