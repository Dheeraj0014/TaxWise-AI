"""Financial-head CRUD (§4 Profile & finances).

The six heads — income, deductions, investments, loans, insurance, capital
gains — are the same resource shape: a user-scoped, AY-filtered collection with
list/create/delete. `_register_crud` builds those three routes from a table +
DTO pair so the handlers exist once rather than eighteen times.

NOTE: this module deliberately omits `from __future__ import annotations`.
FastAPI resolves handler annotations to build the request model, and the
factory's annotations reference closure locals (`dto_in`) that a deferred,
string-based annotation could not resolve.
"""

from typing import Type

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.application.dto.finances import (CapitalGainIn, CapitalGainOut,
                                          DeductionIn, DeductionOut, IncomeIn,
                                          IncomeOut, InsuranceIn, InsuranceOut,
                                          InvestmentIn, InvestmentOut, LoanIn,
                                          LoanOut)
from app.core.database import Base, get_db
from app.infrastructure.db.models import (CapitalGainRow, Deduction,
                                          IncomeSource, Insurance, Investment,
                                          Loan, User)

router = APIRouter(tags=["finances"])


def _register_crud(
    path: str,
    model: Type[Base],
    dto_in: Type[BaseModel],
    dto_out: Type[BaseModel],
    name: str,
) -> None:
    """Register GET/POST/DELETE for one financial head, scoped to the caller."""

    @router.get(path, response_model=list[dto_out], name=f"list_{name}")
    def list_rows(
        assessment_year: int | None = Query(
            default=None, description="Filter to one AY; omit for all years."
        ),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        q = db.query(model).filter(model.user_id == user.id)
        if assessment_year is not None:
            q = q.filter(model.assessment_year == assessment_year)
        return list(q.all())

    @router.post(path, response_model=dto_out, status_code=201, name=f"add_{name}")
    def create_row(
        body: dto_in,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        row = model(user_id=user.id, **body.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @router.delete(
        path + "/{row_id}", status_code=204, name=f"delete_{name}"
    )
    def delete_row(
        row_id: str,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        row = db.get(model, row_id)
        # Same 404 whether the row is missing or someone else's — never confirm
        # the existence of another user's data (§8 per-user scoping).
        if row is None or row.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{name} not found")
        db.delete(row)
        db.commit()


_register_crud("/income", IncomeSource, IncomeIn, IncomeOut, "income")
_register_crud("/deductions", Deduction, DeductionIn, DeductionOut, "deduction")
_register_crud("/investments", Investment, InvestmentIn, InvestmentOut, "investment")
_register_crud("/loans", Loan, LoanIn, LoanOut, "loan")
_register_crud("/insurance", Insurance, InsuranceIn, InsuranceOut, "insurance")
_register_crud(
    "/capital-gains", CapitalGainRow, CapitalGainIn, CapitalGainOut, "capital_gain"
)
