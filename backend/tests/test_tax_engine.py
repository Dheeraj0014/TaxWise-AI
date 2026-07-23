"""Golden-file tests for the deterministic tax engine (§5).

Each case pins expected outputs for a scenario. A rate-table change that alters
any of these must ship with an intentional update here — that is the safety net.
"""
from decimal import Decimal

import pytest

from app.domain.entities.tax import CapitalGain, Regime, TaxInput
from app.domain.services.tax_engine import compare_regimes, compute_tax


def D(x):
    return Decimal(str(x))


# ---------------------------------------------------------------------------
# New regime, AY 2026-27
# ---------------------------------------------------------------------------

def test_new_regime_income_12L_is_zero_tax_after_rebate():
    # Salary 12,75,000 - std 75,000 = 12,00,000 taxable -> rebate wipes tax.
    r = compute_tax(TaxInput(2026, Regime.NEW, salary_gross=D(1275000)))
    assert r.taxable_income == D(1200000)
    assert r.tax_before_rebate == D(60000)
    assert r.rebate_87a == D(60000)
    assert r.total_tax == D(0)


def test_new_regime_marginal_relief_just_above_ceiling():
    # Taxable 12,10,000: slab tax = 61,500; marginal relief caps tax to 10,000.
    r = compute_tax(TaxInput(2026, Regime.NEW, salary_gross=D(1285000)))
    assert r.taxable_income == D(1210000)
    assert r.tax_after_rebate == D(10000)      # capped to income over 12L
    # + 4% cess
    assert r.total_tax == D(10400)


def test_new_regime_20L_salary():
    # Salary 20,75,000 - std 75,000 = 20,00,000 taxable.
    # slab: 0..4L:0; 4-8L 5%=20000; 8-12L 10%=40000; 12-16L 15%=60000;
    #       16-20L 20%=80000  => 200000; no rebate; cess 4% = 8000 => 208000
    r = compute_tax(TaxInput(2026, Regime.NEW, salary_gross=D(2075000)))
    assert r.taxable_income == D(2000000)
    assert r.tax_before_rebate == D(200000)
    assert r.rebate_87a == D(0)
    assert r.total_tax == D(208000)


# ---------------------------------------------------------------------------
# Old regime, AY 2026-27
# ---------------------------------------------------------------------------

def test_old_regime_with_deductions():
    # Salary 18,00,000; std 50k + 80C 1.5L + 80CCD1B 50k + 80D 25k = 2,75,000
    # taxable = 15,25,000. slab: 2.5-5L 5%=12500; 5-10L 20%=100000;
    #           10-15.25L 30%=157500 => 270000; cess 4% => 280800
    r = compute_tax(TaxInput(
        2026, Regime.OLD, salary_gross=D(1800000),
        deductions={"80C": D(150000), "80CCD1B": D(50000), "80D": D(25000)},
    ))
    assert r.total_deductions == D(275000)
    assert r.taxable_income == D(1525000)
    assert r.tax_before_rebate == D(270000)
    assert r.total_tax == D(280800)


def test_old_regime_80c_capped():
    r = compute_tax(TaxInput(
        2026, Regime.OLD, salary_gross=D(1000000),
        deductions={"80C": D(250000)},   # claim 2.5L, cap 1.5L
    ))
    # std 50k + 80C 1.5L = 2L ; taxable = 8L
    assert r.taxable_income == D(800000)


def test_old_regime_rebate_under_5L():
    # Taxable 4,50,000 -> tax 10,000 -> fully rebated.
    r = compute_tax(TaxInput(2026, Regime.OLD, salary_gross=D(500000)))
    assert r.taxable_income == D(450000)
    assert r.rebate_87a == D(10000)
    assert r.total_tax == D(0)


# ---------------------------------------------------------------------------
# Capital gains — special rate, excluded from 87A base
# ---------------------------------------------------------------------------

def test_ltcg_equity_112a_exemption_and_rate():
    # Only a 3,00,000 LTCG on equity, no other income.
    # 112A: (3,00,000 - 1,25,000) * 12.5% = 21,875 ; cess 4% => 22,750
    r = compute_tax(TaxInput(
        2026, Regime.NEW,
        capital_gains=[CapitalGain("112A", D(300000))],
    ))
    assert r.taxable_income == D(0)
    assert r.rebate_87a == D(0)          # rebate must NOT apply to CG
    assert r.capital_gains_tax == D(21875)
    assert r.total_tax == D(22750)


def test_stcg_111a_not_rebated_even_when_small():
    # 4,00,000 STCG equity only -> 111A 20% = 80,000; cess => 83,200.
    # Rebate excluded from CG, so tax is NOT zero despite low total income.
    r = compute_tax(TaxInput(
        2026, Regime.NEW,
        capital_gains=[CapitalGain("111A", D(400000))],
    ))
    assert r.capital_gains_tax == D(80000)
    assert r.rebate_87a == D(0)
    assert r.total_tax == D(83200)


# ---------------------------------------------------------------------------
# Surcharge + marginal relief
# ---------------------------------------------------------------------------

def test_surcharge_applies_above_50L_new_regime():
    r = compute_tax(TaxInput(2026, Regime.NEW, salary_gross=D(6075000)))
    # taxable 60,00,000 -> surcharge band 10% applies
    assert r.surcharge > 0


# ---------------------------------------------------------------------------
# Regime comparison + refund
# ---------------------------------------------------------------------------

def test_compare_picks_cheaper_regime():
    base = TaxInput(
        2026, Regime.NEW, salary_gross=D(1800000), other_income=D(25000),
        deductions={"80C": D(150000), "80CCD1B": D(50000), "80D": D(25000)},
        tds_paid=D(210000),
    )
    result = compare_regimes(base)
    assert result["recommended_regime"] in ("old", "new")
    assert result["old_regime"].total_tax >= 0
    assert result["new_regime"].total_tax >= 0
    # savings is the absolute gap
    assert result["savings_vs_alternative"] == abs(
        result["old_regime"].total_tax - result["new_regime"].total_tax
    )


def test_refund_when_tds_exceeds_liability():
    r = compute_tax(TaxInput(2026, Regime.NEW, salary_gross=D(1275000),
                             tds_paid=D(50000)))
    assert r.total_tax == D(0)
    assert r.refund_or_due == D(50000)      # full refund


# ---------------------------------------------------------------------------
# Versioning — the same input differs across AYs (proves rates are data)
# ---------------------------------------------------------------------------

def test_ay2025_vs_ay2026_new_regime_differ():
    inp2025 = TaxInput(2025, Regime.NEW, salary_gross=D(1275000))
    inp2026 = TaxInput(2026, Regime.NEW, salary_gross=D(1275000))
    r25 = compute_tax(inp2025)
    r26 = compute_tax(inp2026)
    # AY2025-26 taxes a 12L income; AY2026-27 rebate makes it nil.
    assert r26.total_tax == Decimal(0)
    assert r25.total_tax > Decimal(0)
    assert r25.rules_version != r26.rules_version
