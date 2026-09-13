"""The feasibility stage. This runs before extraction.

The stage compares the blueprint against two things.
It compares against the capability registry.
It compares against the documents that the user provided.
It reports each gap before the pipeline does any model work.

The system fails loudly and early, not silently and late.
A clear gap report is the trust story of the system.
"""
from __future__ import annotations

from .capabilities import CapabilityRegistry
from .models import Blueprint, DocumentRef, GapReport


def assess(
    blueprint: Blueprint,
    documents: list[DocumentRef],
    registry: CapabilityRegistry,
) -> GapReport:
    """Return a gap report for a run."""
    report = GapReport()
    provided_types = {doc.doc_type for doc in documents}

    for doc_type in sorted(blueprint.required_doc_types()):
        if not registry.can_extract(doc_type):
            # The system has no extractor for this document type.
            report.capability_gaps.append(
                f"No extractor exists for document type '{doc_type}'."
            )
        elif doc_type not in provided_types:
            # The extractor exists, but the user did not provide the document.
            report.data_gaps.append(
                f"The document type '{doc_type}' is required but was not provided."
            )

    for name in sorted(blueprint.required_computations()):
        if not registry.can_compute(name):
            report.computation_gaps.append(
                f"No computation exists for '{name}'."
            )

    return report
