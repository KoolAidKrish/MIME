"""The composition stage. This writes the report.

The stage builds each section from the fact ledger.
It gives the provider only the facts, not the raw documents.
It attaches a citation for each fact that it uses.
It records a warning when a required field is absent.
"""
from __future__ import annotations

from .contextpack import pack_context
from .models import Blueprint, FactLedger, MemoSection, PolicyResult
from .providers.base import ProviderAdapter

_INSTRUCTION = (
    "Write one report section from the facts below. "
    "Use short, factual sentences in the active voice. "
    "State each value once. "
    "Do not add any number that is not in the facts."
)


def compose(
    blueprint: Blueprint,
    ledger: FactLedger,
    provider: ProviderAdapter,
    policy_results: list[PolicyResult],
) -> tuple[list[MemoSection], list[str]]:
    """Return the report sections and the run warnings."""
    sections: list[MemoSection] = []
    warnings: list[str] = []

    for section in blueprint.sections:
        facts_payload = []
        citations: list[str] = []
        missing: list[str] = []

        for field in section.required_fields:
            fact = ledger.get(field.name)
            if fact is None:
                if field.required:
                    missing.append(field.name)
                    warnings.append(
                        f"Section '{section.title}' is missing the field '{field.name}'."
                    )
                continue
            facts_payload.append(
                {
                    "name": field.name,
                    "description": field.description,
                    "type": field.type,
                    "value": fact.value,
                }
            )
            if fact.source_quote:
                citations.append(f"{field.name}: {fact.source_doc} - \"{fact.source_quote}\"")

        prompt = _INSTRUCTION + "\n\n" + pack_context(
            {
                "section_title": section.title,
                "facts": facts_payload,
                "missing": missing,
            }
        )
        narrative = provider.complete(prompt, task="composition", max_tokens=1024)

        sections.append(
            MemoSection(
                id=section.id,
                title=section.title,
                narrative=narrative,
                citations=citations,
            )
        )

    return sections, warnings
