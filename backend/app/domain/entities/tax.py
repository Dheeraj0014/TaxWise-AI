"""Framework-free domain entities and value objects for tax computation.

Pure Python dataclasses — no FastAPI, no SQLAlchemy, no LLM. Monetary values
use Decimal to keep tax arithmetic exact and auditable (§5, determinism).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum


class Regime(str, Enum):
    OLD = "old"
    NEW = "new"


@dataclass(frozen=True)
class CapitalGain:
    """A capital-gain line taxed at a special rate, excluded from the 87A base."""
    tax_section: str          # "111A" | "112A" | "112"
    amount: Decimal           # gain amount (already net of cost)


@dataclass(frozen=True)
class TaxInput:
    """Everything the engine needs to compute one regime, for one AY.

    `deductions` maps a section code -> claimed amount (e.g. {"80C": 150000}).
    The engine applies each regime's allow-list and statutory caps; callers do
    not pre-filter, so the same input can be run against both regimes fairly.
    """
    assessment_year: int
    regime: Regime
    salary_gross: Decimal = Decimal(0)
    rental_income: Decimal = Decimal(0)
    other_income: Decimal = Decimal(0)
    business_income: Decimal = Decimal(0)
    deductions: dict[str, Decimal] = field(default_factory=dict)
    capital_gains: list[CapitalGain] = field(default_factory=list)
    tds_paid: Decimal = Decimal(0)
    advance_tax_paid: Decimal = Decimal(0)
    # Age drives senior-citizen-only relief (80TTB replacing 80TTA, higher 80D
    # ceilings). The engine ignores it; the optimizer uses it to avoid offering
    # mutually exclusive sections side by side. None => treat as non-senior.
    age: int | None = None


@dataclass(frozen=True)
class TaxResult:
    """Full, auditable breakdown of a single computation (maps to TAX_COMPUTATION)."""
    assessment_year: int
    regime: Regime
    rules_version: str
    gross_total_income: Decimal
    total_deductions: Decimal
    taxable_income: Decimal                # slab income (excludes special-rate CG)
    tax_before_rebate: Decimal
    rebate_87a: Decimal
    tax_after_rebate: Decimal
    capital_gains_tax: Decimal
    surcharge: Decimal
    marginal_relief: Decimal
    cess: Decimal
    total_tax: Decimal
    tds_paid: Decimal
    refund_or_due: Decimal                 # positive => refund, negative => payable
    breakdown: dict = field(default_factory=dict)
