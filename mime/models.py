"""Typed data models for the pipeline.

The models use Pydantic. Pydantic checks each value against the schema.
The schema is the contract between each stage of the pipeline.
A wrong shape fails early and points to the exact field.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

FieldType = Literal["string", "number", "date", "boolean"]


class FieldSpec(BaseModel):
    """One data point that a report section needs.

    An empty ``source_doc_type`` means the engine computes the value.
    A computed value comes from other fields, not from a document.
    """

    name: str
    description: str = ""
    type: FieldType = "string"
    source_doc_type: str = ""
    required: bool = True
    computed: bool = False
    computation: Optional[str] = None
    extraction_hint: str = ""


class SectionSpec(BaseModel):
    """One section of the report."""

    id: str
    title: str
    required_fields: list[FieldSpec] = Field(default_factory=list)
    style_guide: str = ""


class Blueprint(BaseModel):
    """A machine-readable description of one report format.

    The induction engine builds the blueprint from an example report.
    A human checks the blueprint before the engine uses it.
    The blueprint is data. The engine that reads it is code.
    You add a new report format with a new blueprint, not new code.
    """

    report_type: str
    version: int = 1
    sections: list[SectionSpec] = Field(default_factory=list)
    notes: str = ""

    def all_fields(self) -> list[FieldSpec]:
        """Return every field from every section."""
        fields: list[FieldSpec] = []
        for section in self.sections:
            fields.extend(section.required_fields)
        return fields

    def required_doc_types(self) -> set[str]:
        """Return each document type that the report needs."""
        types: set[str] = set()
        for field in self.all_fields():
            if field.source_doc_type:
                types.add(field.source_doc_type)
        return types

    def required_computations(self) -> set[str]:
        """Return each computation that the report needs."""
        names: set[str] = set()
        for field in self.all_fields():
            if field.computed and field.computation:
                names.add(field.computation)
        return names


class DocumentRef(BaseModel):
    """One source document and its text."""

    name: str
    doc_type: str
    text: str
    path: str = ""


class Fact(BaseModel):
    """One extracted value with its source.

    The source fields give provenance. A reviewer uses provenance to check the value.
    """

    field_name: str
    value: Any = None
    source_doc: str = ""
    source_quote: str = ""
    char_start: int = -1
    char_end: int = -1
    confidence: float = 1.0
    computed: bool = False


class FactLedger(BaseModel):
    """The store of every extracted and computed value."""

    facts: list[Fact] = Field(default_factory=list)

    def add(self, fact: Fact) -> None:
        """Add one fact to the ledger."""
        self.facts.append(fact)

    def get(self, field_name: str) -> Optional[Fact]:
        """Return the fact for a field, or ``None`` when it is absent."""
        for fact in self.facts:
            if fact.field_name == field_name:
                return fact
        return None

    def has(self, field_name: str) -> bool:
        """Return ``True`` when the ledger holds a value for the field."""
        return self.get(field_name) is not None


class PolicyResult(BaseModel):
    """The outcome of one policy rule."""

    rule: str
    passed: bool
    detail: str = ""


class GapReport(BaseModel):
    """The result of the feasibility check.

    A data gap means the extractor exists but the document is absent.
    A capability gap means the system has no extractor for the document type.
    A computation gap means the system cannot compute a required value.
    """

    data_gaps: list[str] = Field(default_factory=list)
    capability_gaps: list[str] = Field(default_factory=list)
    computation_gaps: list[str] = Field(default_factory=list)

    @property
    def satisfiable(self) -> bool:
        """Return ``True`` when the system can produce a complete report."""
        return not (self.data_gaps or self.capability_gaps or self.computation_gaps)


class MemoSection(BaseModel):
    """One finished section of the output report."""

    id: str
    title: str
    narrative: str
    citations: list[str] = Field(default_factory=list)


class Memo(BaseModel):
    """The finished report."""

    report_type: str
    sections: list[MemoSection] = Field(default_factory=list)
    policy_results: list[PolicyResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
