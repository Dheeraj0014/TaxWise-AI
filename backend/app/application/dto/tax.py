"""Pydantic DTOs for the tax API (§4). Validation + serialization boundary."""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field, field_validator

from app.domain.entities.tax import (CapitalGain, Regime, TaxInput, TaxResult)


class CapitalGainIn(BaseModel):
    tax_section: str = Field(..., examples=["112A", "111A", "112"])
    amount: Decimal


class IncomeIn(BaseModel):
    salary_gross: Decimal = Decimal(0)
    rental: Decimal = Decimal(0)
    other: Decimal = Decimal(0)
    business: Decimal = Decimal(0)


class TaxCalcRequest(BaseModel):
    assessment_year: int = 2026
    regime: Regime = Regime.NEW
    income: IncomeIn = IncomeIn()
    deductions: dict[str, Decimal] = Field(default_factory=dict)
    capital_gains: list[CapitalGainIn] = Field(default_factory=list)
    tds_paid: Decimal = Decimal(0)
    advance_tax_paid: Decimal = Decimal(0)

    @field_validator("deductions")
    @classmethod
    def _non_negative(cls, v: dict[str, Decimal]) -> dict[str, Decimal]:
        for k, amt in v.items():
            if amt < 0:
                raise ValueError(f"deduction {k} must be non-negative")
        return v

    def to_domain(self, regime: Regime | None = None) -> TaxInput:
        return TaxInput(
            assessment_year=self.assessment_year,
            regime=regime or self.regime,
            salary_gross=self.income.salary_gross,
            rental_income=self.income.rental,
            other_income=self.income.other,
            business_income=self.income.business,
            deductions=dict(self.deductions),
            capital_gains=[CapitalGain(c.tax_section, c.amount) for c in self.capital_gains],
            tds_paid=self.tds_paid,
            advance_tax_paid=self.advance_tax_paid,
        )


class TaxResultOut(BaseModel):
    assessment_year: int
    regime: str
    rules_version: str
    gross_total_income: Decimal
    total_deductions: Decimal
    taxable_income: Decimal
    tax_before_rebate: Decimal
    rebate_87a: Decimal
    tax_after_rebate: Decimal
    capital_gains_tax: Decimal
    surcharge: Decimal
    marginal_relief: Decimal
    cess: Decimal
    total_tax: Decimal
    tds_paid: Decimal
    refund_or_due: Decimal
    breakdown: dict

    @classmethod
    def from_domain(cls, r: TaxResult) -> "TaxResultOut":
        return cls(
            assessment_year=r.assessment_year,
            regime=r.regime.value,
            rules_version=r.rules_version,
            gross_total_income=r.gross_total_income,
            total_deductions=r.total_deductions,
            taxable_income=r.taxable_income,
            tax_before_rebate=r.tax_before_rebate,
            rebate_87a=r.rebate_87a,
            tax_after_rebate=r.tax_after_rebate,
            capital_gains_tax=r.capital_gains_tax,
            surcharge=r.surcharge,
            marginal_relief=r.marginal_relief,
            cess=r.cess,
            total_tax=r.total_tax,
            tds_paid=r.tds_paid,
            refund_or_due=r.refund_or_due,
            breakdown=r.breakdown,
        )


class TaxCompareOut(BaseModel):
    assessment_year: int
    rules_version: str
    old_regime: TaxResultOut
    new_regime: TaxResultOut
    recommended_regime: str
    savings_vs_alternative: Decimal
    note: str


class SimulateRequest(TaxCalcRequest):
    """A what-if delta applied on top of the base scenario."""
    delta_salary: Decimal = Decimal(0)
    delta_deductions: dict[str, Decimal] = Field(default_factory=dict)
