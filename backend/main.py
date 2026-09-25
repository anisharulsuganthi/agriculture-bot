
from fastapi import FastAPI, File, Form, UploadFile, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json
import hashlib
import random
from datetime import datetime, timedelta
from typing import List, Optional

from database import SessionLocal, engine, DiseasePrediction, FarmingSession, DailyLog, RecommendationLog, init_db, get_db, AnimalSession, AnimalDailyLog, User
from ml_service import load_or_download_model, predict_image
from grok_service import get_cure_for_disease
from weather_service import get_current_weather, get_forecast
from climate_engine import assess_disease_risk
from recommendation_engine import generate_watering_recommendation, generate_fertilizing_recommendation
from notification_service import send_email_alert, format_alert_message, send_otp_email
from pydantic import BaseModel

def hash_password(password: str) -> str:
    salt = "smartfarm_secret_salt_123"
    return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

class UserRegister(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class ForgotPasswordRequest(BaseModel):
    email: str

class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
    new_password: str

class SessionCreate(BaseModel):
    crop_type: str
    plot_name: str
    area_cents: float
    soil_type: str
    location: str
    seed_qty: float = 0.0
    cost_per_seed: float = 0.0
    total_land_cost: float = 0.0
    fertilizer_qty: float = 0.0
    cost_per_fertilizer: float = 0.0

class DailyLogCreate(BaseModel):
    watered: bool
    water_reason: str = ""
    fertilized: bool
    fertilizer_amount: float = 0.0
    weather_condition: str = ""
    notes: str = ""

class HarvestCreate(BaseModel):
    harvest_yield: float
    market_price: float

class AnimalSessionCreate(BaseModel):
    animal_type: str
    session_name: str
    animal_count: int
    cost_per_animal: float
    initial_food_qty: float
    cost_per_food_qty: float
    medicine_cost: float
    shelter_cost: float

class AnimalDailyLogCreate(BaseModel):
    food_given_qty: float
    food_cost_today: float
    yield_amount: float
    yield_selling_price: float
    medicine_given: bool
    medicine_name: Optional[str] = None
    medicine_cost: float = 0.0
    medicine_reason: Optional[str] = None
    deaths_today: int = 0
    notes: Optional[str] = None

class AnimalSessionClose(BaseModel):
    animals_sold: int
    sell_price_per_animal: float

app = FastAPI(title="Smart Farm API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()
    try:
        load_or_download_model()
    except Exception as e:
        print(f"Warning: Failed to load ML model on startup: {e}")

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.post("/api/auth/register")
def register_endpoint(user_data: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    
    hashed = hash_password(user_data.password)
    user = User(
        name=user_data.name,
        email=user_data.email.lower(),
        hashed_password=hashed
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {
        "status": "success",
        "message": "Account created successfully!",
        "user": {"id": user.id, "name": user.name, "email": user.email}
    }

@app.post("/api/auth/login")
def login_endpoint(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email.lower()).first()
    if not user or user.hashed_password != hash_password(user_data.password):
        raise HTTPException(status_code=400, detail="Invalid email or password.")
        
    return {
        "status": "success",
        "message": "Logged in successfully!",
        "user": {"id": user.id, "name": user.name, "email": user.email, "created_at": user.created_at.isoformat() if user.created_at else None}
    }

@app.post("/api/auth/forgot-password")
def forgot_password_endpoint(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="No account found with this email.")
        
    # Generate 6-digit OTP
    otp = f"{random.randint(100000, 999999)}"
    user.otp = otp
    user.otp_expiry = datetime.now() + timedelta(minutes=10)
    db.commit()
    
    email_res = send_otp_email(user.email, otp)
    if email_res["status"] == "error":
        raise HTTPException(status_code=500, detail=f"Failed to send OTP email: {email_res['message']}")
        
    return {"status": "success", "message": "OTP has been sent to your email."}

@app.post("/api/auth/reset-password")
def reset_password_endpoint(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email.lower()).first()
    if not user or not user.otp:
        raise HTTPException(status_code=400, detail="Invalid request.")
        
    if user.otp != request.otp:
        raise HTTPException(status_code=400, detail="Incorrect OTP.")
        
    if datetime.now() > user.otp_expiry:
        raise HTTPException(status_code=400, detail="OTP has expired.")
        
    # Valid OTP. Update password
    user.hashed_password = hash_password(request.new_password)
    user.otp = None
    user.otp_expiry = None
    db.commit()
    
    return {"status": "success", "message": "Password updated successfully! You can now log in."}

@app.get("/api/auth/user-stats")
def get_user_stats(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    u_id = int(x_user_id)
    
    plant_count = db.query(FarmingSession).filter(FarmingSession.user_id == u_id).count()
    active_plant = db.query(FarmingSession).filter(FarmingSession.user_id == u_id, FarmingSession.is_active == True).count()
    animal_count = db.query(AnimalSession).filter(AnimalSession.user_id == u_id).count()
    active_animal = db.query(AnimalSession).filter(AnimalSession.user_id == u_id, AnimalSession.is_active == True).count()
    predictions = db.query(DiseasePrediction).filter(DiseasePrediction.user_id == u_id).count()
    
    return {
        "plant_count": plant_count,
        "active_plant": active_plant,
        "animal_count": animal_count,
        "active_animal": active_animal,
        "predictions": predictions
    }

@app.post("/api/predict/disease")
async def predict_disease_endpoint(
    image: UploadFile = File(...),
    crop_type: str = Form("Unknown"),
    symptoms: str = Form(""),
    location: str = Form("Tamil Nadu, India"),
    x_user_id: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")
        
    image_bytes = await image.read()
    
    try:
        prediction = predict_image(image_bytes)
    except Exception as e:
        import traceback
        with open("error.log", "w") as f:
            f.write(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"ML Prediction failed: {e}")

    detections = prediction.get("detections", [])
    annotated_image = prediction.get("annotated_image_base64", "")
    
    # Use top detection for cure and DB stats
    if detections:
        top_detection = detections[0]
        disease_name = top_detection["label"]
        confidence_score = top_detection["score"]
        is_healthy = False
        severity = "Severe" if confidence_score > 90 else ("Moderate" if confidence_score > 70 else "Mild")
    else:
        disease_name = "Healthy"
        confidence_score = 100.0
        is_healthy = True
        severity = "None"

    cure = get_cure_for_disease(disease_name, crop_type, location)

    db_record = DiseasePrediction(
        user_id=int(x_user_id) if x_user_id else None,
        crop_type=crop_type,
        symptoms=symptoms,
        location=location,
        disease_name=disease_name,
        confidence_score=confidence_score,
        is_healthy=is_healthy,
        severity=severity,
        cure_data=json.dumps(cure)
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)

    return {
        "prediction": {
            "id": db_record.id,
            "disease_name": disease_name,
            "confidence_score": confidence_score,
            "is_healthy": is_healthy,
            "severity": severity,
            "detections": detections,
            "annotated_image_base64": annotated_image
        },
        "cure": cure
    }

@app.get("/api/sessions")
def list_sessions(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    query = db.query(FarmingSession)
    if x_user_id:
        query = query.filter(FarmingSession.user_id == int(x_user_id))
    sessions = query.all()
    return sessions

@app.post("/api/sessions")
def create_session(session_data: SessionCreate, x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    db_record = FarmingSession(
        user_id=int(x_user_id) if x_user_id else None,
        crop_type=session_data.crop_type,
        plot_name=session_data.plot_name,
        area_cents=session_data.area_cents,
        soil_type=session_data.soil_type,
        location=session_data.location,
        seed_qty=session_data.seed_qty,
        cost_per_seed=session_data.cost_per_seed,
        total_land_cost=session_data.total_land_cost,
        fertilizer_qty=session_data.fertilizer_qty,
        cost_per_fertilizer=session_data.cost_per_fertilizer,
        is_active=True,
        created_at=datetime.now().isoformat()
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return {"status": "success", "session_id": db_record.id, "message": "Farming session created"}

@app.post("/api/sessions/{session_id}/daily_logs")
def create_daily_log(session_id: int, log_data: DailyLogCreate, db: Session = Depends(get_db)):
    session = db.query(FarmingSession).filter(FarmingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    db_log = DailyLog(
        session_id=session_id,
        date=datetime.now().isoformat(),
        watered=log_data.watered,
        water_reason=log_data.water_reason,
        fertilized=log_data.fertilized,
        fertilizer_amount=log_data.fertilizer_amount,
        weather_condition=log_data.weather_condition,
        notes=log_data.notes
    )
    db.add(db_log)
    db.commit()
    return {"status": "success", "message": "Daily log added"}

@app.get("/api/sessions/{session_id}/daily_logs")
def get_daily_logs(session_id: int, db: Session = Depends(get_db)):
    logs = db.query(DailyLog).filter(DailyLog.session_id == session_id).all()
    return logs

@app.post("/api/sessions/{session_id}/harvest")
def harvest_session(session_id: int, harvest_data: HarvestCreate, db: Session = Depends(get_db)):
    session = db.query(FarmingSession).filter(FarmingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.is_active = False
    session.harvest_yield = harvest_data.harvest_yield
    session.market_price = harvest_data.market_price
    db.commit()
    return {"status": "success", "message": "Session harvested successfully"}

# ==========================================
# Animal Farm API
# ==========================================

@app.post("/api/animals")
def create_animal_session(session_data: AnimalSessionCreate, x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    new_session = AnimalSession(
        user_id=int(x_user_id) if x_user_id else None,
        **session_data.dict()
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return {"status": "success", "session_id": new_session.id}

@app.get("/api/animals")
def get_animal_sessions(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    query = db.query(AnimalSession)
    if x_user_id:
        query = query.filter(AnimalSession.user_id == int(x_user_id))
    sessions = query.all()
    return sessions

@app.post("/api/animals/{session_id}/daily_logs")
def add_animal_daily_log(session_id: int, log_data: AnimalDailyLogCreate, db: Session = Depends(get_db)):
    session = db.query(AnimalSession).filter(AnimalSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    new_log = AnimalDailyLog(session_id=session_id, **log_data.dict())
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return {"status": "success", "log_id": new_log.id}

@app.get("/api/animals/{session_id}/daily_logs")
def get_animal_daily_logs(session_id: int, db: Session = Depends(get_db)):
    logs = db.query(AnimalDailyLog).filter(AnimalDailyLog.session_id == session_id).order_by(AnimalDailyLog.date.desc()).all()
    return logs

@app.post("/api/animals/{session_id}/close")
def close_animal_session(session_id: int, close_data: AnimalSessionClose, db: Session = Depends(get_db)):
    session = db.query(AnimalSession).filter(AnimalSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    session.is_active = False
    session.animals_sold = close_data.animals_sold
    session.sell_price_per_animal = close_data.sell_price_per_animal
    session.total_sale_revenue = close_data.animals_sold * close_data.sell_price_per_animal
    
    db.commit()
    return {"status": "success"}

@app.get("/api/animals/dashboard/summary")
def get_animal_dashboard_summary(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    query = db.query(AnimalSession)
    if x_user_id:
        query = query.filter(AnimalSession.user_id == int(x_user_id))
    sessions = query.all()
    
    total_investment = 0.0
    total_yield = 0.0
    total_revenue = 0.0
    
    for s in sessions:
        # Initial Investment
        investment = (s.animal_count * s.cost_per_animal) + \
                     (s.initial_food_qty * s.cost_per_food_qty) + \
                     s.medicine_cost + s.shelter_cost
                     
        # Daily Logs
        logs = db.query(AnimalDailyLog).filter(AnimalDailyLog.session_id == s.id).all()
        revenue = 0.0
        
        for log in logs:
            investment += log.food_cost_today + log.medicine_cost
            total_yield += log.yield_amount
            revenue += (log.yield_amount * log.yield_selling_price)
            
        # Add the final sale revenue if closed
        if not s.is_active and s.total_sale_revenue:
            revenue += s.total_sale_revenue
            
        total_investment += investment
        total_revenue += revenue
        
    net_profit = total_revenue - total_investment
    profit_margin = (net_profit / total_investment * 100) if total_investment > 0 else 0
    
    return {
        "total_investment": round(total_investment, 2),
        "total_yield": round(total_yield, 2),
        "total_revenue": round(total_revenue, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin_percent": round(profit_margin, 2),
        "active_sessions": len([s for s in sessions if s.is_active]),
        "completed_sessions": len([s for s in sessions if not s.is_active])
    }

@app.get("/api/animals/dashboard/analytics")
def get_animal_analytics(session_id: Optional[int] = None, x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    query = db.query(AnimalSession)
    if x_user_id:
        query = query.filter(AnimalSession.user_id == int(x_user_id))
    if session_id:
        sessions = query.filter(AnimalSession.id == session_id).all()
    else:
        sessions = query.all()
    
    total_animal_cost = 0.0
    total_food_cost = 0.0
    total_med_cost = 0.0
    total_shelter_cost = 0.0
    
    performance = []
    animal_distribution = {}
    resource_timeline_dict = {}
    
    for s in sessions:
        # Cost breakdown
        initial_animal = s.animal_count * s.cost_per_animal
        initial_food = s.initial_food_qty * s.cost_per_food_qty
        
        # Animal Distribution
        if s.animal_type not in animal_distribution:
            animal_distribution[s.animal_type] = 0
        animal_distribution[s.animal_type] += s.animal_count
        
        total_animal_cost += initial_animal
        total_food_cost += initial_food
        total_med_cost += s.medicine_cost
        total_shelter_cost += s.shelter_cost
        
        logs = db.query(AnimalDailyLog).filter(AnimalDailyLog.session_id == s.id).all()
        
        for log in logs:
            if isinstance(log.date, str):
                date_str = log.date.split("T")[0].split(" ")[0]
            else:
                date_str = log.date.strftime("%Y-%m-%d")
            if date_str not in resource_timeline_dict:
                resource_timeline_dict[date_str] = {"yield": 0.0, "food_cost": 0.0}
            resource_timeline_dict[date_str]["yield"] += log.yield_amount
            resource_timeline_dict[date_str]["food_cost"] += log.food_cost_today
        
        daily_food = sum(log.food_cost_today for log in logs)
        daily_med = sum(log.medicine_cost for log in logs)
        
        total_food_cost += daily_food
        total_med_cost += daily_med
        
        # Performance for all sessions (active and completed)
        investment = initial_animal + initial_food + s.medicine_cost + s.shelter_cost + daily_food + daily_med
        daily_revenue = sum((log.yield_amount * log.yield_selling_price) for log in logs)
        total_yield = sum(log.yield_amount for log in logs)
        final_sale_revenue = s.total_sale_revenue or 0.0
        revenue = daily_revenue + final_sale_revenue
        profit = revenue - investment
        
        status_label = "(Active)" if s.is_active else "(Ended)"
        
        performance.append({
            "session_id": s.id,
            "plot_name": f"{s.session_name} {status_label}",
            "animal_count": s.animal_count,
            "total_yield": round(total_yield, 2),
            "investment": round(investment, 2),
            "revenue": round(revenue, 2),
            "profit": round(profit, 2)
        })
            
    # Sort by yield descending for High Yield Board
    performance.sort(key=lambda x: x["total_yield"], reverse=True)
    
    sorted_dates = sorted(list(resource_timeline_dict.keys()))
    timeline_dates = []
    cumulative_yield = []
    cumulative_food_cost = []
    
    current_yield = 0.0
    current_food = 0.0
    for d in sorted_dates:
        current_yield += resource_timeline_dict[d]["yield"]
        current_food += resource_timeline_dict[d]["food_cost"]
        timeline_dates.append(d)
        cumulative_yield.append(round(current_yield, 2))
        cumulative_food_cost.append(round(current_food, 2))
            
    return {
        "cost_breakdown": {
            "labels": ["Animals", "Food", "Medicine", "Shelter"],
            "data": [
                round(total_animal_cost, 2),
                round(total_food_cost, 2),
                round(total_med_cost, 2),
                round(total_shelter_cost, 2)
            ]
        },
        "session_performance": performance,
        "animal_distribution": {
            "labels": list(animal_distribution.keys()),
            "data": list(animal_distribution.values())
        },
        "resource_timeline": {
            "dates": timeline_dates,
            "yield": cumulative_yield,
            "food_cost": cumulative_food_cost
        }
    }

@app.get("/api/dashboard/summary")
def get_dashboard_summary(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    query = db.query(FarmingSession)
    if x_user_id:
        query = query.filter(FarmingSession.user_id == int(x_user_id))
    sessions = query.all()
    
    total_investment = 0.0
    total_yield = 0.0
    total_revenue = 0.0
    
    for s in sessions:
        # Seed + Land + Initial Fertilizer
        inv = (s.seed_qty * s.cost_per_seed) + s.total_land_cost + (s.fertilizer_qty * s.cost_per_fertilizer)
        
        # Add daily log fertilizers
        logs = db.query(DailyLog).filter(DailyLog.session_id == s.id).all()
        for log in logs:
            if log.fertilized:
                inv += (log.fertilizer_amount * s.cost_per_fertilizer)
                
        total_investment += inv
        
        if not s.is_active and s.harvest_yield and s.market_price:
            total_yield += s.harvest_yield
            total_revenue += (s.harvest_yield * s.market_price)
            
    net_profit = total_revenue - total_investment
    profit_margin = (net_profit / total_investment * 100) if total_investment > 0 else 0.0
    
    return {
        "total_investment": round(total_investment, 2),
        "total_yield": round(total_yield, 2),
        "total_revenue": round(total_revenue, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin_percent": round(profit_margin, 2),
        "active_sessions": len([s for s in sessions if s.is_active]),
        "completed_sessions": len([s for s in sessions if not s.is_active])
    }

@app.get("/api/dashboard/analytics")
def get_dashboard_analytics(session_id: Optional[int] = None, x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    query = db.query(FarmingSession)
    if x_user_id:
        query = query.filter(FarmingSession.user_id == int(x_user_id))
    if session_id:
        sessions = query.filter(FarmingSession.id == session_id).all()
    else:
        sessions = query.all()
    
    # Cost Breakdown
    total_seeds_cost = 0.0
    total_land_cost = 0.0
    total_fertilizer_cost = 0.0
    
    # Session Performance
    performance = []
    
    # Detailed Analytics Aggregation
    summary_investment = 0.0
    summary_revenue = 0.0
    summary_profit = 0.0
    active_area_cents = 0.0
    
    crop_distribution = {}
    resource_timeline_dict = {}
    
    for s in sessions:
        seed_cost = s.seed_qty * s.cost_per_seed
        land_cost = s.total_land_cost
        fert_cost = s.fertilizer_qty * s.cost_per_fertilizer
        
        # Crop Distribution
        if s.crop_type not in crop_distribution:
            crop_distribution[s.crop_type] = 0.0
        crop_distribution[s.crop_type] += s.area_cents
        
        if s.is_active:
            active_area_cents += s.area_cents
            
        # Add daily log fertilizers and watering
        logs = db.query(DailyLog).filter(DailyLog.session_id == s.id).all()
        for log in logs:
            date_str = log.date.split("T")[0] if "T" in log.date else log.date.split(" ")[0]
            if date_str not in resource_timeline_dict:
                resource_timeline_dict[date_str] = {"water_events": 0, "fert_cost": 0.0}
            
            if log.watered:
                resource_timeline_dict[date_str]["water_events"] += 1
                
            if log.fertilized:
                f_cost = log.fertilizer_amount * s.cost_per_fertilizer
                fert_cost += f_cost
                resource_timeline_dict[date_str]["fert_cost"] += f_cost
                
        total_seeds_cost += seed_cost
        total_land_cost += land_cost
        total_fertilizer_cost += fert_cost
        
        investment = seed_cost + land_cost + fert_cost
        
        harvest_yield = s.harvest_yield or 0.0
        market_price = s.market_price or 0.0
        revenue = harvest_yield * market_price
        profit = revenue - investment
        
        summary_investment += investment
        summary_revenue += revenue
        summary_profit += profit
        
        status_label = "(Active)" if s.is_active else "(Harvested)"
        
        performance.append({
            "session_id": s.id,
            "plot_name": f"{s.plot_name} {status_label}",
            "area_cents": s.area_cents,
            "investment": round(investment, 2),
            "revenue": round(revenue, 2),
            "profit": round(profit, 2)
        })
            
    # Sort performance by revenue descending for leaderboard
    performance.sort(key=lambda x: x["revenue"], reverse=True)
    
    # Process timeline into lists sorted by date
    sorted_dates = sorted(list(resource_timeline_dict.keys()))
    timeline_dates = []
    cumulative_water = []
    cumulative_fert = []
    
    current_water = 0
    current_fert = 0.0
    for d in sorted_dates:
        current_water += resource_timeline_dict[d]["water_events"]
        current_fert += resource_timeline_dict[d]["fert_cost"]
        timeline_dates.append(d)
        cumulative_water.append(current_water)
        cumulative_fert.append(round(current_fert, 2))
            
    return {
        "summary": {
            "investment": round(summary_investment, 2),
            "revenue": round(summary_revenue, 2),
            "profit": round(summary_profit, 2),
            "active_area": round(active_area_cents, 2)
        },
        "cost_breakdown": {
            "labels": ["Seeds", "Land", "Fertilizer"],
            "data": [round(total_seeds_cost, 2), round(total_land_cost, 2), round(total_fertilizer_cost, 2)]
        },
        "session_performance": performance,
        "crop_distribution": {
            "labels": list(crop_distribution.keys()),
            "data": [round(v, 2) for v in crop_distribution.values()]
        },
        "resource_timeline": {
            "dates": timeline_dates,
            "water": cumulative_water,
            "fertilizer": cumulative_fert
        }
    }

@app.get("/api/sessions/{session_id}/weather")
def get_session_weather(session_id: int, db: Session = Depends(get_db)):
    session = db.query(FarmingSession).filter(FarmingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    current = get_current_weather(session.location)
    return current

@app.get("/api/sessions/{session_id}/recommendations")
def get_session_recommendations(session_id: int, db: Session = Depends(get_db)):
    session = db.query(FarmingSession).filter(FarmingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    current_weather = get_current_weather(session.location)
    forecast = get_forecast(session.location, days=1)[0] # get next 24h forecast
    
    # Normally we would get soil moisture from a sensor. Mocking it here.
    import random
    soil_moisture = random.randint(20, 80)
    
    watering = generate_watering_recommendation(
        crop_type=session.crop_type,
        current_weather=current_weather,
        forecast_24h=forecast,
        soil_type=session.soil_type,
        soil_moisture=soil_moisture,
        session_id=session.id
    )
    
    fertilizing = generate_fertilizing_recommendation(
        crop_type=session.crop_type,
        current_weather=current_weather,
        forecast_24h=forecast,
        soil_moisture=soil_moisture
    )
    
    disease_risk = assess_disease_risk(
        humidity=current_weather["humidity"],
        temperature=current_weather["temperature"]
    )
    
    # Log the recommendations
    for rec in [watering, fertilizing]:
        log = RecommendationLog(
            session_id=session.id,
            date=datetime.now().isoformat(),
            action_type=rec["action"],
            recommendation=rec["recommendation"],
            reason=rec["reason"]
        )
        db.add(log)
    db.commit()
    
    return {
        "current_weather": current_weather,
        "soil_moisture": soil_moisture,
        "watering": watering,
        "fertilizing": fertilizing,
        "disease_risk": disease_risk
    }

class NotifyRequest(BaseModel):
    email: str

@app.post("/api/sessions/{session_id}/notify")
def send_session_notification(session_id: int, request: NotifyRequest, db: Session = Depends(get_db)):
    session = db.query(FarmingSession).filter(FarmingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Re-fetch recommendations to format the message
    current_weather = get_current_weather(session.location)
    forecast = get_forecast(session.location, days=1)[0]
    soil_moisture = 50 # Mocking
    
    watering = generate_watering_recommendation(
        session.crop_type, current_weather, forecast, session.soil_type, soil_moisture, session.id
    )
    fertilizing = generate_fertilizing_recommendation(
        session.crop_type, current_weather, forecast, soil_moisture
    )
    disease_risk = assess_disease_risk(
        current_weather["humidity"], current_weather["temperature"]
    )
    
    recommendations = {
        "watering": watering,
        "fertilizing": fertilizing,
        "disease_risk": disease_risk
    }
    
    msg_body = format_alert_message(session.plot_name, session.crop_type, recommendations)
    result = send_email_alert(request.email, msg_body)
    
    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result["message"])
        
    return {"status": "success", "message": "Email alert sent successfully!"}

# ==========================================
# Market Intelligence Endpoints
# ==========================================

import random
from datetime import timedelta

@app.get("/api/market/intelligence")
def get_market_intelligence(x_user_id: Optional[str] = Header(None), db: Session = Depends(get_db)):
    # 1. Get all sessions (active or ended)
    plant_query = db.query(FarmingSession)
    animal_query = db.query(AnimalSession)
    if x_user_id:
        plant_query = plant_query.filter(FarmingSession.user_id == int(x_user_id))
        animal_query = animal_query.filter(AnimalSession.user_id == int(x_user_id))
    all_plants = plant_query.all()
    all_animals = animal_query.all()
    
    commodities = []
    
    # Extract unique crop types
    for p in all_plants:
        if p.crop_type.lower() not in [c['name'].lower() for c in commodities]:
            commodities.append({"name": p.crop_type, "type": "crop", "plot": p.plot_name})
            
    for a in all_animals:
        if a.animal_type.lower() not in [c['name'].lower() for c in commodities]:
            commodities.append({"name": a.animal_type, "type": "animal", "plot": a.session_name})
        
    market_data = []
    news_feed = []
    recommendations = []
    
    for c in commodities:
        name = c["name"].capitalize()
        ctype = c["type"]
        
        # Simulate base price
        base_price = random.randint(15, 60) if ctype == "crop" else random.randint(150, 400)
        unit = "kg" if ctype == "crop" else ("kg live" if name != "Cow" else "liter")
        if name.lower() in ["hen", "duck"]:
            base_price = random.randint(5, 12)
            unit = "egg"
            
        trend_perc = random.randint(-15, 30)
        trend_dir = "↑" if trend_perc > 0 else "↓"
        forecast_price = round(base_price * (1 + (trend_perc/100)), 2)
        
        market_data.append({
            "commodity": name,
            "plot": c["plot"],
            "current_price": base_price,
            "unit": unit,
            "state_avg": round(base_price * 1.15, 2),
            "national_avg": round(base_price * 1.25, 2),
            "trend_perc": trend_perc,
            "trend_dir": trend_dir,
            "forecast_price": forecast_price,
            "mandis": [
                {"location": "Coimbatore", "price": base_price, "distance": "0 km"},
                {"location": "Salem", "price": round(base_price * 1.1, 2), "distance": "85 km"},
                {"location": "Chennai", "price": round(base_price * 1.3, 2), "distance": "190 km"}
            ]
        })
        
        # Simulate News
        if trend_perc > 0:
            reason = random.choice(["Heavy rain reduced supply", "Festival demand surging", "Export demand increased"])
            action = "Sell soon to maximize profits"
        else:
            reason = random.choice(["Overproduction in neighboring states", "Low export demand", "Favorable weather increased harvest"])
            action = "Hold stock if possible until prices recover"
            
        news_feed.append({
            "commodity": name,
            "headline": f"{name.upper()} MARKET UPDATE: Prices { 'rising' if trend_perc > 0 else 'falling' } {abs(trend_perc)}%",
            "source": f"{'Tamil Nadu Agriculture' if ctype == 'crop' else 'Livestock Auction Report'}",
            "reason": reason,
            "forecast": f"Expected to reach ₹{forecast_price}/{unit} soon",
            "recommendation": action
        })
        
        # Smart Recommendation
        rec = {
            "title": f"SMART SELLING RECOMMENDATION ({name})",
            "current_price": f"₹{base_price}/{unit}",
            "forecast_price": f"₹{forecast_price}/{unit}",
            "best_location": "Chennai (Net +15% after transport)",
            "action": f"{'Wait 3-5 days' if trend_perc > 0 else 'Sell immediately before further drops'}"
        }
        recommendations.append(rec)
        
    return {
        "market_data": market_data,
        "news_feed": news_feed,
        "recommendations": recommendations
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
