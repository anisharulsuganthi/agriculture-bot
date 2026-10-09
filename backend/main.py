"""
Smart Farm - AI-Powered Agricultural Decision Intelligence System for Precision Farming.
FastAPI application (Phase 1 + Phase 2 hardened).

Version 1 -> Version 2 changes (evidence: PROJECT_AUDIT.md)
    * real authentication: bcrypt hashing with transparent upgrade of legacy
      hashes, JWT access tokens and a ``get_current_user`` dependency. The client
      supplied ``X-User-Id`` header is tolerated only while
      ``ALLOW_LEGACY_USER_HEADER=true`` and every use is logged.
    * every user-owned resource is loaded through ownership-checked helpers,
      closing the 9 IDOR routes found in the audit.
    * configuration, secrets, CORS, database path, model path, upload limits and
      rate limits all come from ``app.config`` - nothing is hardcoded.
    * structured logging with secret redaction; unhandled errors are logged and
      returned as a generic message.
    * simulated market data is isolated in ``simulation_service`` and labelled as
      demonstration data in every response.
    * soil moisture is a documented estimate, never ``random.randint``.
    * all Version-1 endpoints keep their paths and response shapes, so the
      existing frontend keeps working.

See API_DOCUMENTATION.md for the endpoint reference.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from advisory_service import get_cure_for_disease
from app.config import settings
from app.crop_vocab import canonical_crops, normalize_crop_type, supported_crops
from app.deps import get_current_user, get_owned_animal_session, get_owned_plant_session
from app.logging_config import get_logger, setup_logging
from app.rate_limit import rate_limit
from app.security import (
    bearer_token,
    create_access_token,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from climate_engine import assess_disease_risk, assess_forecast_risk, calculate_et0
from app.crop_recommendation import evaluate_crop_suitability
from app.yield_prediction import predict_crop_yield
from app.rag_engine import answer_agricultural_query, retrieve_relevant_contexts, load_knowledge_corpus, initialize_rag
from app.assistant import process_assistant_message
from database import (
    AnimalDailyLog,
    AnimalSession,
    DailyLog,
    DiseasePrediction,
    FarmingSession,
    RecommendationLog,
    User,
    FarmerKnowledgeNote,
    get_db,
    init_db,
    to_date_key,
)
from ml_service import load_or_download_model, model_info, parse_model_selection, predict_image
from notification_service import (
    format_alert_message,
    is_configured as email_configured,
    send_email_alert,
    send_otp_email,
)
from recommendation_engine import (
    estimate_soil_moisture,
    generate_fertilizing_recommendation,
    generate_watering_recommendation,
    get_crop_requirement,
    is_crop_supported,
)
from simulation_service import build_market_intelligence
from weather_service import WeatherUnavailable, get_current_weather, get_forecast

logger = setup_logging()
api_logger = get_logger("api")


# ==========================================================================
# Request models (validated)
# ==========================================================================
class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=100)
    password: str = Field(..., min_length=4, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        value = value.strip().lower()
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError("Enter a valid email address.")
        return value


class UserLogin(BaseModel):
    email: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return value.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=100)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=100)
    otp: str = Field(..., min_length=4, max_length=10)
    new_password: str = Field(..., min_length=4, max_length=200)

    @field_validator("email")
    @classmethod
    def _email(cls, value: str) -> str:
        return value.strip().lower()


class SessionCreate(BaseModel):
    crop_type: str = Field(..., min_length=2, max_length=50)
    plot_name: str = Field(..., min_length=1, max_length=100)
    area_cents: float = Field(..., ge=0)
    soil_type: str = Field(..., min_length=2, max_length=50)
    location: str = Field(..., min_length=2, max_length=100)
    seed_qty: float = Field(0.0, ge=0)
    cost_per_seed: float = Field(0.0, ge=0)
    total_land_cost: float = Field(0.0, ge=0)
    fertilizer_qty: float = Field(0.0, ge=0)
    cost_per_fertilizer: float = Field(0.0, ge=0)


class DailyLogCreate(BaseModel):
    watered: bool = False
    water_reason: str = Field("", max_length=200)
    fertilized: bool = False
    fertilizer_amount: float = Field(0.0, ge=0)
    weather_condition: str = Field("", max_length=100)
    notes: str = Field("", max_length=1000)


class HarvestCreate(BaseModel):
    harvest_yield: float = Field(..., ge=0)
    market_price: float = Field(..., ge=0)


class AnimalSessionCreate(BaseModel):
    animal_type: str = Field(..., min_length=2, max_length=50)
    session_name: str = Field(..., min_length=1, max_length=100)
    animal_count: int = Field(..., ge=1)
    cost_per_animal: float = Field(..., ge=0)
    initial_food_qty: float = Field(0.0, ge=0)
    cost_per_food_qty: float = Field(0.0, ge=0)
    medicine_cost: float = Field(0.0, ge=0)
    shelter_cost: float = Field(0.0, ge=0)


class AnimalDailyLogCreate(BaseModel):
    food_given_qty: float = Field(0.0, ge=0)
    food_cost_today: float = Field(0.0, ge=0)
    yield_amount: float = Field(0.0, ge=0)
    yield_selling_price: float = Field(0.0, ge=0)
    medicine_given: bool = False
    medicine_name: Optional[str] = Field(None, max_length=100)
    medicine_cost: float = Field(0.0, ge=0)
    medicine_reason: Optional[str] = Field(None, max_length=200)
    deaths_today: int = Field(0, ge=0)
    notes: Optional[str] = Field(None, max_length=1000)


class AnimalSessionClose(BaseModel):
    animals_sold: int = Field(..., ge=0)
    sell_price_per_animal: float = Field(..., ge=0)


class NotifyRequest(BaseModel):
    """
    Advisory email request.

    ``email`` is optional and **advisory only**: the message is always sent to
    the authenticated account's own address. Version 1 accepted any recipient,
    which turned the endpoint into an open relay (PROJECT_AUDIT.md §10).
    """

    email: Optional[str] = Field(None, max_length=100)


# ==========================================================================
# Application lifecycle
# ==========================================================================
@asynccontextmanager
async def lifespan(_: FastAPI):
    """Startup: database + migrations, then optional model warm-up."""
    report = init_db()
    if report.get("applied"):
        api_logger.info("Database migrations applied: %s", json.dumps(report.get("details", {}), default=str))
    else:
        api_logger.info("Database ready (no pending migrations)")
    api_logger.info("Database file: %s", settings.database_path)

    if settings.ml_warmup_on_startup:
        try:
            load_or_download_model()
            api_logger.info("ML model ready: %s", model_info())
        except Exception as exc:  # noqa: BLE001 - the API must still start
            api_logger.error("ML model warm-up failed (disease endpoint retries lazily): %s", exc)

    try:
        initialize_rag()
        api_logger.info("RAG vector index and knowledge store initialized.")
    except Exception as exc:
        api_logger.warning("RAG vector store initialization deferred: %s", exc)

    api_logger.info("%s v%s started (env=%s)", settings.app_name, settings.app_version, settings.app_env)
    api_logger.info("API bound to %s:%s", settings.api_host, settings.api_port)
    for problem in settings.validate_startup():
        api_logger.warning("Configuration: %s", problem)
    yield
    api_logger.info("Application shutting down")


app = FastAPI(
    title="Smart Farm - Agricultural Decision Intelligence API",
    description=(
        "AI-Powered Agricultural Decision Intelligence System for Precision Farming: "
        "plant disease detection, weather-aware advisory, farm analytics and clearly "
        "labelled demonstration market data."
    ),
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-User-Id"],
)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    """Record latency, log slow requests and server errors (no secrets)."""
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.1f}"
    if response.status_code >= 500:
        api_logger.error("%s %s -> %s in %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
    elif elapsed_ms > 4000:
        api_logger.warning("Slow request %s %s -> %s in %.1fms", request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Generic response; full detail stays in the redacted log."""
    api_logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error. Check the server logs."})


