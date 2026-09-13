"""The provider interface.

Every provider gives the engine two core methods.
The ``complete`` method returns free text.
The ``extract_structured`` method returns a value that matches a schema.
Each provider also reports its capabilities.
The engine keeps the interface small on purpose.
A small interface is easy to add a new provider to.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum


class Capability(str, Enum):
    """One optional feature that a provider may support.

    The engine checks a capability before it uses the matching feature.
    The engine falls back to a simpler method when the capability is absent.
    """

    STRUCTURED_OUTPUT = "structured_output"
    CITATIONS = "citations"
    PROMPT_CACHE = "prompt_cache"
    BATCH = "batch"
    NATIVE_PDF = "native_pdf"


class ProviderAdapter(ABC):
    """The base class for every provider adapter."""

    name: str = "base"
    capabilities: set[Capability] = set()

    def supports(self, capability: Capability) -> bool:
        """Return ``True`` when the provider supports the capability."""
        return capability in self.capabilities

    @abstractmethod
    def complete(self, prompt: str, *, task: str, max_tokens: int = 1024) -> str:
        """Return free text for a prompt.

        The ``task`` tag names the pipeline stage.
        A real adapter uses the tag to pick a model and a cache policy.
        """

    @abstractmethod
    def extract_structured(self, prompt: str, schema: dict, *, task: str) -> dict:
        """Return structured data that matches a JSON schema."""
