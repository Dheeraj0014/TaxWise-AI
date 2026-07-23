"""Optimizer routes (§4). Ranked, quantified tax-saving strategies."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.application.dto.tax import TaxCalcRequest
from app.domain.services.optimizer import combined_saving, recommend
from app.domain.services.rate_tables import RateTableNotFound

router = APIRouter(prefix="/optimizer", tags=["optimizer"])


@router.post("/recommend")
def recommend_strategies(body: TaxCalcRequest) -> dict:
    base = body.to_domain()
    try:
        recs = recommend(base)
        # Taking every idea at once saves LESS than the sum of the individual
        # figures, because deductions interact through the slabs. Report the
        # achievable number, not the flattering one.
        total = float(combined_saving(base, recs))
    except RateTableNotFound as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    # Donations are excluded from the headline total on purpose: giving ₹1L to
    # save ₹31k leaves you poorer, so folding it into "potential saving" would
    # overstate what the user actually stands to gain. Reported separately.
    donation_relief = sum(float(r["estimated_saving"]) for r in recs
                          if r.get("kind") == "donate")
    return {
        "recommendations": recs,
        "total_potential_saving": total,
        "sum_if_taken_individually": sum(
            float(r["estimated_saving"]) for r in recs if r["kind"] != "donate"
        ),
        "donation_relief": donation_relief,
        "disclaimer": (
            "Informational only, not tax or financial advice. "
            "Consult a qualified professional before filing."
        ),
    }
