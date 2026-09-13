"""The pipeline orchestrator.

The orchestrator runs the runtime stages in order.
It checks feasibility first.
It extracts facts second.
It computes derived values third.
It writes the report last.

The flow is a fixed sequence, not an open agent loop.
The task is well defined, so code controls the order.
Code control gives a clear, testable, and cheap pipeline.
"""
from __future__ import annotations

from .capabilities import CapabilityRegistry
from .composition import compose
from .computation import check_policy, compute_derived
from .extraction import extract_facts
from .feasibility import assess
from .models import Blueprint, DocumentRef, GapReport, Memo
from .providers.base import ProviderAdapter
from .render import render_markdown


class RunResult:
    """The full output of one pipeline run."""

    def __init__(self, blueprint: Blueprint, gaps: GapReport, memo: Memo) -> None:
        self.blueprint = blueprint
        self.gaps = gaps
        self.memo = memo

    def to_markdown(self) -> str:
        """Return the report and the gap report as Markdown."""
        return render_markdown(self.memo, self.gaps)


def run(
    blueprint: Blueprint,
    documents: list[DocumentRef],
    provider: ProviderAdapter,
    registry: CapabilityRegistry,
) -> RunResult:
    """Run the runtime pipeline and return the result."""
    # Stage 1: check feasibility before any model work.
    gaps = assess(blueprint, documents, registry)

    # Stage 2: extract facts. Each document is read one time.
    ledger = extract_facts(blueprint, documents, provider)

    # Stage 3: compute derived values in code.
    compute_derived(blueprint, ledger)
    policy_results = check_policy(ledger)

    # Stage 4: write the report from the compact ledger.
    sections, warnings = compose(blueprint, ledger, provider, policy_results)

    memo = Memo(
        report_type=blueprint.report_type,
        sections=sections,
        policy_results=policy_results,
        warnings=warnings,
    )
    return RunResult(blueprint=blueprint, gaps=gaps, memo=memo)
