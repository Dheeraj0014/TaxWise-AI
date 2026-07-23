"""SQLAlchemy models for the §3 ERD.

USER, PROFILE, INCOME_SOURCE, INVESTMENT, LOAN, INSURANCE, CAPITAL_GAIN,
DEDUCTION, TAX_COMPUTATION, RECOMMENDATION. Financial rows carry
`assessment_year` as a first-class dimension. PAN is stored encrypted-at-rest in
the blueprint; here we mark the column and defer envelope encryption to the
infrastructure/storage adapter.

Still modelled in the blueprint but not yet here: DOCUMENT / EXTRACTED_FIELD
(Phase 3) and CHAT_SESSION / CHAT_MESSAGE / CITATION (Phase 4). ROLE is
denormalised onto `User.role` — see the note on that column.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (JSON, Boolean, Date, DateTime, ForeignKey, Integer,
                        Numeric, String)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # The blueprint models ROLE as its own table with a JSONB permission set. We
    # denormalise to a name here because the guard in api/v1/deps.py is
    # role-based (`require_role`), not permission-based; promoting this to a
    # ROLE table is what §8's `require_permission("admin:reindex")` would need.
    role: Mapped[str] = mapped_column(String(20), default="user")  # user|advisor|admin
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    profile: Mapped["Profile"] = relationship(back_populates="user", uselist=False)
    incomes: Mapped[list["IncomeSource"]] = relationship(back_populates="user")
    deductions: Mapped[list["Deduction"]] = relationship(back_populates="user")
    computations: Mapped[list["TaxComputation"]] = relationship(back_populates="user")
    investments: Mapped[list["Investment"]] = relationship(back_populates="user")
    loans: Mapped[list["Loan"]] = relationship(back_populates="user")
    insurances: Mapped[list["Insurance"]] = relationship(back_populates="user")
    capital_gains: Mapped[list["CapitalGainRow"]] = relationship(back_populates="user")
    recommendations: Mapped[list["Recommendation"]] = relationship(back_populates="user")


class Profile(Base):
    __tablename__ = "profiles"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pan_encrypted: Mapped[str | None] = mapped_column(String(255), nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    residential_status: Mapped[str] = mapped_column(String(30), default="resident")
    preferred_regime: Mapped[str | None] = mapped_column(String(10), nullable=True)
    assessment_year: Mapped[int] = mapped_column(Integer, default=2026)
    locale: Mapped[str] = mapped_column(String(5), default="en")

    user: Mapped["User"] = relationship(back_populates="profile")


class IncomeSource(Base):
    __tablename__ = "income_sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))  # salary|business|rental|other
    gross_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    exemptions: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    # Not in the §3 ERD, which carries TDS only inside `detail`. Promoted to a
    # column because /dashboard/summary needs to sum it to derive refund/due,
    # and a JSON probe per row would neither index nor validate.
    tds_paid: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    assessment_year: Mapped[int] = mapped_column(Integer, default=2026, index=True)

    user: Mapped["User"] = relationship(back_populates="incomes")


class Investment(Base):
    """§3 INVESTMENT — PPF/ELSS/NPS etc., each mapped to the section it claims."""
    __tablename__ = "investments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    instrument: Mapped[str] = mapped_column(String(20))  # PPF|ELSS|NPS|MF|EQUITY
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    section: Mapped[str] = mapped_column(String(20))     # 80C|80CCD1B
    invested_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    assessment_year: Mapped[int] = mapped_column(Integer, default=2026, index=True)

    user: Mapped["User"] = relationship(back_populates="investments")


class Loan(Base):
    """§3 LOAN — principal and interest split, since they claim different sections."""
    __tablename__ = "loans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))        # home|education
    principal_paid: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    interest_paid: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    section: Mapped[str] = mapped_column(String(20))     # 80C|24b|80E|80EEA
    assessment_year: Mapped[int] = mapped_column(Integer, default=2026, index=True)

    user: Mapped["User"] = relationship(back_populates="loans")


class Insurance(Base):
    """§3 INSURANCE — life premiums claim 80C, health premiums 80D."""
    __tablename__ = "insurances"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))        # life|health
    premium: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    section: Mapped[str] = mapped_column(String(20))     # 80C|80D
    for_senior_citizen: Mapped[bool] = mapped_column(Boolean, default=False)
    assessment_year: Mapped[int] = mapped_column(Integer, default=2026, index=True)

    user: Mapped["User"] = relationship(back_populates="insurances")


class CapitalGainRow(Base):
    """§3 CAPITAL_GAIN. Named ...Row to avoid clashing with the domain entity.

    Taxed at special rates and excluded from the §87A rebate base (§5).
    """
    __tablename__ = "capital_gains"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    asset_class: Mapped[str] = mapped_column(String(20))  # equity|debt|property
    term: Mapped[str] = mapped_column(String(10))         # STCG|LTCG
    amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    tax_section: Mapped[str] = mapped_column(String(10))  # 111A|112|112A
    assessment_year: Mapped[int] = mapped_column(Integer, default=2026, index=True)

    user: Mapped["User"] = relationship(back_populates="capital_gains")


class Deduction(Base):
    __tablename__ = "deductions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    section: Mapped[str] = mapped_column(String(20))
    claimed_amount: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    assessment_year: Mapped[int] = mapped_column(Integer, default=2026, index=True)

    user: Mapped["User"] = relationship(back_populates="deductions")


class TaxComputation(Base):
    __tablename__ = "tax_computations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    assessment_year: Mapped[int] = mapped_column(Integer, index=True)
    regime: Mapped[str] = mapped_column(String(10))
    taxable_income: Mapped[float] = mapped_column(Numeric(14, 2))
    total_tax: Mapped[float] = mapped_column(Numeric(14, 2))
    refund_or_due: Mapped[float] = mapped_column(Numeric(14, 2))
    rules_version: Mapped[str] = mapped_column(String(30))
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    user: Mapped["User"] = relationship(back_populates="computations")
    recommendations: Mapped[list["Recommendation"]] = relationship(
        back_populates="computation"
    )


class Recommendation(Base):
    """§3 RECOMMENDATION — a strategy produced by one computation.

    `estimated_saving` is quantified by re-running the engine (see
    domain/services/optimizer.py), never estimated by an LLM.
    """
    __tablename__ = "recommendations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    computation_id: Mapped[str] = mapped_column(
        ForeignKey("tax_computations.id"), index=True
    )
    title: Mapped[str] = mapped_column(String(255))
    section: Mapped[str] = mapped_column(String(20))
    estimated_saving: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    # expense | structural | invest | donate — what the idea does to your money.
    # `net_cost` is the cash you never get back, so a donation can never be
    # presented as a net gain the way an ELSS investment legitimately is.
    kind: Mapped[str] = mapped_column(String(20), default="invest")
    amount_modelled: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    net_cost: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    required_documents: Mapped[list] = mapped_column(JSON, default=list)
    deadline: Mapped[str | None] = mapped_column(String(30), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="suggested")

    user: Mapped["User"] = relationship(back_populates="recommendations")
    computation: Mapped["TaxComputation"] = relationship(
        back_populates="recommendations"
    )
