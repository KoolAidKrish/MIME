"""The computation stage.

This stage runs in plain Python, not in the language model.
It computes ratios from the extracted facts.
It checks the policy rules.

The rule is simple and strict. The model never does arithmetic.
Code computes every number. Code checks every policy.
This choice removes a whole class of model error.
It also gives a clear audit trail for each number.
"""
from __future__ import annotations

from typing import Callable, Optional

from .models import Blueprint, Fact, FactLedger, PolicyResult

# A computation reads the ledger and returns a value.
Computation = Callable[[FactLedger], Optional[float]]


def _dscr(ledger: FactLedger) -> Optional[float]:
    """Return the debt service coverage ratio.

    The ratio divides the net operating income by the annual debt service.
    """
    noi = ledger.get("net_operating_income")
    service = ledger.get("annual_debt_service")
    if noi is None or service is None or not service.value:
        return None
    return float(noi.value) / float(service.value)


def _ltv(ledger: FactLedger) -> Optional[float]:
    """Return the loan to value ratio.

    The ratio divides the loan amount by the appraised value.
    """
    loan = ledger.get("loan_amount")
    value = ledger.get("appraised_value")
    if loan is None or value is None or not value.value:
        return None
    return float(loan.value) / float(value.value)


_COMPUTATIONS: dict[str, Computation] = {
    "dscr": _dscr,
    "ltv": _ltv,
}


def compute_derived(blueprint: Blueprint, ledger: FactLedger) -> None:
    """Add each computed value to the ledger.

    The function edits the ledger in place.
    """
    for field in blueprint.all_fields():
        if not field.computed or not field.computation:
            continue
        if ledger.has(field.name):
            continue
        func = _COMPUTATIONS.get(field.computation)
        if func is None:
            continue
        value = func(ledger)
        if value is None:
            continue
        ledger.add(
            Fact(
                field_name=field.name,
                value=value,
                source_doc="computed",
                source_quote=f"computed by rule '{field.computation}'",
                computed=True,
            )
        )


def check_policy(ledger: FactLedger) -> list[PolicyResult]:
    """Return the result of each policy rule.

    The prototype ships a small, clear rule set.
    A real system loads these rules from credit policy.
    """
    results: list[PolicyResult] = []

    dscr = ledger.get("dscr")
    if dscr is not None:
        passed = float(dscr.value) >= 1.25
        results.append(
            PolicyResult(
                rule="DSCR >= 1.25",
                passed=passed,
                detail=f"DSCR is {float(dscr.value):.2f}.",
            )
        )

    ltv = ledger.get("ltv")
    if ltv is not None:
        passed = float(ltv.value) <= 0.80
        results.append(
            PolicyResult(
                rule="LTV <= 80%",
                passed=passed,
                detail=f"LTV is {float(ltv.value) * 100:.1f}%.",
            )
        )

    return results
