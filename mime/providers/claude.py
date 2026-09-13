"""The Claude provider.

This adapter calls the Anthropic API.
It shows how a real provider fills the same interface as the mock.
It uses a model cascade. A cheap model extracts. A strong model writes.
It uses structured outputs for extraction.
It uses prompt caching for the stable system text.

The import of the ``anthropic`` package is optional.
The mock demo runs without this package.
This adapter raises a clear error when the package or key is absent.
"""
from __future__ import annotations

import json
from typing import Any

from .base import Capability, ProviderAdapter

# The system text is stable across requests, so it caches well.
_SYSTEM = (
    "You extract facts and write sections for a standard financial report. "
    "You use only the data in the prompt. "
    "You never invent numbers. "
    "You return values that match the requested schema."
)

# The cascade maps a pipeline stage to a model.
# Extraction is high volume, so it uses a cheap model.
# Composition needs judgment, so it uses a strong model.
_MODEL_BY_TASK = {
    "induction": "claude-sonnet-5",
    "extraction": "claude-haiku-4-5",
    "composition": "claude-opus-5",
}
_DEFAULT_MODEL = "claude-opus-5"


class ClaudeProvider(ProviderAdapter):
    """An adapter for the Anthropic API."""

    name = "claude"
    capabilities = {
        Capability.STRUCTURED_OUTPUT,
        Capability.CITATIONS,
        Capability.PROMPT_CACHE,
        Capability.BATCH,
        Capability.NATIVE_PDF,
    }

    def __init__(self) -> None:
        try:
            import anthropic
        except ImportError as error:
            raise RuntimeError(
                "The anthropic package is not installed. "
                "Run 'pip install anthropic' to use the Claude provider."
            ) from error
        # The client reads the API key from the environment.
        self._client = anthropic.Anthropic()

    def _model_for(self, task: str) -> str:
        """Return the model for a pipeline stage."""
        return _MODEL_BY_TASK.get(task, _DEFAULT_MODEL)

    def complete(self, prompt: str, *, task: str, max_tokens: int = 1024) -> str:
        """Return free text from the model."""
        response = self._client.messages.create(
            model=self._model_for(task),
            max_tokens=max_tokens,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
        )
        parts = [block.text for block in response.content if block.type == "text"]
        return "".join(parts)

    def extract_structured(self, prompt: str, schema: dict, *, task: str) -> dict:
        """Return structured data that matches a schema.

        The method uses the structured output feature of the API.
        Native citations do not combine with structured output.
        The schema therefore asks the model for a source quote field.
        This keeps provenance while it keeps a strict output shape.
        """
        response = self._client.messages.create(
            model=self._model_for(task),
            max_tokens=4096,
            system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        text = next((block.text for block in response.content if block.type == "text"), "{}")
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        return data
