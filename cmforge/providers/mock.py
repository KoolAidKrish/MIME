"""The mock provider.

The mock provider is a test double for a language model.
It runs offline and needs no API key.
It produces deterministic output from simple rules.
This lets the whole pipeline run and demo without a network.
The mock reads the structured context that the engine packs into each prompt.

The mock is coupled to the engine's prompt format on purpose.
That coupling is the explicit contract of the test double.
A real provider reads the same prompt as natural instruction instead.
"""
from __future__ import annotations

import re
from typing import Any

from ..contextpack import unpack_context
from .base import Capability, ProviderAdapter

# The mock maps a keyword in the example report to a field specification.
# A real model would infer these fields from the text on its own.
_KEYWORD_FIELDS: list[dict[str, Any]] = [
    {
        "trigger": "borrower",
        "name": "borrower_name",
        "type": "string",
        "source_doc_type": "loan_application",
        "extraction_hint": "Borrower",
        "description": "legal name of the borrower",
    },
    {
        "trigger": "industry",
        "name": "industry",
        "type": "string",
        "source_doc_type": "loan_application",
        "extraction_hint": "Industry",
        "description": "industry of the borrower",
    },
    {
        "trigger": "loan amount",
        "name": "loan_amount",
        "type": "number",
        "source_doc_type": "loan_application",
        "extraction_hint": "Loan Amount",
        "description": "requested loan amount",
    },
    {
        "trigger": "revenue",
        "name": "annual_revenue",
        "type": "number",
        "source_doc_type": "financial_statements",
        "extraction_hint": "Annual Revenue",
        "description": "annual revenue of the borrower",
    },
    {
        "trigger": "net operating income",
        "name": "net_operating_income",
        "type": "number",
        "source_doc_type": "financial_statements",
        "extraction_hint": "Net Operating Income",
        "description": "net operating income",
    },
    {
        "trigger": "debt service",
        "name": "annual_debt_service",
        "type": "number",
        "source_doc_type": "debt_schedule",
        "extraction_hint": "Annual Debt Service",
        "description": "annual debt service",
    },
    {
        "trigger": "dscr",
        "name": "dscr",
        "type": "number",
        "source_doc_type": "",
        "computed": True,
        "computation": "dscr",
        "description": "debt service coverage ratio",
    },
    {
        "trigger": "appraised",
        "name": "appraised_value",
        "type": "number",
        "source_doc_type": "appraisal_report",
        "extraction_hint": "Appraised Value",
        "description": "appraised value of the collateral",
    },
    {
        "trigger": "loan-to-value",
        "name": "ltv",
        "type": "number",
        "source_doc_type": "",
        "computed": True,
        "computation": "ltv",
        "description": "loan to value ratio",
    },
    {
        "trigger": "guarantor",
        "name": "guarantor_net_worth",
        "type": "number",
        "source_doc_type": "guarantor_financials",
        "extraction_hint": "Guarantor Net Worth",
        "description": "net worth of the guarantor",
    },
    {
        "trigger": "environmental",
        "name": "environmental_status",
        "type": "string",
        "source_doc_type": "environmental_report",
        "extraction_hint": "Environmental Status",
        "description": "environmental review status",
    },
]


