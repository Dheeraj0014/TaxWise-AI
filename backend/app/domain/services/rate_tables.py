"""Loads versioned tax rate tables from YAML config (§5: rates are data).

A new Budget year = a new YAML file + tests. No engine code changes.
"""
from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

RULES_DIR = Path(__file__).resolve().parents[2] / "config" / "tax_rules"


class RateTableNotFound(Exception):
    pass


@lru_cache(maxsize=32)
def load_rate_table(assessment_year: int) -> dict:
    """Return the parsed rules dict for an AY, or raise if unavailable."""
    path = RULES_DIR / f"AY{assessment_year}-{str(assessment_year + 1)[2:]}.yaml"
    if not path.exists():
        available = sorted(p.name for p in RULES_DIR.glob("*.yaml"))
        raise RateTableNotFound(
            f"No rate table for AY {assessment_year} (looked for {path.name}). "
            f"Available: {available}"
        )
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data


def available_years() -> list[int]:
    years = []
    for p in RULES_DIR.glob("*.yaml"):
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        years.append(int(data["assessment_year"]))
    return sorted(years)


def d(value) -> Decimal:
    """Coerce YAML numbers/strings to Decimal safely."""
    if value is None:
        return Decimal(0)
    return Decimal(str(value))
