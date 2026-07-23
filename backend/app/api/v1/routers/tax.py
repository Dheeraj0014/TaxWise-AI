"""Tax calculation routes (§4 Tax calculation, §4.3). Public — no PII required.

The engine is deterministic; authenticated callers additionally get their
computation persisted to history.
"""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.application.dto.tax import (SimulateRequest, TaxCalcRequest,
                                     TaxCompareOut, TaxResultOut)
from app.core.database import get_db
from app.domain.entities.tax import Regime
from app.domain.services.rate_tables import (RateTableNotFound, available_years)
from app.domain.services.tax_engine import compare_regimes, compute_tax
from app.infrastructure.db.models import TaxComputation, User

router = APIRouter(prefix="/tax", tags=["tax"])


def _run(inp):
    try:
        return compute_tax(inp)
    except RateTableNotFound as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


@router.get("/assessment-years")
def assessment_years() -> dict:
    return {"available": available_years()}


@router.post("/calculate", response_model=TaxResultOut)
def calculate(body: TaxCalcRequest) -> TaxResultOut:
    return TaxResultOut.from_domain(_run(body.to_domain()))


@router.post("/compare", response_model=TaxCompareOut)
def compare(body: TaxCalcRequest) -> TaxCompareOut:
    try:
        res = compare_regimes(body.to_domain())
    except RateTableNotFound as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    old = res["old_regime"]
    new = res["new_regime"]
    if res["recommended_regime"] == "new":
        note = "New regime wins: lower slabs outweigh the lost Ch VI-A deductions."
    else:
        note = "Old regime wins: your deductions (80C/80D/HRA/24b) beat the lower new slabs."
    return TaxCompareOut(
        assessment_year=res["assessment_year"],
        rules_version=res["rules_version"],
        old_regime=TaxResultOut.from_domain(old),
        new_regime=TaxResultOut.from_domain(new),
        recommended_regime=res["recommended_regime"],
        savings_vs_alternative=res["savings_vs_alternative"],
        note=note,
    )


@router.post("/capital-gains", response_model=TaxResultOut)
def capital_gains(body: TaxCalcRequest) -> TaxResultOut:
    if not body.capital_gains:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Provide at least one capital_gains line")
    return TaxResultOut.from_domain(_run(body.to_domain()))


@router.post("/simulate", response_model=TaxCompareOut)
def simulate(body: SimulateRequest) -> TaxCompareOut:
    """What-if: apply salary/deduction deltas then compare regimes."""
    base = body.to_domain()
    merged = dict(base.deductions)
    for k, v in body.delta_deductions.items():
        merged[k] = merged.get(k, Decimal(0)) + v
    projected = replace(
        base,
        salary_gross=base.salary_gross + body.delta_salary,
        deductions=merged,
    )
    try:
        res = compare_regimes(projected)
    except RateTableNotFound as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    note = f"Simulated: salary {body.delta_salary:+}, deduction deltas {dict(body.delta_deductions)}."
    return TaxCompareOut(
        assessment_year=res["assessment_year"],
        rules_version=res["rules_version"],
        old_regime=TaxResultOut.from_domain(res["old_regime"]),
        new_regime=TaxResultOut.from_domain(res["new_regime"]),
        recommended_regime=res["recommended_regime"],
        savings_vs_alternative=res["savings_vs_alternative"],
        note=note,
    )


@router.post("/save", response_model=dict)
def save_computation(body: TaxCalcRequest, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)) -> dict:
    """Persist a computation to the authenticated user's history (§3 TAX_COMPUTATION)."""
    r = _run(body.to_domain())
    row = TaxComputation(
        user_id=user.id, assessment_year=r.assessment_year, regime=r.regime.value,
        taxable_income=r.taxable_income, total_tax=r.total_tax,
        refund_or_due=r.refund_or_due, rules_version=r.rules_version,
        breakdown=r.breakdown,
    )
    db.add(row)
    db.commit()
    return {"id": row.id, "saved": True}


@router.get("/computations")
def history(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list:
    rows = (db.query(TaxComputation)
            .filter(TaxComputation.user_id == user.id)
            .order_by(TaxComputation.computed_at.desc()).all())
    return [{
        "id": r.id, "assessment_year": r.assessment_year, "regime": r.regime,
        "taxable_income": float(r.taxable_income), "total_tax": float(r.total_tax),
        "refund_or_due": float(r.refund_or_due), "rules_version": r.rules_version,
        "computed_at": r.computed_at.isoformat(),
    } for r in rows]
