"""Persisted recommendations (§3 RECOMMENDATION, §4 Optimizer & assistant).

`/optimizer/recommend` stays stateless and unauthenticated — anyone can price a
scenario. These routes are the stateful half: they run the optimizer over the
user's *stored* data, persist the computation that produced the numbers, and
let the user accept or dismiss each strategy.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.application.dto.finances import RecommendationOut, RecommendationPatch
from app.application.use_cases.assemble_tax_input import assemble_tax_input
from app.core.database import get_db
from app.domain.entities.tax import Regime
from app.domain.services.optimizer import recommend
from app.domain.services.rate_tables import RateTableNotFound
from app.domain.services.tax_engine import compute_tax
from app.infrastructure.db.models import (Profile, Recommendation,
                                          TaxComputation, User)

router = APIRouter(tags=["recommendations"])


def _default_ay(db: Session, user: User) -> int:
    p = db.query(Profile).filter(Profile.user_id == user.id).first()
    return p.assessment_year if p else 2026


@router.post("/recommendations/generate", response_model=list[RecommendationOut],
             status_code=201)
def generate(
    assessment_year: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run the optimizer over stored data and persist the results.

    Regenerating replaces any still-`suggested` rows for the AY, so stale
    advice cannot outlive the numbers it was based on. Rows the user already
    accepted or dismissed are left alone — that is their decision history.
    """
    ay = assessment_year or _default_ay(db, user)
    # Optimizer strategies are deduction-driven, so evaluate against the old
    # regime; it also self-detects when switching regimes is the better move.
    base = assemble_tax_input(db, user.id, ay, Regime.OLD)

    try:
        result = compute_tax(base)
        recs = recommend(base)
    except RateTableNotFound as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))

    computation = TaxComputation(
        user_id=user.id,
        assessment_year=result.assessment_year,
        regime=result.regime.value,
        taxable_income=result.taxable_income,
        total_tax=result.total_tax,
        refund_or_due=result.refund_or_due,
        rules_version=result.rules_version,
        breakdown=result.breakdown,
    )
    db.add(computation)
    db.flush()  # need computation.id for the FK below

    (db.query(Recommendation)
       .filter(Recommendation.user_id == user.id,
               Recommendation.status == "suggested",
               Recommendation.computation_id.in_(
                   db.query(TaxComputation.id).filter(
                       TaxComputation.user_id == user.id,
                       TaxComputation.assessment_year == ay,
                   )
               ))
       .delete(synchronize_session=False))

    rows = [
        Recommendation(
            user_id=user.id,
            computation_id=computation.id,
            title=r["title"],
            section=r["section"],
            estimated_saving=Decimal(r["estimated_saving"]),
            kind=r.get("kind", "invest"),
            amount_modelled=Decimal(r.get("amount_modelled", 0)),
            net_cost=Decimal(r.get("net_cost", 0)),
            priority=r["priority"],
            required_documents=r.get("required_documents", []),
            deadline=r.get("deadline"),
            note=r.get("note"),
        )
        for r in recs
    ]
    db.add_all(rows)
    db.commit()
    for row in rows:
        db.refresh(row)
    return rows


@router.get("/recommendations", response_model=list[RecommendationOut])
def list_recommendations(
    status_filter: str | None = Query(
        default=None, alias="status",
        description="suggested | accepted | dismissed",
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Recommendation).filter(Recommendation.user_id == user.id)
    if status_filter:
        q = q.filter(Recommendation.status == status_filter)
    return list(q.order_by(Recommendation.priority).all())


@router.patch("/recommendations/{rec_id}", response_model=RecommendationOut)
def update_recommendation(
    rec_id: str,
    body: RecommendationPatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept or dismiss a strategy (§4 PATCH /recommendations/{id})."""
    row = db.get(Recommendation, rec_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")
    row.status = body.status
    db.commit()
    db.refresh(row)
    return row
