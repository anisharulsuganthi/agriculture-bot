import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./database.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class DiseasePrediction(Base):
    __tablename__ = "disease_predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    crop_type = Column(String(50), index=True)
    symptoms = Column(Text, nullable=True)
    location = Column(String(100), nullable=True)
    disease_name = Column(String(100), index=True)
    confidence_score = Column(Float)
    is_healthy = Column(Boolean)
    severity = Column(String(20))
    cure_data = Column(Text) # JSON stringified

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
    otp = Column(String(10), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

def run_migrations():
    import sqlite3
    db_path = "./database.db"
    if not os.path.exists(db_path) and os.path.exists("backend/database.db"):
        db_path = "backend/database.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check and add user_id to farming_sessions
        try:
            cursor.execute("SELECT user_id FROM farming_sessions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE farming_sessions ADD COLUMN user_id INTEGER DEFAULT NULL")
            print("Migration: Added user_id to farming_sessions")
            
        # Check and add user_id to animal_sessions
        try:
            cursor.execute("SELECT user_id FROM animal_sessions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE animal_sessions ADD COLUMN user_id INTEGER DEFAULT NULL")
            print("Migration: Added user_id to animal_sessions")
            
        # Check and add user_id to disease_predictions
        try:
            cursor.execute("SELECT user_id FROM disease_predictions LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE disease_predictions ADD COLUMN user_id INTEGER DEFAULT NULL")
            print("Migration: Added user_id to disease_predictions")
            
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

def init_db():
    Base.metadata.create_all(bind=engine)
    run_migrations()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
