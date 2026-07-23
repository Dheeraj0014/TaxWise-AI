"""Auth + profile DTOs (§4, §8)."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    role: str
    is_active: bool


class ProfileIn(BaseModel):
    full_name: str | None = None
    pan: str | None = None
    age: int | None = Field(default=None, ge=0, le=120)
    residential_status: str = "resident"
    preferred_regime: str | None = None
    assessment_year: int = 2026
    locale: str = "en"


class ProfileOut(BaseModel):
    full_name: str | None
    pan_masked: str | None
    age: int | None
    residential_status: str
    preferred_regime: str | None
    assessment_year: int
    locale: str
