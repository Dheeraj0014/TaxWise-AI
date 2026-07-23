"""Dashboard aggregations (§4 Reports, dashboard).

Both routes read the user's stored financial heads, assemble them into a domain
TaxInput, and run the same deterministic engine the calculator uses. There is
no second tax implementation here — the dashboard is a *view* of the engine.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.application.dto.tax import TaxResultOut
from app.application.use_cases.assemble_tax_input import (assemble_tax_input,
                                                          income_breakdown)
from app.core.database import get_db
from app.domain.entities.tax import Regime
from app.domain.services.rate_tables import RateTableNotFound, available_years
from app.domain.services.tax_engine import compare_regimes
from app.infrastructure.db.models import Profile, User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _default_ay(db: Session, user: User) -> int:
    p = db.query(Profile).filter(Profile.user_id == user.id).first()
    return p.assessment_year if p else 2026


@router.get("/summary")
def summary(
    assessment_year: int | None = Query(
        default=None, description="Defaults to the AY on the user's profile."
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Aggregated position for one AY: both regimes, plus chart-ready breakdowns."""
    ay = assessment_year or _default_ay(db, user)
    base = assemble_tax_input(db, user.id, ay, Regime.NEW)

    try:
        res = compare_regimes(base)
    except RateTableNotFound as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    recommended = res["recommended_regime"]
    chosen = res[f"{recommended}_regime"]

    return {
        "assessment_year": ay,
        "rules_version": res["rules_version"],
        "has_data": base.salary_gross + base.rental_income
        + base.other_income + base.business_income > 0,
        "income_breakdown": income_breakdown(db, user.id, ay),
        "deduction_breakdown": {k: str(v) for k, v in base.deductions.items()},
        "capital_gains": [
            {"tax_section": g.tax_section, "amount": str(g.amount)}
            for g in base.capital_gains
        ],
        "old_regime": TaxResultOut.from_domain(res["old_regime"]),
        "new_regime": TaxResultOut.from_domain(res["new_regime"]),
        "recommended_regime": recommended,
        "savings_vs_alternative": str(res["savings_vs_alternative"]),
        "headline": {
            "gross_total_income": str(chosen.gross_total_income),
            "total_deductions": str(chosen.total_deductions),
            "taxable_income": str(chosen.taxable_income),
            "total_tax": str(chosen.total_tax),
            "tds_paid": str(chosen.tds_paid),
            "refund_or_due": str(chosen.refund_or_due),
        },
        "disclaimer": (
            "Informational only, not tax or financial advice. "
            "Consult a qualified professional before filing."
        ),
    }


@router.get("/forecast")
def forecast(
    assessment_year: int | None = Query(default=None),
    growth_pct: Decimal = Query(
        default=Decimal(10), ge=-100, le=200,
        description="Assumed income growth applied to every income head.",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Project this AY's position onto the next one.

    A deliberately simple, deterministic projection: grow every income head by
    `growth_pct`, hold deductions flat, and re-run the engine against the next
    AY's rate table if one exists (otherwise this AY's, which the response
    flags via `projected_with_rules_version`). It is a planning aid, not a
    prediction — nothing here models a future Budget's rates.
    """
    ay = assessment_year or _default_ay(db, user)
    years = available_years()
    target_ay = ay + 1 if (ay + 1) in years else ay

    base = assemble_tax_input(db, user.id, ay, Regime.NEW)
    factor = (Decimal(100) + growth_pct) / Decimal(100)

    projected = replace(
        base,
        assessment_year=target_ay,
        salary_gross=base.salary_gross * factor,
        rental_income=base.rental_income * factor,
        other_income=base.other_income * factor,
        business_income=base.business_income * factor,
        # TDS is not projected: next year's withholding is unknown.
        tds_paid=Decimal(0),
    )

    try:
        current = compare_regimes(base)
        future = compare_regimes(projected)
    except RateTableNotFound as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    def _tax(res) -> Decimal:
        return res[f"{res['recommended_regime']}_regime"].total_tax

    current_tax, future_tax = _tax(current), _tax(future)

    return {
        "base_assessment_year": ay,
        "projected_assessment_year": target_ay,
        "projected_with_rules_version": future["rules_version"],
        "same_year_rules_reused": target_ay == ay,
        "growth_pct": str(growth_pct),
        "current_tax": str(current_tax),
        "projected_tax": str(future_tax),
        "delta": str(future_tax - current_tax),
        "recommended_regime": future["recommended_regime"],
        "note": (
            "Projection grows income by the given rate and holds deductions "
            "flat. Future Budget changes are not modelled."
        ),
    }
