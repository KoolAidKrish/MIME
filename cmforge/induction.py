"""The induction engine. This is the compile step.

The engine reads one example report.
It produces a blueprint for that report format.
The blueprint is data that the runtime later executes.

The induction runs once per report format at design time.
A human reviews the blueprint before the runtime uses it.
This review keeps the low blast radius that a design-time step gives.
"""
from __future__ import annotations

from .contextpack import pack_context
from .models import Blueprint
from .providers.base import ProviderAdapter

# The schema tells a real model the exact output shape.
# The mock provider ignores the schema and uses its own rules.
_BLUEPRINT_SCHEMA = {
    "type": "object",
    "properties": {
        "report_type": {"type": "string"},
        "version": {"type": "integer"},
        "sections": {"type": "array"},
        "notes": {"type": "string"},
    },
    "required": ["report_type", "sections"],
    "additionalProperties": True,
}

_INSTRUCTION = (
    "Read the example report below. "
    "Return a blueprint for this report format. "
    "List each section. "
    "For each section, list the data fields that the section needs. "
    "For each field, name the source document type. "
    "Mark a field as computed when it comes from other fields."
)


def induce_blueprint(
    exemplar_text: str,
    provider: ProviderAdapter,
    report_type: str = "Credit Memo",
) -> Blueprint:
    """Return a blueprint that describes the example report."""
    prompt = _INSTRUCTION + "\n\n" + pack_context(
        {"exemplar_text": exemplar_text, "report_type": report_type}
    )
    data = provider.extract_structured(prompt, _BLUEPRINT_SCHEMA, task="induction")
    # Pydantic validates the shape. A wrong shape fails here with a clear message.
    return Blueprint.model_validate(data)