# ==========================================================================
# System endpoints
# ==========================================================================
@app.get("/api/health", tags=["System"])
def health_check():
    return {"status": "ok", "version": settings.app_version, "environment": settings.app_env}


@app.get("/api/system/info", tags=["System"])
def system_info():
    """Public, secret-free runtime information (useful for the paper's setup section)."""
    return {
        "app_name": settings.app_name,
        "settings": settings.as_public_dict(),
        "ml": model_info(),
        "email_configured": email_configured(),
        "weather_configured": bool(settings.openweather_api_key),
    }


@app.get("/api/crops", tags=["System"])
def list_crops():
    """Canonical crop vocabulary plus the crops with documented requirements."""
    return {
        "supported_crops": supported_crops(),
        "canonical_crops": canonical_crops(),
    }


# ==========================================================================
# Authentication
# ==========================================================================
def _issue_token(user: User) -> str:
    return create_access_token(user.id, user.email, user.name or "")


def _user_payload(user: User) -> Dict[str, Any]:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _otp_digest(user_id: int, otp: str) -> str:
    """
    OTP digest.

    The code is never stored: only a keyed digest is persisted, so a leaked
    database row cannot be replayed against ``/api/auth/reset-password``. The
    key is the deployment's JWT secret, so rotating it invalidates every
    outstanding OTP.
    """
    message = f"smartfarm-otp:{user_id}:{otp}".encode("utf-8")
    return hmac.new(settings.jwt_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def _generate_otp(length: int) -> str:
    """Cryptographically strong numeric OTP (``random`` is not a CSPRNG)."""
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


@app.post("/api/auth/register", tags=["Authentication"], dependencies=[Depends(rate_limit("register", settings.register_rate_limit))])
def register_endpoint(user_data: UserRegister, db: Session = Depends(get_db)):
    password_error = validate_password_strength(user_data.password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user = User(
        name=user_data.name.strip(),
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    api_logger.info("New account registered: id=%s", user.id)
    return {
        "status": "success",
        "message": "Account created successfully!",
        "user": _user_payload(user),
        "access_token": _issue_token(user),
        "token_type": "bearer",
        "expires_in_minutes": settings.access_token_expire_minutes,
    }


@app.post("/api/auth/login", tags=["Authentication"], dependencies=[Depends(rate_limit("login", settings.login_rate_limit))])
def login_endpoint(user_data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        api_logger.warning("Failed login attempt for %s", user_data.email)
        raise HTTPException(status_code=400, detail="Invalid email or password.")

    if needs_rehash(user.hashed_password):
        user.hashed_password = hash_password(user_data.password)
        db.commit()
        api_logger.info("Upgraded legacy password hash to bcrypt for user id=%s", user.id)

    return {
        "status": "success",
        "message": "Logged in successfully!",
        "user": _user_payload(user),
        "access_token": _issue_token(user),
        "token_type": "bearer",
        "expires_in_minutes": settings.access_token_expire_minutes,
    }


@app.get("/api/auth/me", tags=["Authentication"])
def me_endpoint(
    current_user: User = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
):
    """Identity of the caller, with the credential scheme that was actually used."""
    if bearer_token(authorization):
        auth_method = "bearer-token"
    elif x_user_id and settings.allow_legacy_user_header:
        auth_method = "legacy-x-user-id"
    else:
        auth_method = "unknown"
    return {"status": "success", "user": _user_payload(current_user), "auth_method": auth_method}


@app.post("/api/auth/forgot-password", tags=["Authentication"], dependencies=[Depends(rate_limit("forgot", settings.forgot_rate_limit))])
def forgot_password_endpoint(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Always answers with the same generic message.

    A delivery failure is logged but never surfaced as a 500: returning an error
    only for real accounts re-enabled account enumeration in misconfigured
    deployments (PROJECT_AUDIT.md S9 follow-up).
    """
    generic = {"status": "success", "message": "If that email is registered, a reset code has been sent."}
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        api_logger.info("Forgot-password requested for an unknown email (response kept generic)")
        return generic

    otp = _generate_otp(settings.otp_length)
    user.otp = _otp_digest(user.id, otp)
    user.otp_expiry = datetime.utcnow() + timedelta(minutes=settings.otp_expiry_minutes)
    user.otp_attempts = 0
    db.commit()

    result = send_otp_email(user.email, otp)
    if result.get("status") == "error":
        api_logger.error("OTP delivery failed for user id=%s: %s", user.id, result.get("message"))
    return generic


@app.post("/api/auth/reset-password", tags=["Authentication"], dependencies=[Depends(rate_limit("reset", settings.reset_rate_limit))])
def reset_password_endpoint(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not user.otp:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code.")

    if (user.otp_attempts or 0) >= settings.otp_max_attempts:
        raise HTTPException(status_code=429, detail="Too many incorrect attempts. Request a new reset code.")

    if not user.otp_expiry or datetime.utcnow() > user.otp_expiry:
        raise HTTPException(status_code=400, detail="Reset code has expired. Request a new one.")

    if user.otp != _otp_digest(user.id, request.otp):
        user.otp_attempts = (user.otp_attempts or 0) + 1
        db.commit()
        api_logger.warning("Incorrect OTP for user id=%s (attempt %s)", user.id, user.otp_attempts)
        raise HTTPException(status_code=400, detail="Incorrect reset code.")

    password_error = validate_password_strength(request.new_password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    user.hashed_password = hash_password(request.new_password)
    user.otp = None
    user.otp_expiry = None
    user.otp_attempts = 0
    db.commit()
    api_logger.info("Password reset completed for user id=%s", user.id)
    return {"status": "success", "message": "Password updated successfully! You can now log in."}


@app.get("/api/auth/user-stats", tags=["Authentication"])
def get_user_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    uid = current_user.id
    return {
        "plant_count": db.query(FarmingSession).filter(FarmingSession.user_id == uid).count(),
        "active_plant": db.query(FarmingSession).filter(FarmingSession.user_id == uid, FarmingSession.is_active == True).count(),  # noqa: E712
        "animal_count": db.query(AnimalSession).filter(AnimalSession.user_id == uid).count(),
        "active_animal": db.query(AnimalSession).filter(AnimalSession.user_id == uid, AnimalSession.is_active == True).count(),  # noqa: E712
        "predictions": db.query(DiseasePrediction).filter(DiseasePrediction.user_id == uid).count(),
    }


# ==========================================================================
# Plant disease detection
# ==========================================================================
MAX_UPLOAD_NOTE = f"Maximum upload size is {settings.max_upload_bytes // (1024 * 1024)} MB."


def _validate_upload(image: UploadFile) -> None:
    """Content-type + extension validation (Phase 2 hardening)."""
    if image is None or not image.filename:
        raise HTTPException(status_code=400, detail="No image file was provided.")

    content_type = (image.content_type or "").lower()
    if content_type not in settings.allowed_image_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{content_type or 'unknown'}'. Allowed: {', '.join(settings.allowed_image_types)}.",
        )

    filename = image.filename.lower()
    if not any(filename.endswith(ext) for ext in settings.allowed_image_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension. Allowed: {', '.join(settings.allowed_image_extensions)}.",
        )


async def _read_upload_limited(image: UploadFile) -> bytes:
    """Read the upload with a hard size cap so a huge file cannot exhaust memory."""
    chunks: List[bytes] = []
    total = 0
    while True:
        chunk = await image.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail=f"Image is too large. {MAX_UPLOAD_NOTE}")
        chunks.append(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    return b"".join(chunks)


@app.post("/api/predict/disease", tags=["Disease detection"])
async def predict_disease_endpoint(
    image: UploadFile = File(...),
    crop_type: str = Form("Unknown"),
    symptoms: str = Form(""),
    location: str = Form("Tamil Nadu, India"),
    models: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Classify a leaf image and return top-k predictions plus advisory steps.

    Low-confidence results are flagged (``status: "uncertain"``) instead of being
    reported as a disease - Version 1 returned a confident label for any image.

    ``models`` selects the ensemble: a comma-separated subset of the registry
    ids (``mobilenetv2``, ``resnet50``, ``swin``). One model runs standalone;
    two or more hard-vote on the winning class. Empty uses ML_DEFAULT_MODELS.
    """
    _validate_upload(image)
    try:
        model_ids = parse_model_selection(models)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    image_bytes = await _read_upload_limited(image)

    try:
        # Inference is CPU/GPU bound: run it in the worker thread pool so the
        # event loop keeps serving other requests during a prediction.
        result = await run_in_threadpool(predict_image, image_bytes, None, model_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - model/runtime failure
        api_logger.exception("Prediction failed for user %s: %s", current_user.id, exc)
        raise HTTPException(status_code=500, detail="Disease prediction failed. Please retry.")

    canonical_crop = normalize_crop_type(crop_type)
    disease_name = result["top_label"]
    is_healthy = bool(result["is_healthy"])
    severity = "None" if is_healthy else result["severity"]
    confidence_score = float(result["top_score"])

    cure = get_cure_for_disease(disease_name, canonical_crop, location)

    record = DiseasePrediction(
        user_id=current_user.id,
        crop_type=canonical_crop,
        symptoms=(symptoms or "")[:2000],
        location=location,
        disease_name=disease_name,
        confidence_score=confidence_score,
        is_healthy=is_healthy,
        severity=severity,
        cure_data=json.dumps(cure),
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    api_logger.info(
        "Prediction id=%s user=%s label=%s score=%.2f status=%s mode=%s models=%s in %sms (%s)",
        record.id, current_user.id, disease_name, confidence_score,
        result["status"], result["mode"], ",".join(m["id"] for m in result["models"]),
        result["inference_ms"], result["device"],
    )

    return {
        "prediction": {
            "id": record.id,
            "disease_name": disease_name,
            "confidence_score": confidence_score,
            "is_healthy": is_healthy,
            "severity": severity,
            "status": result["status"],
            "confident": result["confident"],
            "requires_expert_review": result["requires_expert_review"],
            "confidence_floor": result["confidence_floor"],
            "detections": result["detections"],
            "annotated_image_base64": result["annotated_image_base64"],
            "annotation_type": result["annotation_type"],
            "inference_ms": result["inference_ms"],
            "device": result["device"],
            "mode": result["mode"],
            "models": result["models"],
            "votes": result["votes"],
            "agreement": result["agreement"],
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "crop_type": canonical_crop,
        },
        "cure": cure,
        "cure_source": cure[0]["source"] if cure else "unknown",
        "notice": (
            "Low confidence: the model is not certain about this image. Capture a clearer close-up "
            "leaf photo in daylight, or consult an expert."
            if not result["confident"]
            else None
        ),
    }


@app.get("/api/predictions", tags=["Disease detection"])
def list_predictions(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detection history for the authenticated user (now timestamped)."""
    limit = max(1, min(int(limit or 20), 200))
    rows = (
        db.query(DiseasePrediction)
        .filter(DiseasePrediction.user_id == current_user.id)
        .order_by(DiseasePrediction.created_at.desc(), DiseasePrediction.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "count": len(rows),
        "items": [
            {
                "id": row.id,
                "crop_type": row.crop_type,
                "disease_name": row.disease_name,
                "confidence_score": row.confidence_score,
                "is_healthy": row.is_healthy,
                "severity": row.severity,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "location": row.location,
            }
            for row in rows
        ],
    }


@app.get("/api/predictions/stats", tags=["Disease detection"])
def prediction_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Aggregate detection statistics (healthy vs diseased, per crop)."""
    rows = db.query(DiseasePrediction).filter(DiseasePrediction.user_id == current_user.id).all()
    by_crop: Dict[str, int] = {}
    for row in rows:
        by_crop[row.crop_type or "Unknown"] = by_crop.get(row.crop_type or "Unknown", 0) + 1
    healthy = sum(1 for row in rows if row.is_healthy)
    return {
        "total": len(rows),
        "healthy": healthy,
        "diseased": len(rows) - healthy,
        "by_crop": by_crop,
        "avg_confidence": round(sum(float(row.confidence_score or 0) for row in rows) / len(rows), 2) if rows else 0.0,
    }


# ==========================================================================
# Plant (crop) farm management
# ==========================================================================
@app.get("/api/sessions", tags=["Plant farm"])
def list_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """List the authenticated user's farming sessions."""
    return (
        db.query(FarmingSession)
        .filter(FarmingSession.user_id == current_user.id)
        .order_by(FarmingSession.id.desc())
        .all()
    )


@app.post("/api/sessions", tags=["Plant farm"])
def create_session(
    session_data: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    canonical_crop = normalize_crop_type(session_data.crop_type)
    record = FarmingSession(
        user_id=current_user.id,
        crop_type=canonical_crop,
        plot_name=session_data.plot_name.strip(),
        area_cents=session_data.area_cents,
        soil_type=session_data.soil_type.strip(),
        location=session_data.location.strip(),
        seed_qty=session_data.seed_qty,
        cost_per_seed=session_data.cost_per_seed,
        total_land_cost=session_data.total_land_cost,
        fertilizer_qty=session_data.fertilizer_qty,
        cost_per_fertilizer=session_data.cost_per_fertilizer,
        is_active=True,
        created_at=datetime.now().isoformat(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    api_logger.info("Farming session %s created for user %s (%s)", record.id, current_user.id, canonical_crop)
    return {
        "status": "success",
        "session_id": record.id,
        "message": "Farming session created",
        "crop_supported": is_crop_supported(canonical_crop),
        "crop_type": canonical_crop,
    }


@app.post("/api/sessions/{session_id}/daily_logs", tags=["Plant farm"])
def create_daily_log(
    session_id: int,
    log_data: DailyLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a daily farm log. Ownership is enforced (Version 1 had no check)."""
    get_owned_plant_session(session_id, current_user, db)
    record = DailyLog(
        session_id=session_id,
        date=datetime.now().isoformat(),
        watered=log_data.watered,
        water_reason=log_data.water_reason[:200],
        fertilized=log_data.fertilized,
        fertilizer_amount=log_data.fertilizer_amount,
        weather_condition=log_data.weather_condition[:100],
        notes=log_data.notes[:1000],
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "success", "log_id": record.id, "message": "Daily log added"}


@app.get("/api/sessions/{session_id}/daily_logs", tags=["Plant farm"])
def get_daily_logs(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_plant_session(session_id, current_user, db)
    return db.query(DailyLog).filter(DailyLog.session_id == session_id).order_by(DailyLog.id.desc()).all()


@app.post("/api/sessions/{session_id}/harvest", tags=["Plant farm"])
def harvest_session(
    session_id: int,
    harvest_data: HarvestCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Close a plant session with the realised yield and market price."""
    session = get_owned_plant_session(session_id, current_user, db)
    if not session.is_active:
        # Version 1 silently overwrote a recorded harvest on every repeat call.
        raise HTTPException(
            status_code=409,
            detail="This session was already harvested. Create a new session to record another harvest.",
        )
    session.is_active = False
    session.harvest_yield = harvest_data.harvest_yield
    session.market_price = harvest_data.market_price
    session.ended_at = datetime.utcnow()
    db.commit()
    revenue = round(harvest_data.harvest_yield * harvest_data.market_price, 2)
    api_logger.info("Session %s harvested (yield=%s, revenue=%s)", session_id, harvest_data.harvest_yield, revenue)
    return {"status": "success", "message": "Session harvested successfully", "revenue": revenue}


@app.get("/api/sessions/{session_id}/weather", tags=["Plant farm"])
def get_session_weather(
    session_id: int,
    days: int = 5,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Current weather + forecast for the session location.

    ``current`` carries ``data_source``/``simulated`` flags so the UI and the
    paper can distinguish live values from labelled fallbacks.
    """
    session = get_owned_plant_session(session_id, current_user, db)
    try:
        current = get_current_weather(session.location)
        forecast = get_forecast(session.location, days=max(1, min(days, 5)))
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    return {
        "location": session.location,
        "current": current,
        "forecast": forecast,
        "disease_risk_forecast": assess_forecast_risk(forecast),
    }


@app.get("/api/sessions/{session_id}/recommendations", tags=["Advisory"])
def get_session_recommendations(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Watering + fertilizing + disease-risk advisory for a session.

    Soil moisture is an explicit **estimate** (weather + soil type + irrigation
    history) because no sensor is deployed; Version 1 used ``random.randint``,
    which made two identical requests disagree.
    """
    session = get_owned_plant_session(session_id, current_user, db)

    try:
        current_weather = get_current_weather(session.location)
        forecast_days = get_forecast(session.location, days=5)
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    forecast_24h = forecast_days[0] if forecast_days else {"rain_probability": None, "simulated": True}
    today_key = datetime.now().date().isoformat()
    logs = db.query(DailyLog).filter(DailyLog.session_id == session_id).all()
    watered_today = any(to_date_key(log.date) == today_key and log.watered for log in logs)
    last_dates = sorted((to_date_key(log.date) for log in logs), reverse=True)
    if last_dates:
        try:
            days_since_watering = max(1, (datetime.now().date() - datetime.fromisoformat(last_dates[0]).date()).days + 1)
        except ValueError:
            days_since_watering = 1
    else:
        days_since_watering = 1

    moisture = estimate_soil_moisture(
        soil_type=session.soil_type,
        watered_today=watered_today,
        rain_probability=forecast_24h.get("rain_probability"),
        temperature=current_weather.get("temperature") or 25,
        days_since_watering=days_since_watering,
    )
    soil_moisture = moisture["value"]

    watering = generate_watering_recommendation(
        crop_type=session.crop_type,
        current_weather=current_weather,
        forecast_24h=forecast_24h,
        soil_type=session.soil_type,
        soil_moisture=soil_moisture,
        session_id=session.id,
        soil_moisture_source=moisture["source"],
    )
    fertilizing = generate_fertilizing_recommendation(
        crop_type=session.crop_type,
        current_weather=current_weather,
        forecast_24h=forecast_24h,
        soil_moisture=soil_moisture,
        soil_moisture_source=moisture["source"],
    )
    disease_risk = assess_disease_risk(
        humidity=current_weather.get("humidity") or 60,
        temperature=current_weather.get("temperature") or 25,
    )

    # Personalization adjustment from Farmer Profile (Phase 7)
    farmer_profile_info = {
        "irrigation_source": current_user.irrigation_source or "Borewell / Drip",
        "farm_location": current_user.farm_location or session.location,
        "soil_type": current_user.soil_type or session.soil_type,
        "land_area_cents": current_user.land_area_cents or session.area_cents
    }

    for recommendation in (watering, fertilizing):
        db.add(
            RecommendationLog(
                session_id=session.id,
                date=datetime.now().isoformat(),
                action_type=recommendation["action"],
                recommendation=recommendation["recommendation"],
                reason=recommendation["reason"],
            )
        )
    db.commit()

    return {
        "session_id": session.id,
        "crop_type": session.crop_type,
        "crop_supported": is_crop_supported(session.crop_type),
        "crop_requirement": get_crop_requirement(session.crop_type),
        "location": session.location,
        "farmer_profile": farmer_profile_info,
        "current_weather": current_weather,
        "forecast_24h": forecast_24h,
        "soil_moisture": soil_moisture,
        "soil_moisture_detail": moisture,
        "watering": watering,
        "fertilizing": fertilizing,
        "disease_risk": disease_risk,
        "disease_risk_forecast": assess_forecast_risk(forecast_days),
        "et0_estimate": calculate_et0(
            temp_celsius=current_weather.get("temperature") or 25,
            solar_rad_mj=None,
            temp_min=forecast_24h.get("temp_min"),
        ),
        "inputs_summary": {
            "soil_moisture_source": moisture["source"],
            "weather_source": current_weather.get("data_source"),
            "method": "rule_based_decision_engine",
        },
    }


@app.post("/api/sessions/{session_id}/notify", tags=["Advisory"], dependencies=[Depends(rate_limit("notify", settings.notify_rate_limit))])
def send_session_notification(
    session_id: int,
    request: NotifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Email the current advisory for a session to the caller's own account.

    Fixes three Version-1 defects: the handler returned ``null`` (no ``return``),
    the recipient was attacker controlled, and the soil-moisture estimate was
    forced to "not watered today", so the email could contradict the dashboard.
    """
    session = get_owned_plant_session(session_id, current_user, db)
    recipient = (current_user.email or "").strip().lower()
    if not recipient:
        raise HTTPException(status_code=400, detail="This account has no email address to send the advisory to.")

    if not email_configured():
        raise HTTPException(status_code=503, detail="Email delivery is not configured on this server.")

    try:
        current_weather = get_current_weather(session.location)
        forecast_days = get_forecast(session.location, days=1)
    except WeatherUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    forecast_24h = forecast_days[0] if forecast_days else {"rain_probability": None}

    # Same inputs as /recommendations so both surfaces agree.
    today_key = datetime.now().date().isoformat()
    logs = db.query(DailyLog).filter(DailyLog.session_id == session_id).all()
    watered_today = any(to_date_key(log.date) == today_key and log.watered for log in logs)
    last_dates = sorted((to_date_key(log.date) for log in logs), reverse=True)
    days_since_watering = 1
    if last_dates:
        try:
            days_since_watering = max(1, (datetime.now().date() - datetime.fromisoformat(last_dates[0]).date()).days + 1)
        except ValueError:
            days_since_watering = 1

    moisture = estimate_soil_moisture(
        soil_type=session.soil_type,
        watered_today=watered_today,
        rain_probability=forecast_24h.get("rain_probability"),
        temperature=current_weather.get("temperature") or 25,
        days_since_watering=days_since_watering,
    )
    recommendations = {
        "watering": generate_watering_recommendation(
            session.crop_type, current_weather, forecast_24h, session.soil_type, moisture["value"], session.id,
            soil_moisture_source=moisture["source"],
        ),
        "fertilizing": generate_fertilizing_recommendation(
            session.crop_type, current_weather, forecast_24h, moisture["value"],
            soil_moisture_source=moisture["source"],
        ),
        "disease_risk": assess_disease_risk(
            current_weather.get("humidity") or 60, current_weather.get("temperature") or 25
        ),
    }

    message = format_alert_message(session.plot_name, session.crop_type, recommendations)
    result = send_email_alert(recipient, message)
    if result.get("status") == "error":
        api_logger.error("Advisory email failed for user %s: %s", current_user.id, result.get("message"))
        raise HTTPException(status_code=502, detail=result.get("message", "Email delivery failed."))

    api_logger.info("Advisory emailed to the account address for session %s (user %s)", session_id, current_user.id)
    return {
        "status": "success",
        "message": "Advisory sent to your account email address.",
        "recipient": recipient,
        "advice": recommendations,
    }

# ==========================================================================
# Plant farm dashboards
# ==========================================================================
@app.get("/api/dashboard/summary", tags=["Dashboards"])
def get_dashboard_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Investment / yield / revenue / profit KPIs for the user's crop sessions."""
    sessions = db.query(FarmingSession).filter(FarmingSession.user_id == current_user.id).all()

    total_investment = 0.0
    total_yield = 0.0
    total_revenue = 0.0

    for session in sessions:
        investment = (
            (session.seed_qty or 0) * (session.cost_per_seed or 0)
            + (session.total_land_cost or 0)
            + (session.fertilizer_qty or 0) * (session.cost_per_fertilizer or 0)
        )
        for log in db.query(DailyLog).filter(DailyLog.session_id == session.id).all():
            if log.fertilized:
                investment += (log.fertilizer_amount or 0) * (session.cost_per_fertilizer or 0)

        total_investment += investment
        if not session.is_active and session.harvest_yield and session.market_price:
            total_yield += session.harvest_yield
            total_revenue += session.harvest_yield * session.market_price

    net_profit = total_revenue - total_investment
    profit_margin = (net_profit / total_investment * 100) if total_investment > 0 else 0.0

    return {
        "total_investment": round(total_investment, 2),
        "total_yield": round(total_yield, 2),
        "total_revenue": round(total_revenue, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin_percent": round(profit_margin, 2),
        "active_sessions": len([s for s in sessions if s.is_active]),
        "completed_sessions": len([s for s in sessions if not s.is_active]),
    }


@app.get("/api/dashboard/analytics", tags=["Dashboards"])
def get_dashboard_analytics(
    session_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chart-ready aggregates: cost split, per-session performance, crop mix, timeline."""
    query = db.query(FarmingSession).filter(FarmingSession.user_id == current_user.id)
    if session_id:
        query = query.filter(FarmingSession.id == session_id)
    sessions = query.all()

    total_seeds_cost = 0.0
    total_land_cost = 0.0
    total_fertilizer_cost = 0.0
    summary_investment = 0.0
    summary_revenue = 0.0
    summary_profit = 0.0
    active_area_cents = 0.0
    crop_distribution: Dict[str, float] = {}
    timeline: Dict[str, Dict[str, float]] = {}
    performance: List[Dict[str, Any]] = []

    for session in sessions:
        seed_cost = (session.seed_qty or 0) * (session.cost_per_seed or 0)
        land_cost = session.total_land_cost or 0
        fert_cost = (session.fertilizer_qty or 0) * (session.cost_per_fertilizer or 0)

        crop = session.crop_type or "Unknown"
        crop_distribution[crop] = crop_distribution.get(crop, 0.0) + (session.area_cents or 0)
        if session.is_active:
            active_area_cents += session.area_cents or 0

        for log in db.query(DailyLog).filter(DailyLog.session_id == session.id).all():
            date_key = to_date_key(log.date)
            if not date_key:
                continue
            bucket = timeline.setdefault(date_key, {"water_events": 0.0, "fert_cost": 0.0})
            if log.watered:
                bucket["water_events"] += 1
            if log.fertilized:
                # Daily-log fertiliser is part of the investment, exactly as in
                # /dashboard/summary (Version 1 counted it in one place only, so
                # the two dashboards disagreed).
                cost = (log.fertilizer_amount or 0) * (session.cost_per_fertilizer or 0)
                fert_cost += cost
                bucket["fert_cost"] += cost

        total_seeds_cost += seed_cost
        total_land_cost += land_cost
        total_fertilizer_cost += fert_cost

        investment = seed_cost + land_cost + fert_cost
        harvest_yield = session.harvest_yield or 0.0
        market_price = session.market_price or 0.0
        revenue = harvest_yield * market_price
        summary_investment += investment
        summary_revenue += revenue
        summary_profit += revenue - investment

        performance.append(
            {
                "session_id": session.id,
                "plot_name": f"{session.plot_name} {'(Active)' if session.is_active else '(Harvested)'}",
                "crop_type": crop,
                "area_cents": session.area_cents,
                "investment": round(investment, 2),
                "revenue": round(revenue, 2),
                "profit": round(revenue - investment, 2),
            }
        )

    performance.sort(key=lambda item: item["revenue"], reverse=True)

    dates = sorted(timeline.keys())
    cumulative_water: List[int] = []
    cumulative_fert: List[float] = []
    running_water = 0.0
    running_fert = 0.0
    for date_key in dates:
        running_water += timeline[date_key]["water_events"]
        running_fert += timeline[date_key]["fert_cost"]
        cumulative_water.append(int(running_water))
        cumulative_fert.append(round(running_fert, 2))

    return {
        "summary": {
            "investment": round(summary_investment, 2),
            "revenue": round(summary_revenue, 2),
            "profit": round(summary_profit, 2),
            "active_area": round(active_area_cents, 2),
        },
        "cost_breakdown": {
            "labels": ["Seeds", "Land", "Fertilizer"],
            "data": [round(total_seeds_cost, 2), round(total_land_cost, 2), round(total_fertilizer_cost, 2)],
        },
        "session_performance": performance,
        "crop_distribution": {
            "labels": list(crop_distribution.keys()),
            "data": [round(value, 2) for value in crop_distribution.values()],
        },
        "resource_timeline": {
            "dates": dates,
            "water": cumulative_water,
            "fertilizer": cumulative_fert,
        },
    }


# ==========================================================================
# Animal (livestock) farm management - preserved from Version 1
# ==========================================================================
@app.post("/api/animals", tags=["Animal farm"])
def create_animal_session(
    session_data: AnimalSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = AnimalSession(
        user_id=current_user.id,
        animal_type=session_data.animal_type.strip().title(),
        session_name=session_data.session_name.strip(),
        animal_count=session_data.animal_count,
        cost_per_animal=session_data.cost_per_animal,
        initial_food_qty=session_data.initial_food_qty,
        cost_per_food_qty=session_data.cost_per_food_qty,
        medicine_cost=session_data.medicine_cost,
        shelter_cost=session_data.shelter_cost,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "success", "session_id": record.id}


@app.get("/api/animals", tags=["Animal farm"])
def get_animal_sessions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(AnimalSession)
        .filter(AnimalSession.user_id == current_user.id)
        .order_by(AnimalSession.id.desc())
        .all()
    )


@app.post("/api/animals/{session_id}/daily_logs", tags=["Animal farm"])
def add_animal_daily_log(
    session_id: int,
    log_data: AnimalDailyLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_animal_session(session_id, current_user, db)
    record = AnimalDailyLog(session_id=session_id, date=datetime.utcnow(), **log_data.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"status": "success", "log_id": record.id}


@app.get("/api/animals/{session_id}/daily_logs", tags=["Animal farm"])
def get_animal_daily_logs(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    get_owned_animal_session(session_id, current_user, db)
    return (
        db.query(AnimalDailyLog)
        .filter(AnimalDailyLog.session_id == session_id)
        .order_by(AnimalDailyLog.date.desc())
        .all()
    )


@app.post("/api/animals/{session_id}/close", tags=["Animal farm"])
def close_animal_session(
    session_id: int,
    close_data: AnimalSessionClose,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = get_owned_animal_session(session_id, current_user, db)
    if not session.is_active:
        raise HTTPException(
            status_code=409,
            detail="This animal session is already closed. Create a new session to record another close-out.",
        )
    session.is_active = False
    session.animals_sold = close_data.animals_sold
    session.sell_price_per_animal = close_data.sell_price_per_animal
    session.total_sale_revenue = close_data.animals_sold * close_data.sell_price_per_animal
    session.ended_at = datetime.utcnow()
    db.commit()
    return {"status": "success", "total_sale_revenue": round(session.total_sale_revenue, 2)}


@app.get("/api/animals/dashboard/summary", tags=["Dashboards"])
def get_animal_dashboard_summary(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = db.query(AnimalSession).filter(AnimalSession.user_id == current_user.id).all()

    total_investment = 0.0
    total_yield = 0.0
    total_revenue = 0.0

    for session in sessions:
        investment = (
            session.animal_count * session.cost_per_animal
            + session.initial_food_qty * session.cost_per_food_qty
            + session.medicine_cost
            + session.shelter_cost
        )
        revenue = 0.0
        for log in db.query(AnimalDailyLog).filter(AnimalDailyLog.session_id == session.id).all():
            investment += (log.food_cost_today or 0) + (log.medicine_cost or 0)
            total_yield += log.yield_amount or 0
            revenue += (log.yield_amount or 0) * (log.yield_selling_price or 0)

        if not session.is_active and session.total_sale_revenue:
            revenue += session.total_sale_revenue

        total_investment += investment
        total_revenue += revenue

    net_profit = total_revenue - total_investment
    profit_margin = (net_profit / total_investment * 100) if total_investment > 0 else 0.0

    return {
        "total_investment": round(total_investment, 2),
        "total_yield": round(total_yield, 2),
        "total_revenue": round(total_revenue, 2),
        "net_profit": round(net_profit, 2),
        "profit_margin_percent": round(profit_margin, 2),
        "active_sessions": len([s for s in sessions if s.is_active]),
        "completed_sessions": len([s for s in sessions if not s.is_active]),
    }












@app.get("/api/animals/dashboard/analytics", tags=["Dashboards"])
def get_animal_analytics(
    session_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Chart-ready livestock aggregates (cost split, distribution, yield timeline)."""
    query = db.query(AnimalSession).filter(AnimalSession.user_id == current_user.id)
    if session_id:
        query = query.filter(AnimalSession.id == session_id)
    sessions = query.all()

    total_animal_cost = 0.0
    total_food_cost = 0.0
    total_med_cost = 0.0
    total_shelter_cost = 0.0
    animal_distribution: Dict[str, int] = {}
    timeline: Dict[str, Dict[str, float]] = {}
    performance: List[Dict[str, Any]] = []

    for session in sessions:
        initial_animal = session.animal_count * session.cost_per_animal
        initial_food = session.initial_food_qty * session.cost_per_food_qty
        animal_type = session.animal_type or "Unknown"
        animal_distribution[animal_type] = animal_distribution.get(animal_type, 0) + session.animal_count

        total_animal_cost += initial_animal
        total_food_cost += initial_food
        total_med_cost += session.medicine_cost or 0
        total_shelter_cost += session.shelter_cost or 0

        logs = db.query(AnimalDailyLog).filter(AnimalDailyLog.session_id == session.id).all()
        for log in logs:
            date_key = to_date_key(log.date)
            if date_key:
                bucket = timeline.setdefault(date_key, {"yield": 0.0, "food_cost": 0.0})
                bucket["yield"] += log.yield_amount or 0
                bucket["food_cost"] += log.food_cost_today or 0

        daily_food = sum(log.food_cost_today or 0 for log in logs)
        daily_med = sum(log.medicine_cost or 0 for log in logs)
        total_food_cost += daily_food
        total_med_cost += daily_med

        investment = (
            initial_animal + initial_food + (session.medicine_cost or 0) + (session.shelter_cost or 0) + daily_food + daily_med
        )
        daily_revenue = sum((log.yield_amount or 0) * (log.yield_selling_price or 0) for log in logs)
        total_yield = sum(log.yield_amount or 0 for log in logs)
        revenue = daily_revenue + (session.total_sale_revenue or 0.0)

        performance.append(
            {
                "session_id": session.id,
                "plot_name": f"{session.session_name} {'(Active)' if session.is_active else '(Ended)'}",
                "animal_type": animal_type,
                "animal_count": session.animal_count,
                "total_yield": round(total_yield, 2),
                "investment": round(investment, 2),
                "revenue": round(revenue, 2),
                "profit": round(revenue - investment, 2),
            }
        )

    performance.sort(key=lambda item: item["total_yield"], reverse=True)

    dates = sorted(timeline.keys())
    cumulative_yield: List[float] = []
    cumulative_food: List[float] = []
    running_yield = 0.0
    running_food = 0.0
    for date_key in dates:
        running_yield += timeline[date_key]["yield"]
        running_food += timeline[date_key]["food_cost"]
        cumulative_yield.append(round(running_yield, 2))
        cumulative_food.append(round(running_food, 2))

    return {
        "cost_breakdown": {
            "labels": ["Animals", "Food", "Medicine", "Shelter"],
            "data": [
                round(total_animal_cost, 2),
                round(total_food_cost, 2),
                round(total_med_cost, 2),
                round(total_shelter_cost, 2),
            ],
        },
        "session_performance": performance,
        "animal_distribution": {
            "labels": list(animal_distribution.keys()),
            "data": list(animal_distribution.values()),
        },
        "resource_timeline": {
            "dates": dates,
            "yield": cumulative_yield,
            "food_cost": cumulative_food,
        },
    }


# ==========================================================================
# Market intelligence (demonstration data - clearly labelled)
# ==========================================================================
@app.get("/api/market/intelligence", tags=["Market"])
def get_market_intelligence(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Commodity overview for the user's crops and livestock.

    Values are SIMULATED demonstration values (deterministic per commodity/day)
    because no live mandi feed is integrated. Every record carries
    ``data_source: "simulated"`` and a disclaimer - Version 1 presented the same
    randomly generated numbers as market data.
    """
    plants = db.query(FarmingSession).filter(FarmingSession.user_id == current_user.id).all()
    animals = db.query(AnimalSession).filter(AnimalSession.user_id == current_user.id).all()

    commodities: List[Dict[str, str]] = []
    seen = set()
    for plant in plants:
        name = (plant.crop_type or "Unknown").lower()
        if name not in seen:
            seen.add(name)
            commodities.append({"name": plant.crop_type or "Unknown", "type": "crop", "plot": plant.plot_name or ""})
    for animal in animals:
        name = (animal.animal_type or "Unknown").lower()
        if name not in seen:
            seen.add(name)
            commodities.append(
                {"name": animal.animal_type or "Unknown", "type": "animal", "plot": animal.session_name or ""}
            )

    payload = build_market_intelligence(commodities)
    payload["commodities_tracked"] = len(commodities)
    return payload


# =====================================================================
# Phase 3: Crop Recommendation & Yield Prediction Routes
# =====================================================================

class CropRecommendationRequest(BaseModel):
    n: float = Field(..., description="Nitrogen content in soil (kg/ha)", ge=0, le=300)
    p: float = Field(..., description="Phosphorus content in soil (kg/ha)", ge=0, le=300)
    k: float = Field(..., description="Potassium content in soil (kg/ha)", ge=0, le=300)
    temperature: float = Field(..., description="Temperature (°C)", ge=-10, le=60)
    humidity: float = Field(..., description="Relative humidity (%)", ge=0, le=100)
    ph: float = Field(..., description="Soil pH value", ge=0, le=14)
    rainfall: float = Field(..., description="Rainfall (mm)", ge=0, le=1000)
    top_k: int = Field(default=3, ge=1, le=10)


@app.post("/api/ml/crop-recommendation", tags=["AI / ML"], summary="Recommend suitable crops from soil & climate")
def get_crop_recommendation(
    req: CropRecommendationRequest,
    current_user: User = Depends(get_current_user)
):
    recommendations = evaluate_crop_suitability(
        n=req.n,
        p=req.p,
        k=req.k,
        temperature=req.temperature,
        humidity=req.humidity,
        ph=req.ph,
        rainfall=req.rainfall,
        top_k=req.top_k
    )
    return {
        "status": "success",
        "inputs": req.dict(),
        "recommendations": recommendations,
        "methodology": "Agronomic multi-variable compatibility scoring based on optimal nutrient and climatic ranges"
    }


class YieldPredictionRequest(BaseModel):
    crop: str = Field(..., description="Crop name")
    area_cents: float = Field(..., description="Plot land area in cents", gt=0)
    soil_type: str = Field(default="Loamy", description="Soil classification")
    fertilizer_applied_kg: float = Field(default=50.0, description="Fertilizer applied in kg", ge=0)
    rainfall_mm: float = Field(default=100.0, description="Seasonal rainfall in mm", ge=0)
    temperature_c: float = Field(default=25.0, description="Mean temperature in °C")
    irrigation_available: bool = Field(default=True, description="Availability of assured irrigation")


@app.post("/api/ml/yield-prediction", tags=["AI / ML"], summary="Predict expected crop harvest yield")
def get_yield_prediction(
    req: YieldPredictionRequest,
    current_user: User = Depends(get_current_user)
):
    prediction = predict_crop_yield(
        crop=req.crop,
        area_cents=req.area_cents,
        soil_type=req.soil_type,
        fertilizer_applied_kg=req.fertilizer_applied_kg,
        rainfall_mm=req.rainfall_mm,
        temperature_c=req.temperature_c,
        irrigation_available=req.irrigation_available
    )
    return {
        "status": "success",
        "prediction": prediction
    }


# =====================================================================
# Phase 4 & 5: Government Knowledge Base & RAG Retrieval Routes
# =====================================================================

@app.get("/api/knowledge/schemes", tags=["Knowledge Base & Schemes"], summary="List verified government schemes")
def get_government_schemes(current_user: User = Depends(get_current_user)):
    corpus = load_knowledge_corpus()
    return {
        "status": "success",
        "total_schemes": len(corpus),
        "schemes": corpus
    }


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500, description="Query regarding schemes, loans, or subsidies")


@app.post("/api/knowledge/query", tags=["Knowledge Base & Schemes"], summary="Grounded RAG agricultural answering with citations")
def query_knowledge_base(
    req: RAGQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    farmer_ctx = {
        "user_id": current_user.id,
        "name": current_user.name,
        "location": current_user.farm_location,
        "soil_type": current_user.soil_type,
        "land_area_cents": current_user.land_area_cents,
        "irrigation_source": current_user.irrigation_source,
        "primary_crop": current_user.primary_crop,
        "livestock_owned": current_user.livestock_owned
    }
    result = answer_agricultural_query(req.query, farmer_context=farmer_ctx, db=db, user_id=current_user.id)
    return result


class FarmerNoteCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=200, description="Title of farm note or record")
    category: Optional[str] = Field("farm_record", max_length=50, description="Category: soil_test, advisory, crop_record, general")
    content: str = Field(..., min_length=5, max_length=5000, description="Detailed record or guideline text")


@app.get("/api/knowledge/farmer-notes", tags=["Knowledge Base & Schemes"], summary="List personal farm knowledge notes")
def get_farmer_knowledge_notes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    notes = db.query(FarmerKnowledgeNote).filter(FarmerKnowledgeNote.user_id == current_user.id).order_by(FarmerKnowledgeNote.created_at.desc()).all()
    return {
        "status": "success",
        "total_notes": len(notes),
        "notes": [
            {
                "id": n.id,
                "title": n.title,
                "category": n.category,
                "content": n.content,
                "created_at": n.created_at.isoformat() if n.created_at else ""
            }
            for n in notes
        ]
    }


@app.post("/api/knowledge/farmer-notes", tags=["Knowledge Base & Schemes"], summary="Add personal farm knowledge note or record")
def create_farmer_knowledge_note(
    payload: FarmerNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = FarmerKnowledgeNote(
        user_id=current_user.id,
        title=payload.title,
        category=payload.category or "farm_record",
        content=payload.content
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return {
        "status": "success",
        "message": "Farmer knowledge note saved successfully",
        "note": {
            "id": note.id,
            "title": note.title,
            "category": note.category,
            "content": note.content,
            "created_at": note.created_at.isoformat() if note.created_at else ""
        }
    }


@app.delete("/api/knowledge/farmer-notes/{note_id}", tags=["Knowledge Base & Schemes"], summary="Delete personal farm knowledge note")
def delete_farmer_knowledge_note(
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    note = db.query(FarmerKnowledgeNote).filter(FarmerKnowledgeNote.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Farm note not found")
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not own this note")
    db.delete(note)
    db.commit()
    return {
        "status": "success",
        "message": f"Farm note {note_id} deleted successfully"
    }


# =====================================================================
# Phase 6: Conversational Agricultural Assistant Route
# =====================================================================

class AssistantMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="User prompt or question")


@app.post("/api/assistant/chat", tags=["Conversational Assistant"], summary="Interact with Unified Agricultural AI Assistant")
def chat_with_assistant(
    req: AssistantMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    farmer_ctx = {
        "user_id": current_user.id,
        "name": current_user.name,
        "location": current_user.farm_location,
        "soil_type": current_user.soil_type,
        "land_area_cents": current_user.land_area_cents,
        "irrigation_source": current_user.irrigation_source,
        "primary_crop": current_user.primary_crop,
        "livestock_owned": current_user.livestock_owned
    }
    reply = process_assistant_message(req.message, farmer_context=farmer_ctx, db=db)
    return {
        "status": "success",
        "query": req.message,
        "result": reply
    }


# =====================================================================
# Phase 7: Farmer Profile & Personalization Routes
# =====================================================================

class FarmerProfileUpdate(BaseModel):
    farm_location: Optional[str] = Field(None, max_length=100)
    land_area_cents: Optional[float] = Field(None, gt=0)
    soil_type: Optional[str] = Field(None, max_length=50)
    irrigation_source: Optional[str] = Field(None, max_length=50)
    primary_crop: Optional[str] = Field(None, max_length=50)
    livestock_owned: Optional[str] = Field(None, max_length=100)


@app.get("/api/farmer/profile", tags=["Farmer Profile"], summary="Get current farmer profile and farm configuration")
def get_farmer_profile(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "farm_location": current_user.farm_location or "Tamil Nadu, India",
        "land_area_cents": current_user.land_area_cents or 50.0,
        "soil_type": current_user.soil_type or "Loamy",
        "irrigation_source": current_user.irrigation_source or "Borewell / Drip",
        "primary_crop": current_user.primary_crop or "Tomato",
        "livestock_owned": current_user.livestock_owned or "Dairy Cattle"
    }


@app.put("/api/farmer/profile", tags=["Farmer Profile"], summary="Update farmer farm characteristics")
def update_farmer_profile(
    profile_data: FarmerProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if profile_data.farm_location is not None:
        current_user.farm_location = profile_data.farm_location
    if profile_data.land_area_cents is not None:
        current_user.land_area_cents = profile_data.land_area_cents
    if profile_data.soil_type is not None:
        current_user.soil_type = profile_data.soil_type
    if profile_data.irrigation_source is not None:
        current_user.irrigation_source = profile_data.irrigation_source
    if profile_data.primary_crop is not None:
        current_user.primary_crop = profile_data.primary_crop
    if profile_data.livestock_owned is not None:
        current_user.livestock_owned = profile_data.livestock_owned

    db.commit()
    db.refresh(current_user)
    return {
        "status": "success",
        "message": "Farmer profile updated successfully",
        "profile": {
            "farm_location": current_user.farm_location,
            "land_area_cents": current_user.land_area_cents,
            "soil_type": current_user.soil_type,
            "irrigation_source": current_user.irrigation_source,
            "primary_crop": current_user.primary_crop,
            "livestock_owned": current_user.livestock_owned
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=not settings.is_production,
    )

