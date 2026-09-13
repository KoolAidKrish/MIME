"""The capability registry.

The registry lists what the system can do today.
It names the document types that the system can extract.
It names the computations that the system can run.
The feasibility check compares a blueprint against this list.
The system reports a gap when a blueprint needs more than the list holds.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CapabilityRegistry:
    """The set of skills that the current build supports."""

    known_doc_types: set[str] = field(default_factory=set)
    known_computations: set[str] = field(default_factory=set)
    output_formats: set[str] = field(default_factory=lambda: {"markdown"})

    def can_extract(self, doc_type: str) -> bool:
        """Return ``True`` when the system has an extractor for the document type."""
        return doc_type in self.known_doc_types

    def can_compute(self, name: str) -> bool:
        """Return ``True`` when the system supports the computation."""
        return name in self.known_computations


def default_registry() -> CapabilityRegistry:
    """Return the registry for the prototype.

    The list is deliberately short.
    The demo shows a gap when a blueprint needs a type that is absent here.
    """
    return CapabilityRegistry(
        known_doc_types={
            "loan_application",
            "financial_statements",
            "debt_schedule",
            "appraisal_report",
            "guarantor_financials",
        },
        known_computations={"dscr", "ltv"},
        output_formats={"markdown"},
    )
