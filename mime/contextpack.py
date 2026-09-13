"""Context packing helpers.

The engine sends one text prompt to a provider.
The prompt carries structured data inside a tagged block.
A real language model reads the block as context.
The mock provider parses the block to work without a network.
This keeps the provider interface small and honest.
"""
from __future__ import annotations

import json
from typing import Any

_OPEN = "<CONTEXT_JSON>"
_CLOSE = "</CONTEXT_JSON>"


def pack_context(data: dict[str, Any]) -> str:
    """Return a tagged JSON block for a prompt."""
    return f"{_OPEN}\n{json.dumps(data, indent=2)}\n{_CLOSE}"


def unpack_context(prompt: str) -> dict[str, Any]:
    """Return the data from a tagged JSON block in a prompt.

    The function returns an empty dict when the prompt has no block.
    """
    start = prompt.find(_OPEN)
    end = prompt.find(_CLOSE)
    if start == -1 or end == -1:
        return {}
    body = prompt[start + len(_OPEN) : end].strip()
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}
