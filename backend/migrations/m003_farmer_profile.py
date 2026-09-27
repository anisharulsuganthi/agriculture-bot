"""
Migration 003: Farmer Profile & Personalization Extensions (Phase 7).

Adds farmer profile fields to users table:
- farm_location: Location / Village / District
- land_area_cents: Total farm land in cents
- soil_type: Predominant soil type
- irrigation_source: Primary irrigation availability
- primary_crop: Main cultivated crop
- livestock_owned: Livestock presence
"""
from __future__ import annotations

import sqlite3
from app.logging_config import get_logger

logger = get_logger("migrations.m003")


def apply(conn: sqlite3.Connection) -> dict:
    cursor = conn.cursor()
    columns_added = []
    
    # Check existing columns in users
    cursor.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in cursor.fetchall()}
    
    profile_columns = [
        ("farm_location", "TEXT DEFAULT 'Tamil Nadu, India'"),
        ("land_area_cents", "REAL DEFAULT 50.0"),
        ("soil_type", "TEXT DEFAULT 'Loamy'"),
        ("irrigation_source", "TEXT DEFAULT 'Borewell / Drip'"),
        ("primary_crop", "TEXT DEFAULT 'Tomato'"),
        ("livestock_owned", "TEXT DEFAULT 'Dairy Cattle'")
    ]
    
    for col_name, col_def in profile_columns:
        if col_name not in existing_cols:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
            columns_added.append(col_name)
            
    conn.commit()
    logger.info("Migration 003 applied: added columns %s", columns_added)
    return {
        "migration": "003_farmer_profile",
        "columns_added": columns_added,
        "status": "success"
    }
