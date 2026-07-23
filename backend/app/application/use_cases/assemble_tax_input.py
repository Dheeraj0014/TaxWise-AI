"""Assemble a user's stored financial heads into a domain TaxInput.

This is the application layer doing what §2.2 says it should: orchestrating
repository reads into a pure domain object, then handing off to the engine. It
imports SQLAlchemy models but the domain does not import this — the dependency
still points inward.

Every stored head maps to exactly one engine input:

    IncomeSource   -> salary/rental/business/other (net of `exemptions`), tds_paid
    Deduction      -> deductions[section]
    Investment     -> deductions[section]      (80C / 80CCD1B)
    Loan           -> deductions[section]      (interest for 24b/80E, else principal)
    Insurance      -> deductions[section]      (80C life / 80D health)
    CapitalGainRow -> capital_gains[]          (special rates, outside the 87A base)

Amounts for the same section are summed across heads. That can exceed the
statutory cap — an 80C investment plus an 80C life premium plus an 80C
deduction row — which is correct and intended: the engine applies the caps from
the rate table, so this layer never second-guesses the law.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.domain.entities.tax import CapitalGain, Regime, TaxInput
from app.infrastructure.db.models import (CapitalGainRow, Deduction,
                                          IncomeSource, Insurance, Investment,
                                          Loan, Profile)

# Income `type` -> the TaxInput field it feeds.
_INCOME_FIELD = {
    "salary": "salary_gross",
    "rental": "rental_income",
    "business": "business_income",
    "other": "other_income",
}

# Sections where the deductible amount is the loan's interest, not its principal.
_INTEREST_SECTIONS = {"24b", "80E", "80EEA"}


def _dec(v) -> Decimal:
    """Coerce a stored amount to Decimal at its natural scale.

    Numeric(14, 2) columns come back as Decimal('220000.00'). Left alone, that
    trailing scale leaks into responses as "220000.00" beside the engine's own
    "150000" — same rupees, two formats, in one payload. Normalising here keeps
    stored and computed money rendering identically.
    """
    d = Decimal(str(v or 0))
    return d.quantize(Decimal(1)) if d == d.to_integral_value() else d.normalize()


def assemble_tax_input(
    db: Session,
    user_id: str,
    assessment_year: int,
    regime: Regime = Regime.NEW,
) -> TaxInput:
    """Build the TaxInput for one user and one assessment year."""
    totals = {field: Decimal(0) for field in _INCOME_FIELD.values()}
    deductions: dict[str, Decimal] = {}
    tds = Decimal(0)

    def add_deduction(section: str, amount: Decimal) -> None:
        if amount > 0:
            deductions[section] = deductions.get(section, Decimal(0)) + amount

    def rows(model):
        return (
            db.query(model)
            .filter(model.user_id == user_id, model.assessment_year == assessment_year)
            .all()
        )

    for inc in rows(IncomeSource):
        field = _INCOME_FIELD.get(inc.type)
        if field is None:            # unknown head: count it as other income
            field = "other_income"
        net = _dec(inc.gross_amount) - _dec(inc.exemptions)
        totals[field] += max(Decimal(0), net)
        tds += _dec(inc.tds_paid)

    for ded in rows(Deduction):
        add_deduction(ded.section, _dec(ded.claimed_amount))

    for inv in rows(Investment):
        add_deduction(inv.section, _dec(inv.amount))

    for loan in rows(Loan):
        claimable = (
            _dec(loan.interest_paid)
            if loan.section in _INTEREST_SECTIONS
            else _dec(loan.principal_paid)
        )
        add_deduction(loan.section, claimable)

    for ins in rows(Insurance):
        add_deduction(ins.section, _dec(ins.premium))

    gains = [
        CapitalGain(tax_section=cg.tax_section, amount=_dec(cg.amount))
        for cg in rows(CapitalGainRow)
        if _dec(cg.amount) > 0
    ]

    profile = db.query(Profile).filter(Profile.user_id == user_id).first()

    return TaxInput(
        assessment_year=assessment_year,
        regime=regime,
        salary_gross=totals["salary_gross"],
        rental_income=totals["rental_income"],
        other_income=totals["other_income"],
        business_income=totals["business_income"],
        deductions=deductions,
        capital_gains=gains,
        tds_paid=tds,
        age=profile.age if profile else None,
    )


def income_breakdown(db: Session, user_id: str, assessment_year: int) -> dict:
    """Per-head gross totals for the dashboard's charts (§4 /dashboard/summary)."""
    out: dict[str, float] = {}
    for inc in (
        db.query(IncomeSource)
        .filter(
            IncomeSource.user_id == user_id,
            IncomeSource.assessment_year == assessment_year,
        )
        .all()
    ):
        out[inc.type] = out.get(inc.type, 0.0) + float(_dec(inc.gross_amount))
    return out
