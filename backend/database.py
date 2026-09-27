"""
Database layer (Phase 1 hardened).

Changes from Version 1 (see PROJECT_AUDIT.md):
* the SQLite path is now **absolute** (derived from the project root), so the app
  behaves identically whatever directory it is started from (fixes §1.1 / B3);
* new columns: ``disease_predictions.created_at`` (research analysis),
  ``farming_sessions.ended_at``, ``animal_sessions.ended_at``,
  ``users.otp_attempts`` (OTP brute-force protection);
* schema upgrades run through versioned scripts in ``backend/migrations`` with an
  automatic database backup, instead of ad-hoc ``ALTER TABLE`` attempts;
* existing demo data is preserved - migrations only add columns / assign owners.

Legacy note: ``farming_sessions.created_at`` and ``daily_logs.date`` remain TEXT
(ISO strings) because the Version-1 data is stored that way; read paths use the
``to_date_key()`` helper so both strings and datetimes are handled safely.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

DATABASE_PATH = settings.database_path
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.database_echo,
)

if settings.database_enable_foreign_keys:

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        """
        SQLite ignores FOREIGN KEY clauses unless enforcement is switched on
        per connection, so the ORM declarations were inert in Version 1.
        """
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
        except Exception:  # pragma: no cover - non-sqlite driver
            pass

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def to_date_key(value) -> str:
    """Normalise a stored date (TEXT ISO string or datetime) to 'YYYY-MM-DD'."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value)
    return text.split("T")[0].split(" ")[0]


def to_datetime(value):
    """Best-effort conversion of a stored value to datetime (None when invalid)."""
    if value is None or isinstance(value, datetime):
        return value
    text = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


class DiseasePrediction(Base):
    __tablename__ = "disease_predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    crop_type = Column(String(50), index=True)
    symptoms = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    disease_name = Column(String(100), index=True)
    confidence_score = Column(Float)
    is_healthy = Column(Boolean)
    severity = Column(String(20))
    cure_data = Column(Text)  # JSON stringified
    created_at = Column(DateTime, nullable=True, index=True)


class FarmingSession(Base):
    __tablename__ = "farming_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    crop_type = Column(String(50), index=True)
    plot_name = Column(String(100))
    area_cents = Column(Float)
    soil_type = Column(String(50))
    location = Column(String(100))
    created_at = Column(Text)
    
    # Investment details
    seed_qty = Column(Float, default=0.0)
    cost_per_seed = Column(Float, default=0.0)
    total_land_cost = Column(Float, default=0.0)
    fertilizer_qty = Column(Float, default=0.0)
    cost_per_fertilizer = Column(Float, default=0.0)
    
    # Status
    is_active = Column(Boolean, default=True)
    harvest_yield = Column(Float, nullable=True) # kg
    market_price = Column(Float, nullable=True) # per kg
    ended_at = Column(DateTime, nullable=True)   # Phase 1: harvest timestamp


class DailyLog(Base):
    __tablename__ = "daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True)
    date = Column(Text)
    watered = Column(Boolean, default=False)
    water_reason = Column(String(200), nullable=True)
    fertilized = Column(Boolean, default=False)
    fertilizer_amount = Column(Float, default=0.0)
    weather_condition = Column(String, nullable=True)
    notes = Column(String, nullable=True)

class AnimalSession(Base):
    __tablename__ = "animal_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    animal_type = Column(String, index=True)
    session_name = Column(String)
    animal_count = Column(Integer)
    cost_per_animal = Column(Float)
    initial_food_qty = Column(Float)
    cost_per_food_qty = Column(Float)
    medicine_cost = Column(Float)
    shelter_cost = Column(Float)
    is_active = Column(Boolean, default=True)
    
    # Final sale data
    animals_sold = Column(Integer, default=0)
    sell_price_per_animal = Column(Float, default=0.0)
    total_sale_revenue = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)   # Phase 1: close-out timestamp

class AnimalDailyLog(Base):
    __tablename__ = "animal_daily_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("animal_sessions.id"))
    date = Column(DateTime, default=datetime.utcnow)
    
    food_given_qty = Column(Float)
    food_cost_today = Column(Float)
    
    yield_amount = Column(Float) # liters or eggs
    yield_selling_price = Column(Float)
    
    medicine_given = Column(Boolean, default=False)
    medicine_name = Column(String, nullable=True)
    medicine_cost = Column(Float, default=0.0)
    medicine_reason = Column(String, nullable=True)
    
    deaths_today = Column(Integer, default=0)
    notes = Column(String, nullable=True)

class RecommendationLog(Base):
    __tablename__ = "recommendation_logs"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, index=True)
    date = Column(Text)
    action_type = Column(String(50))
    recommendation = Column(Text)
    reason = Column(Text)
    is_completed = Column(Boolean, default=False)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(200))
    otp = Column(String(200), nullable=True)          # stored as a keyed digest (Phase 2)
    otp_expiry = Column(DateTime, nullable=True)
    otp_attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Farmer Profile & Personalization (Phase 7)
    farm_location = Column(String(100), default="Tamil Nadu, India")
    land_area_cents = Column(Float, default=50.0)
    soil_type = Column(String(50), default="Loamy")
    irrigation_source = Column(String(50), default="Borewell / Drip")
    primary_crop = Column(String(50), default="Tomato")
    livestock_owned = Column(String(100), default="Dairy Cattle")


def init_db() -> dict:
    """
    Create any missing tables, then apply versioned migrations.

    Returns the migration report (also logged) so startup output states exactly
    what was changed. Existing data is preserved - see backend/migrations.
    """
    Base.metadata.create_all(bind=engine)
    try:
        from migrations import run_all
    except ImportError:  # pragma: no cover - direct script execution
        import sys
        from pathlib import Path

        backend_dir = str(Path(__file__).resolve().parent)
        if backend_dir not in sys.path:
            sys.path.insert(0, backend_dir)
        from migrations import run_all
    return run_all()


def run_migrations():
    """
    Deprecated Version-1 ad-hoc migration (kept only for backwards
    compatibility). Superseded by ``migrations.run_all()``.
    """
    return init_db()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
