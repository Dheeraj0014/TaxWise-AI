"""Deterministic Indian income-tax engine (§5).

Pure function of (TaxInput, rate table). No I/O, no LLM, no randomness — the same
input always yields the same TaxResult. All rates come from versioned YAML so a
Budget change is a data change, not a code change.

Order of operations mirrors the §5 flowchart:
  normalize -> deductions -> slab tax -> §87A rebate -> surcharge (+ marginal
  relief) -> cess -> add special-rate capital-gains tax -> subtract TDS.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.entities.tax import Regime, TaxInput, TaxResult
from app.domain.services.rate_tables import d, load_rate_table

TEN = Decimal(10)
ONE = Decimal(1)


def _round_income(x: Decimal) -> Decimal:
    """Total income is rounded down to the nearest ₹10 (Rule 288A style)."""
    if x <= 0:
        return Decimal(0)
    return (x // TEN) * TEN


def _round_rupee(x: Decimal) -> Decimal:
    return x.quantize(ONE, rounding=ROUND_HALF_UP)


def _slab_tax(taxable: Decimal, slabs: list) -> Decimal:
    """Progressive slab tax. Each slab is [lower, upper|null, rate_pct]."""
    tax = Decimal(0)
    for lower, upper, rate in slabs:
        lo, up = d(lower), (None if upper is None else d(upper))
        if taxable <= lo:
            break
        band_top = taxable if up is None else min(taxable, up)
        tax += (band_top - lo) * d(rate) / Decimal(100)
    return tax


def _apply_deductions(inp: TaxInput, regime_cfg: dict) -> tuple[Decimal, dict]:
    """Apply the regime's allow-list + statutory caps to claimed deductions."""
    allowed = set(regime_cfg.get("allowed_deductions", []))
    caps = {k: d(v) for k, v in regime_cfg.get("deduction_caps", {}).items()}
    detail: dict[str, str] = {}
    total = Decimal(0)

    # Standard deduction — only against salary income, always in both regimes.
    std = min(d(regime_cfg["standard_deduction"]), inp.salary_gross)
    if "std" in allowed and std > 0:
        total += std
        detail["standard_deduction"] = str(std)

    for section, claimed in inp.deductions.items():
        claimed = d(claimed)
        if section not in allowed:
            detail[section] = f"0 (disallowed in {inp.regime.value} regime)"
            continue
        eligible = min(claimed, caps[section]) if section in caps else claimed
        total += eligible
        detail[section] = str(eligible) + (
            f" (capped from {claimed})" if eligible < claimed else ""
        )
    return total, detail


def _capital_gains_tax(inp: TaxInput, cg_cfg: dict) -> tuple[Decimal, list]:
    tax = Decimal(0)
    lines = []
    for cg in inp.capital_gains:
        rules = cg_cfg.get(cg.tax_section)
        if rules is None:
            raise ValueError(f"Unknown capital-gain section {cg.tax_section!r}")
        taxable = max(Decimal(0), d(cg.amount) - d(rules.get("exemption", 0)))
        line_tax = taxable * d(rules["rate_pct"]) / Decimal(100)
        tax += line_tax
        lines.append({
            "section": cg.tax_section,
            "gain": str(d(cg.amount)),
            "exemption": str(d(rules.get("exemption", 0))),
            "taxable": str(taxable),
            "rate_pct": str(d(rules["rate_pct"])),
            "tax": str(_round_rupee(line_tax)),
        })
    return tax, lines


def _surcharge(base_tax: Decimal, cg_tax: Decimal, surcharge_income: Decimal,
               cg_total: Decimal, slabs: list, bands: list) -> tuple[Decimal, Decimal]:
    """Surcharge on (base_tax + cg_tax) by income band, with marginal relief.

    Returns (surcharge, marginal_relief).
    """
    rate = Decimal(0)
    threshold = Decimal(0)
    prev_rate = Decimal(0)
    for lower, upper, band_rate in bands:
        lo = d(lower)
        up = None if upper is None else d(upper)
        if surcharge_income > lo and (up is None or surcharge_income <= up):
            rate = d(band_rate)
            threshold = lo
            break
        if surcharge_income > lo:
            prev_rate = d(band_rate)  # track the last fully-crossed band
    if rate == 0:
        return Decimal(0), Decimal(0)

    pre_surcharge = base_tax + cg_tax
    surcharge = pre_surcharge * rate / Decimal(100)

    # Marginal relief: extra (tax+surcharge) above the threshold must not exceed
    # the income above the threshold.
    slab_at_threshold = _slab_tax(threshold - cg_total, slabs)
    tax_at_threshold = slab_at_threshold + cg_tax
    surcharge_at_threshold = tax_at_threshold * prev_rate / Decimal(100)
    allowed_total = (tax_at_threshold + surcharge_at_threshold
                     + (surcharge_income - threshold))
    actual_total = pre_surcharge + surcharge
    relief = max(Decimal(0), actual_total - allowed_total)
    return surcharge - relief, relief


