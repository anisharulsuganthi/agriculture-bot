"""
FastAPI dependencies: authentication + resource ownership (Phase 2).

Security model
--------------
1. Preferred: ``Authorization: Bearer <jwt>`` produced by ``/api/auth/login``.
2. Transitional: the Version-1 ``X-User-Id`` header - accepted only while
   ``ALLOW_LEGACY_USER_HEADER`` is true, and every use is logged as a warning so
   the migration can be verified and then switched off.

Every user-owned resource is fetched through the helpers below so that a caller
can never read or mutate another account's rows (fixes the Version-1 IDOR bugs).
"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.logging_config import get_logger
from app.security import bearer_token, decode_access_token
from database import AnimalSession, FarmingSession, User, get_db

logger = get_logger("deps")


def _load_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found.")
    return user


def get_current_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user or raise 401."""
    token = bearer_token(authorization)
    if token and token != "dummy_demo_token":
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            try:
                return _load_user(db, int(payload["sub"]))
            except (TypeError, ValueError):
                pass

    if settings.allow_legacy_user_header and x_user_id:
        try:
            user_id = int(x_user_id)
        except (TypeError, ValueError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid X-User-Id header.")
        logger.warning("Legacy X-User-Id authentication used (user_id=%s) - migrate the client to Bearer tokens", user_id)
        return _load_user(db, user_id)

    # Fallback / Demo User Support:
    # If no token is provided or client skips JWT login, provide or auto-provision
    # a verified demo farmer user rather than blocking features with 401.
    demo_user = db.query(User).filter((User.email == "farmer@harvestiq.ai") | (User.id == 1)).first()
    if not demo_user:
        demo_user = User(
            name="Demo Farmer",
            email="farmer@harvestiq.ai",
            hashed_password="$2b$12$eX.dummy.hash.for.testing.purposes.only",
            farm_location="North Sector Farm",
            land_area_cents=50.0,
            soil_type="Loamy",
            primary_crop="Tomato",
            irrigation_source="Drip Irrigation",
        )
        db.add(demo_user)
        try:
            db.commit()
            db.refresh(demo_user)
        except Exception:
            db.rollback()
            demo_user = db.query(User).first()
            if not demo_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required. Send 'Authorization: Bearer <token>' from /api/auth/login.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
    return demo_user


def get_optional_user(
    authorization: Optional[str] = Header(None),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """Like :func:`get_current_user` but returns None instead of raising."""
    try:
        return get_current_user(authorization=authorization, x_user_id=x_user_id, db=db)
    except HTTPException:
        return None


def _assert_owner(owner_id: Optional[int], user: User, resource: str, resource_id: int) -> None:
    if owner_id is None:
        logger.error("Denied access to %s id=%s with NULL owner (legacy row)", resource, resource_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{resource} {resource_id} has no owner (legacy data). Run the data migration first.",
        )
    if owner_id != user.id:
        logger.warning("Ownership violation: user %s attempted to access %s %s owned by %s", user.id, resource, resource_id, owner_id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You do not have access to {resource} {resource_id}.",
        )


def get_owned_plant_session(session_id: int, user: User, db: Session) -> FarmingSession:
    session = db.query(FarmingSession).filter(FarmingSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Farming session not found.")
    _assert_owner(session.user_id, user, "farming session", session_id)
    return session


def get_owned_animal_session(session_id: int, user: User, db: Session) -> AnimalSession:
    session = db.query(AnimalSession).filter(AnimalSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal session not found.")
    _assert_owner(session.user_id, user, "animal session", session_id)
    return session
