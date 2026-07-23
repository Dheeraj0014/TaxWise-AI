"""DTOs for the financial-head CRUD surface (§4 Profile & finances).

One In/Out pair per §3 ERD table. Sections are validated against the set the
engine actually understands, so a typo surfaces as a 422 at the API boundary
rather than silently dropping a deduction at computation time.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import (BaseModel, ConfigDict, Field, field_serializer,
                      field_validator)

# Sections the rate tables recognise (see the old-regime `allowed_deductions`
# in config/tax_rules/*.yaml). Kept in sync with the YAML by test_finances.py.
DEDUCTION_SECTIONS = {
    "80C", "80CCD1B", "80CCD2", "80D", "80E", "80EEA", "24b",
    "hra_exempt", "80G", "80TTA", "80TTB",
}
CG_SECTIONS = {"111A", "112A", "112"}


def Money():  # noqa: N802 - reads as a type in field position
    """A non-negative money field. A fresh FieldInfo per use, never shared."""
    return Field(default=Decimal(0), ge=0)


class _Out(BaseModel):
    """Response models read straight off SQLAlchemy rows."""
    model_config = ConfigDict(from_attributes=True)

    @field_serializer("*")
    def _trim_money_scale(self, v, _info):
        """Render stored money at its natural scale.

        Numeric(14, 2) reads back as Decimal('23400.00'), which would ship as
        "23400.00" here while the engine renders the same rupees as "23400".
        One value, two formats, depending on which endpoint you asked. Trim the
        stored scale so every money field in the API looks the same.
        """
        if isinstance(v, Decimal):
            return (v.quantize(Decimal(1))
                    if v == v.to_integral_value() else v.normalize())
        return v


def _section_validator(field: str, allowed: set[str], label: str):
    """Build a reusable 'is this a section the engine knows' validator."""
    def _check(cls, v: str) -> str:
        if v not in allowed:
            raise ValueError(
                f"unknown {label} '{v}'; expected one of {sorted(allowed)}"
            )
        return v
    return field_validator(field)(classmethod(_check))


# --- Income -----------------------------------------------------------------

class IncomeIn(BaseModel):
    type: Literal["salary", "business", "rental", "other"]
    gross_amount: Decimal = Money()
    exemptions: Decimal = Money()
    tds_paid: Decimal = Money()
    assessment_year: int = 2026


class IncomeOut(_Out):
    id: str
    type: str
    gross_amount: Decimal
    exemptions: Decimal
    tds_paid: Decimal
    assessment_year: int


# --- Deductions -------------------------------------------------------------

class DeductionIn(BaseModel):
    section: str
    claimed_amount: Decimal = Money()
    assessment_year: int = 2026

    _known = _section_validator("section", DEDUCTION_SECTIONS, "deduction section")


class DeductionOut(_Out):
    id: str
    section: str
    claimed_amount: Decimal
    assessment_year: int


# --- Investments ------------------------------------------------------------

class InvestmentIn(BaseModel):
    instrument: Literal["PPF", "ELSS", "NPS", "MF", "EQUITY"]
    amount: Decimal = Money()
    section: str = "80C"
    invested_on: date | None = None
    assessment_year: int = 2026

    _known = _section_validator("section", DEDUCTION_SECTIONS, "investment section")


class InvestmentOut(_Out):
    id: str
    instrument: str
    amount: Decimal
    section: str
    invested_on: date | None
    assessment_year: int


# --- Loans ------------------------------------------------------------------

class LoanIn(BaseModel):
    type: Literal["home", "education"]
    principal_paid: Decimal = Money()
    interest_paid: Decimal = Money()
    section: str = "24b"
    assessment_year: int = 2026

    _known = _section_validator("section", DEDUCTION_SECTIONS, "loan section")


class LoanOut(_Out):
    id: str
    type: str
    principal_paid: Decimal
    interest_paid: Decimal
    section: str
    assessment_year: int


# --- Insurance --------------------------------------------------------------

class InsuranceIn(BaseModel):
    type: Literal["life", "health"]
    premium: Decimal = Money()
    section: str = "80D"
    for_senior_citizen: bool = False
    assessment_year: int = 2026

    _known = _section_validator("section", DEDUCTION_SECTIONS, "insurance section")


class InsuranceOut(_Out):
    id: str
    type: str
    premium: Decimal
    section: str
    for_senior_citizen: bool
    assessment_year: int


# --- Capital gains ----------------------------------------------------------

class CapitalGainIn(BaseModel):
    asset_class: Literal["equity", "debt", "property"]
    term: Literal["STCG", "LTCG"]
    amount: Decimal = Money()
    tax_section: str
    assessment_year: int = 2026

    _known = _section_validator("tax_section", CG_SECTIONS, "capital-gains section")


class CapitalGainOut(_Out):
    id: str
    asset_class: str
    term: str
    amount: Decimal
    tax_section: str
    assessment_year: int


# --- Recommendations --------------------------------------------------------

class RecommendationOut(_Out):
    id: str
    computation_id: str
    title: str
    section: str
    estimated_saving: Decimal
    kind: str = "invest"
    amount_modelled: Decimal = Decimal(0)
    net_cost: Decimal = Decimal(0)
    priority: int
    required_documents: list[str] = Field(default_factory=list)
    deadline: str | None
    note: str | None
    status: str


class RecommendationPatch(BaseModel):
    status: Literal["suggested", "accepted", "dismissed"]
