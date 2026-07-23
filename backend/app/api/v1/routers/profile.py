"""Profile + financial-head routes (§4 Profile & finances)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.application.dto.auth import ProfileIn, ProfileOut
from app.core.database import get_db
from app.infrastructure.db.models import Profile, User

router = APIRouter(tags=["profile"])


def _mask_pan(pan: str | None) -> str | None:
    if not pan or len(pan) < 4:
        return pan
    return "XXXXX" + pan[-4:]


@router.get("/profile", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user),
                db: Session = Depends(get_db)) -> ProfileOut:
    p = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not p:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile not found")
    return ProfileOut(
        full_name=p.full_name, pan_masked=_mask_pan(p.pan_encrypted), age=p.age,
        residential_status=p.residential_status, preferred_regime=p.preferred_regime,
        assessment_year=p.assessment_year, locale=p.locale,
    )


@router.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileIn, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)) -> ProfileOut:
    p = db.query(Profile).filter(Profile.user_id == user.id).first()
    if not p:
        p = Profile(user_id=user.id)
        db.add(p)
    p.full_name = body.full_name
    # NOTE: envelope-encrypt PAN before storing in a real deployment (§12).
    p.pan_encrypted = body.pan
    p.age = body.age
    p.residential_status = body.residential_status
    p.preferred_regime = body.preferred_regime
    p.assessment_year = body.assessment_year
    p.locale = body.locale
    db.commit()
    db.refresh(p)
    return ProfileOut(
        full_name=p.full_name, pan_masked=_mask_pan(p.pan_encrypted), age=p.age,
        residential_status=p.residential_status, preferred_regime=p.preferred_regime,
        assessment_year=p.assessment_year, locale=p.locale,
    )

# Income and deduction CRUD moved to routers/finances.py, which serves all six
# financial heads from one factory and takes JSON bodies rather than the query
# params these handlers used (§4.2: "JSON bodies validated by Pydantic").
