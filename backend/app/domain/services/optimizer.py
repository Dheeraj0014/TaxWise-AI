"""Rule-based tax-saving optimizer (§4 Optimizer, §13 Phase 5).

Deterministic heuristics only — the LLM layer (out of MVP scope) would later
rank/explain these with cited sources. Each recommendation quantifies the saving
by actually re-running the engine with the suggested change, never guessing.

Ideas are declared in one catalog and tagged by what they do to your money:

    expense    money you are ALREADY spending (premiums, loan interest, rent).
               Claiming it costs nothing extra — this is free relief.
    structural restructuring rather than spending (regime switch, employer NPS,
               harvesting the LTCG exemption). No new cash required.
    invest     the money stays yours (ELSS/PPF/NPS). You part with liquidity,
               not with wealth.
    donate     the money leaves for good. Relief here is a DISCOUNT on giving,
               never a way to end up richer.

That tagging is load-bearing, not decoration. An optimizer that ranked an 80G
donation beside an ELSS investment purely by "tax saved" would advise giving
away a lakh to save thirty thousand. Every idea therefore reports
`amount_modelled` and `net_cost` next to `estimated_saving`, ideas are ordered
cheapest-first (free relief before cash outlay), and donations rank last.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from app.domain.entities.tax import Regime, TaxInput
from app.domain.services.rate_tables import d, load_rate_table
from app.domain.services.tax_engine import compute_tax

# Modelling step for sections the statute leaves uncapped (80G, 80E, HRA…).
# Relief there scales linearly, so one unit is enough to show the marginal rate.
UNIT = Decimal(10000)
SENIOR_AGE = 60

# Ranked by what the idea asks of your wallet, not by headline saving. Relief on
# money already committed (or on restructuring) is free, so it outranks anything
# needing fresh cash however large; donations rank last because they alone leave
# you poorer. Ties inside a band break on saving, descending.
_CASH_REQUIRED = {"expense": 0, "structural": 0, "invest": 1, "donate": 2}


@dataclass(frozen=True)
class Idea:
    """One catalog entry. `cap` is filled from the rate table when present."""
    section: str
    title: str
    kind: str
    documents: tuple[str, ...]
    note: str
    fallback_cap: Decimal | None = None   # used when the table caps nothing
    seniors_only: bool = False
    not_for_seniors: bool = False


CATALOG: tuple[Idea, ...] = (
    # --- expense: you are already paying these ------------------------------
    Idea(
        "80D", "Claim health-insurance premiums under 80D", "expense",
        ("Insurance premium receipt", "Policy schedule"),
        "Covers self, spouse, children and parents. Preventive health check-ups "
        "count within the limit. Premiums for senior-citizen parents carry a "
        "higher ceiling than your own cover.",
    ),
    Idea(
        "24b", "Deduct home-loan interest under section 24(b)", "expense",
        ("Lender interest certificate", "Possession/completion proof"),
        "Interest on a self-occupied property. The lender's annual interest "
        "certificate splits principal (80C) from interest (24b) for you.",
    ),
    Idea(
        "80E", "Deduct education-loan interest under 80E", "expense",
        ("Lender interest certificate",),
        "Interest is fully deductible with NO upper limit, for up to 8 "
        "consecutive years from when repayment starts. Principal does not qualify.",
    ),
    Idea(
        "80EEA", "Claim the extra first-home interest under 80EEA", "expense",
        ("Lender interest certificate", "Stamp-duty valuation"),
        "Stacks on top of 24(b) for first-time buyers of an affordable home, "
        "subject to the stamp-duty value and loan-sanction-date conditions.",
        fallback_cap=Decimal(150000),
    ),
    Idea(
        "hra_exempt", "Claim HRA exemption on rent you already pay", "expense",
        ("Rent receipts", "Rent agreement", "Landlord PAN if rent > ₹1L/yr"),
        "Exempt amount is the LEAST of: actual HRA received, rent paid minus 10% "
        "of salary, or 50% of salary (metro) / 40% (non-metro).",
    ),
    Idea(
        "80TTA", "Claim savings-account interest under 80TTA", "expense",
        ("Bank interest certificate",),
        "Interest on savings deposits. Fixed-deposit interest does not qualify.",
        not_for_seniors=True,
    ),
    Idea(
        "80TTB", "Claim senior-citizen deposit interest under 80TTB", "expense",
        ("Bank interest certificate",),
        "For those 60+: covers savings AND fixed/recurring deposit interest, and "
        "replaces 80TTA rather than adding to it.",
        seniors_only=True,
    ),

    # --- structural: no new cash required -----------------------------------
    Idea(
        "80CCD2", "Route part of your CTC into employer NPS (80CCD(2))", "structural",
        ("Salary structure letter", "NPS statement"),
        "Your employer's NPS contribution is deductible OVER AND ABOVE the 80C "
        "and 80CCD(1B) limits, and it survives in the new regime too. This is a "
        "salary-restructuring conversation with payroll, not extra spending.",
    ),

    # --- invest: the money stays yours --------------------------------------
    Idea(
        "80C", "Max out 80C (ELSS / PPF / EPF / life insurance)", "invest",
        ("Investment proofs",),
        "ELSS carries the shortest lock-in at 3 years; PPF runs 15 years but is "
        "tax-free on maturity. Home-loan principal and children's tuition fees "
        "already count here — check before adding new money.",
    ),
    Idea(
        "80CCD1B", "Add NPS Tier-1 for the extra 80CCD(1B) ₹50k", "invest",
        ("NPS statement",),
        "A dedicated ₹50,000 on top of the 80C ceiling. Locked until age 60, and "
        "only part of the maturity corpus comes out tax-free — treat it as "
        "retirement money, not savings you can reach.",
    ),

    # --- donate: the money is gone ------------------------------------------
    Idea(
        "80G", "Deduct eligible donations under 80G", "donate",
        ("Stamped 80G receipt", "Donee PAN & registration number"),
        "Enter the ELIGIBLE amount, not the cheque value: most funds qualify at "
        "50%, some at 100%, and several are further capped at 10% of adjusted "
        "gross total income. Cash donations above ₹2,000 are disallowed outright.",
    ),
)


def _saving_from_extra_deduction(base: TaxInput, section: str,
                                 extra: Decimal) -> Decimal:
    merged = dict(base.deductions)
    merged[section] = merged.get(section, Decimal(0)) + extra
    before = compute_tax(base).total_tax
    after = compute_tax(replace(base, deductions=merged)).total_tax
    return max(Decimal(0), before - after)


def _ltcg_harvest(base: TaxInput, table: dict) -> dict | None:
    """Book long-term equity gains up to the annual 112A exemption, tax-free.

    The §112A exemption does not carry forward — every unused rupee expires on
    31 March. Selling and immediately rebuying resets your cost base at no tax
    cost, so future gains are measured from a higher floor.
    """
    rules = (table.get("capital_gains") or {}).get("112A")
    if not rules:
        return None
    exemption = d(rules.get("exemption", 0))
    if exemption <= 0:
        return None

    booked = sum((d(cg.amount) for cg in base.capital_gains
                  if cg.tax_section == "112A"), Decimal(0))
    unused = exemption - booked
    if unused <= 0:
        return None

    # Tax that this headroom would otherwise attract once the exemption is gone.
    rate = d(rules["rate_pct"]) / Decimal(100)
    cess = d(table["cess_rate_pct"]) / Decimal(100)
    saving = (unused * rate * (Decimal(1) + cess)).quantize(Decimal(1))
    if saving <= 0:
        return None

    return {
        "title": "Harvest your tax-free LTCG allowance before 31 March",
        "section": "112A",
        "kind": "structural",
        "estimated_saving": str(saving),
        "amount_modelled": str(unused),
        "headroom": str(unused),
        "net_cost": "0",
        "retained": True,
        "illustrative": True,
        "priority": 0,
        "required_documents": ["Broker capital-gains statement"],
        "deadline": f"31 Mar {base.assessment_year}",
        "note": (
            "If you hold listed equity or equity mutual funds bought over a year "
            f"ago: ₹{unused} of your ₹{exemption} annual long-term exemption is "
            "still unused, and it does not carry forward. Booking gains up to that "
            "limit — then rebuying — resets your cost base at zero tax cost. "
            "Ignore this if you hold no equity, or if selling would breach an "
            "ELSS lock-in."
        ),
    }


def _is_senior(base: TaxInput) -> bool:
    return base.age is not None and base.age >= SENIOR_AGE


def combined_saving(base: TaxInput, recs: list[dict]) -> Decimal:
    """Tax actually saved by taking ALL the deduction ideas together.

    Per-idea `estimated_saving` answers "what if I did just this one", each
    measured against the same starting point. Those figures do NOT add up:
    claiming home-loan interest can drop you into a lower slab, which makes the
    next deduction worth less. Summing them therefore overstates the prize — the
    more ideas in the catalog, the worse the overstatement. This applies them all
    at once and measures the real delta.

    Donations are excluded: they reduce tax only by making you poorer first.
    """
    merged = dict(base.deductions)
    for r in recs:
        if r["kind"] == "donate":
            continue
        section, amount = r["section"], r.get("amount_modelled")
        if not amount or section not in _DEDUCTION_SECTIONS:
            continue          # e.g. 112A harvesting is not a Chapter VI-A claim
        merged[section] = merged.get(section, Decimal(0)) + d(amount)

    before = compute_tax(base).total_tax
    after = compute_tax(replace(base, deductions=merged)).total_tax
    saving = max(Decimal(0), before - after)

    # Non-deduction ideas (LTCG harvesting) act on a separate tax base, so their
    # saving is genuinely additive rather than slab-coupled.
    for r in recs:
        if r["section"] not in _DEDUCTION_SECTIONS and r["kind"] != "donate":
            saving += d(r["estimated_saving"])
    return saving


_DEDUCTION_SECTIONS = {idea.section for idea in CATALOG}


def recommend(base: TaxInput) -> list[dict]:
    """Return ranked strategies for the OLD regime (where deductions apply)."""
    recs: list[dict] = []
    if base.regime != Regime.OLD:
        # Deductions only bite in the old regime; suggest comparing first.
        new_tax = compute_tax(base).total_tax
        old_tax = compute_tax(replace(base, regime=Regime.OLD)).total_tax
        if old_tax < new_tax:
            recs.append({
                "title": "Switch to the OLD regime",
                "section": "115BAC",
                "kind": "structural",
                "estimated_saving": str(new_tax - old_tax),
                "amount_modelled": "0",
                "net_cost": "0",
                "retained": True,
                "illustrative": False,
                "priority": 1,
                "required_documents": [],
                "deadline": None,
                "note": "Your deductions make the old regime cheaper this year.",
            })
        return recs

    table = load_rate_table(base.assessment_year)
    regime_cfg = table["regimes"]["old"]
    allowed = set(regime_cfg.get("allowed_deductions", []))
    caps = {k: d(v) for k, v in regime_cfg.get("deduction_caps", {}).items()}
    senior = _is_senior(base)

    for idea in CATALOG:
        if idea.section not in allowed:
            continue
        if idea.seniors_only and not senior:
            continue
        if idea.not_for_seniors and senior:
            continue

        cap = caps.get(idea.section) or idea.fallback_cap
        claimed = d(base.deductions.get(idea.section, Decimal(0)))

        if cap is not None:
            headroom = cap - claimed
            if headroom <= 0:          # already maxed out — nothing to suggest
                continue
            amount, capped = headroom, True
        else:
            # Statutorily uncapped: price one unit and let the note extrapolate.
            amount, capped = UNIT, False

        saving = _saving_from_extra_deduction(base, idea.section, amount)
        if saving <= 0:                # already below the tax-free threshold
            continue

        # `net_cost` is cash you never see again. An investment changes form but
        # stays yours; an expense-linked claim rides on spending you have already
        # committed to, so claiming it costs nothing extra. Only a donation
        # genuinely leaves — and there the relief is a discount, not a profit.
        retained = idea.kind != "donate"
        net_cost = Decimal(0) if retained else max(Decimal(0), amount - saving)

        note = idea.note
        if capped:
            note = f"₹{amount} of {idea.section} headroom remains. {note}"
        else:
            note = (
                f"Uncapped — every ₹{UNIT} you claim cuts tax by about ₹{saving}. "
                f"{note}"
            )

        recs.append({
            "title": idea.title,
            "section": idea.section,
            "kind": idea.kind,
            "estimated_saving": str(saving),
            "amount_modelled": str(amount),
            "headroom": str(amount) if capped else None,
            "net_cost": str(net_cost),
            "retained": retained,
            "illustrative": not capped,
            "priority": 0,
            "required_documents": list(idea.documents),
            "deadline": f"31 Mar {base.assessment_year}",
            "note": note,
        })

    harvest = _ltcg_harvest(base, table)
    if harvest:
        recs.append(harvest)

    # Free relief first, cash-out-the-door last; biggest saving breaks ties.
    recs.sort(key=lambda r: (_CASH_REQUIRED.get(r["kind"], 9),
                             -Decimal(r["estimated_saving"])))
    for i, r in enumerate(recs, 1):
        r["priority"] = i
    return recs