def compute_tax(inp: TaxInput) -> TaxResult:
    table = load_rate_table(inp.assessment_year)
    regime_cfg = table["regimes"][inp.regime.value]

    gti = (d(inp.salary_gross) + d(inp.rental_income)
           + d(inp.other_income) + d(inp.business_income))

    total_deductions, ded_detail = _apply_deductions(inp, regime_cfg)
    taxable_income = _round_income(max(Decimal(0), gti - total_deductions))

    slabs = regime_cfg["slabs"]
    tax_before_rebate = _slab_tax(taxable_income, slabs)

    # §87A rebate — computed on slab income only (special-rate CG excluded).
    reb = regime_cfg["rebate_87a"]
    rebate = Decimal(0)
    if taxable_income <= d(reb["max_taxable_income"]):
        rebate = min(tax_before_rebate, d(reb["max_rebate"]))
    tax_after_rebate = tax_before_rebate - rebate

    # Marginal relief just above the rebate ceiling (new regime).
    if reb.get("marginal_relief") and taxable_income > d(reb["max_taxable_income"]):
        excess = taxable_income - d(reb["max_taxable_income"])
        if tax_after_rebate > excess:
            rebate = tax_after_rebate - excess
            tax_after_rebate = excess

    cg_tax, cg_lines = _capital_gains_tax(inp, table.get("capital_gains", {}))

    cg_total = sum((d(c.amount) for c in inp.capital_gains), Decimal(0))
    surcharge_income = taxable_income + cg_total
    surcharge, marginal_relief = _surcharge(
        tax_after_rebate, cg_tax, surcharge_income, cg_total,
        slabs, regime_cfg.get("surcharge_bands", []),
    )

    cess_rate = d(table["cess_rate_pct"]) / Decimal(100)
    taxable_before_cess = tax_after_rebate + cg_tax + surcharge
    cess = taxable_before_cess * cess_rate

    total_tax = _round_rupee(taxable_before_cess + cess)
    paid = d(inp.tds_paid) + d(inp.advance_tax_paid)
    refund_or_due = _round_rupee(paid - total_tax)

    return TaxResult(
        assessment_year=inp.assessment_year,
        regime=inp.regime,
        rules_version=table["version"],
        gross_total_income=_round_rupee(gti),
        total_deductions=_round_rupee(total_deductions),
        taxable_income=taxable_income,
        tax_before_rebate=_round_rupee(tax_before_rebate),
        rebate_87a=_round_rupee(rebate),
        tax_after_rebate=_round_rupee(tax_after_rebate),
        capital_gains_tax=_round_rupee(cg_tax),
        surcharge=_round_rupee(surcharge),
        marginal_relief=_round_rupee(marginal_relief),
        cess=_round_rupee(cess),
        total_tax=total_tax,
        tds_paid=_round_rupee(paid),
        refund_or_due=refund_or_due,
        breakdown={
            "deductions": ded_detail,
            "capital_gains": cg_lines,
            "cess_rate_pct": str(table["cess_rate_pct"]),
        },
    )


def compare_regimes(base: TaxInput) -> dict:
    """Run both regimes and recommend the cheaper one (§4.3 /tax/compare)."""
    from dataclasses import replace

    old = compute_tax(replace(base, regime=Regime.OLD))
    new = compute_tax(replace(base, regime=Regime.NEW))
    recommended = Regime.NEW if new.total_tax <= old.total_tax else Regime.OLD
    savings = abs(old.total_tax - new.total_tax)
    return {
        "assessment_year": base.assessment_year,
        "rules_version": old.rules_version,
        "old_regime": old,
        "new_regime": new,
        "recommended_regime": recommended.value,
        "savings_vs_alternative": savings,
    }