class MockProvider(ProviderAdapter):
    """A deterministic stand-in for a language model."""

    name = "mock"
    # The mock returns spans, so it can support citations.
    # The mock returns typed data, so it can support structured output.
    capabilities = {Capability.STRUCTURED_OUTPUT, Capability.CITATIONS}

    def complete(self, prompt: str, *, task: str, max_tokens: int = 1024) -> str:
        """Return free text.

        The mock uses this method only for narrative tasks.
        """
        context = unpack_context(prompt)
        if task == "composition":
            return self._compose(context)
        return ""

    def extract_structured(self, prompt: str, schema: dict, *, task: str) -> dict:
        """Return structured data for a task."""
        context = unpack_context(prompt)
        if task == "induction":
            return self._induce(context)
        if task == "extraction":
            return self._extract(context)
        return {}

    # -- induction -----------------------------------------------------------

    def _induce(self, context: dict) -> dict:
        """Build a blueprint from an example report.

        The mock detects sections from Markdown headings.
        It infers fields from keywords in each section.
        """
        text: str = context.get("exemplar_text", "")
        report_type: str = context.get("report_type", "Report")
        sections: list[dict] = []

        current_title: str | None = None
        current_body: list[str] = []

        def flush() -> None:
            if current_title is None:
                return
            body = "\n".join(current_body)
            fields = self._fields_from_text(body)
            section_id = re.sub(r"[^a-z0-9]+", "_", current_title.lower()).strip("_")
            sections.append(
                {
                    "id": section_id or "section",
                    "title": current_title,
                    "required_fields": fields,
                    "style_guide": "Write short, factual sentences in the active voice.",
                }
            )

        for line in text.splitlines():
            heading = re.match(r"^(#{1,3})\s+(.*)$", line.strip())
            if heading:
                flush()
                level = len(heading.group(1))
                title = heading.group(2).strip()
                # A level-1 heading is the report title, not a section.
                if level == 1:
                    current_title = None
                    current_body = []
                    continue
                current_title = title
                current_body = []
            elif current_title is not None:
                current_body.append(line)
        flush()

        return {
            "report_type": report_type,
            "version": 1,
            "sections": sections,
            "notes": "The mock provider induced this blueprint. A human must review it.",
        }

    def _fields_from_text(self, body: str) -> list[dict]:
        """Return the field specifications that a section text implies."""
        lower = body.lower()
        fields: list[dict] = []
        seen: set[str] = set()
        for entry in _KEYWORD_FIELDS:
            if entry["trigger"] in lower and entry["name"] not in seen:
                seen.add(entry["name"])
                fields.append(
                    {
                        "name": entry["name"],
                        "description": entry.get("description", ""),
                        "type": entry.get("type", "string"),
                        "source_doc_type": entry.get("source_doc_type", ""),
                        "required": True,
                        "computed": entry.get("computed", False),
                        "computation": entry.get("computation"),
                        "extraction_hint": entry.get("extraction_hint", ""),
                    }
                )
        return fields

    # -- extraction ----------------------------------------------------------

    def _extract(self, context: dict) -> dict:
        """Find one value in one document.

        The method returns the value and the source text.
        The source text gives provenance for a reviewer.
        """
        document_text: str = context.get("document_text", "")
        field: dict = context.get("field", {})
        hint: str = field.get("extraction_hint", "")
        ftype: str = field.get("type", "string")

        if not hint:
            return {"found": False}

        index = document_text.lower().find(hint.lower())
        if index == -1:
            return {"found": False}

        line_end = document_text.find("\n", index)
        if line_end == -1:
            line_end = len(document_text)
        segment = document_text[index:line_end].strip()

        after = segment.split(":", 1)[1].strip() if ":" in segment else segment

        if ftype == "number":
            match = re.search(r"[-+]?\$?[\d,]+(?:\.\d+)?", after)
            if not match:
                return {"found": False}
            raw = match.group().replace("$", "").replace(",", "")
            value: Any = float(raw)
        else:
            value = after

        return {
            "found": True,
            "value": value,
            "source_quote": segment,
            "char_start": index,
            "char_end": line_end,
            "confidence": 0.95,
        }

    # -- composition ---------------------------------------------------------

    def _compose(self, context: dict) -> str:
        """Write the narrative for one section.

        The method builds short sentences from the facts.
        It flags a required field when the value is absent.
        """
        facts: list[dict] = context.get("facts", [])
        missing: list[str] = context.get("missing", [])
        lines: list[str] = []

        for fact in facts:
            description = fact.get("description") or fact.get("name", "value")
            value = _format_value(fact.get("name", ""), fact.get("type", "string"), fact.get("value"))
            lines.append(f"The {description} is {value}.")

        for name in missing:
            lines.append(
                f"[GAP] The value for {name} is not available. "
                f"Provide the source document, then run the report again."
            )

        if not lines:
            lines.append("No data is available for this section.")
        return " ".join(lines)


def _format_value(name: str, ftype: str, value: Any) -> str:
    """Return a display string for a value."""
    if value is None:
        return "not available"
    if ftype == "number":
        if name in {"dscr"}:
            return f"{float(value):.2f}x"
        if name in {"ltv"}:
            return f"{float(value) * 100:.1f}%"
        return f"${float(value):,.0f}"
    return str(value)
