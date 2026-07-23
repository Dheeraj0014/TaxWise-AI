"""Render a saved TaxComputation to a one-page PDF (§4 reports).

Pure formatting: takes the stored row, returns bytes. No DB, no engine — the
numbers were already computed and persisted, so this never re-derives tax math.
"""
from __future__ import annotations

from typing import Any

from fpdf import FPDF

DISCLAIMER = (
    "Informational only, not tax or financial advice. Verify against the "
    "current Finance Act and consult a qualified professional before filing."
)


def _flatten(obj: Any, prefix: str = "") -> list[tuple[str, str]]:
    """breakdown is a small nested dict/list of strings — walk it into flat rows."""
    rows: list[tuple[str, str]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            rows += _flatten(v, f"{prefix}{k} / " if prefix else f"{k} / ")
    elif isinstance(obj, list):
        if not obj:
            rows.append((prefix.rstrip(" /"), "-"))
        for i, v in enumerate(obj):
            rows += _flatten(v, f"{prefix}[{i}] ")
    else:
        rows.append((prefix.rstrip(" /"), str(obj)))
    return rows


def _inr(x: Any) -> str:
    return f"Rs. {float(x):,.2f}"


def computation_pdf(row: Any) -> bytes:
    """`row` is a TaxComputation ORM object (or any object with the same attrs)."""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Tax Computation", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(90)
    pdf.cell(0, 6, f"AY {row.assessment_year}  -  {row.regime} regime  "
                   f"-  rules {row.rules_version}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Computed {row.computed_at:%Y-%m-%d %H:%M}",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0)
    pdf.ln(4)

    headline = [
        ("Taxable income", _inr(row.taxable_income)),
        ("Total tax", _inr(row.total_tax)),
        ("Refund (+) / due (-)", _inr(row.refund_or_due)),
    ]
    pdf.set_font("Helvetica", "", 12)
    for label, val in headline:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(80, 9, label, border="B")
        pdf.set_font("Helvetica", "", 12)
        pdf.cell(0, 9, val, border="B", align="R", new_x="LMARGIN", new_y="NEXT")

    rows = _flatten(row.breakdown or {})
    if rows:
        pdf.ln(6)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "Breakdown", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        for label, val in rows:
            pdf.cell(120, 6, label, border="B")
            pdf.cell(0, 6, val, border="B", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(8)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120)
    pdf.multi_cell(0, 4, DISCLAIMER)

    return bytes(pdf.output())
