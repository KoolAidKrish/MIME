"""The extraction stage. This runs once per document.

The stage reads each source document one time.
It pulls the values that the blueprint needs.
It writes each value to the fact ledger with its source.

The design touches each raw document once.
Later stages read the compact ledger, not the raw documents.
This keeps the token cost low when the document count is high.
"""
from __future__ import annotations

from .contextpack import pack_context
from .models import Blueprint, DocumentRef, Fact, FactLedger
from .providers.base import ProviderAdapter

# Structured outputs require additionalProperties=false on every object.
# They also expect each property to appear in "required".
# The value uses anyOf, because a plain type union is less widely supported.
_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean"},
        "value": {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "null"}]},
        "source_quote": {"type": "string"},
    },
    "required": ["found", "value", "source_quote"],
    "additionalProperties": False,
}

_INSTRUCTION = (
    "Read the document below. "
    "Find the value for the named field. "
    "Return the value and the exact source text. "
    "Return found=false when the value is absent."
)


def extract_facts(
    blueprint: Blueprint,
    documents: list[DocumentRef],
    provider: ProviderAdapter,
) -> FactLedger:
    """Return a fact ledger for the documents.

    The stage skips computed fields.
    A later stage computes those values from the extracted facts.
    """
    ledger = FactLedger()
    by_type: dict[str, DocumentRef] = {doc.doc_type: doc for doc in documents}

    for field in blueprint.all_fields():
        if field.computed:
            continue
        document = by_type.get(field.source_doc_type)
        if document is None:
            # The document is absent. The feasibility check already reports this gap.
            continue

        prompt = _INSTRUCTION + "\n\n" + pack_context(
            {
                "document_text": document.text,
                "field": {
                    "name": field.name,
                    "type": field.type,
                    "extraction_hint": field.extraction_hint,
                    "description": field.description,
                },
            }
        )
        result = provider.extract_structured(prompt, _EXTRACTION_SCHEMA, task="extraction")
        if not result.get("found"):
            continue

        ledger.add(
            Fact(
                field_name=field.name,
                value=result.get("value"),
                source_doc=document.name,
                source_quote=result.get("source_quote", ""),
                char_start=result.get("char_start", -1),
                char_end=result.get("char_end", -1),
                confidence=result.get("confidence", 1.0),
            )
        )
    return ledger
