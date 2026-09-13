"""The provider factory.

The factory returns a provider by name.
The engine asks for a provider and does not know the concrete class.
This is where data residency and vendor choice live.
A customer with no Claude agreement selects a different provider here.
"""
from __future__ import annotations

from .base import ProviderAdapter
from .mock import MockProvider


def get_provider(name: str = "mock") -> ProviderAdapter:
    """Return a provider adapter by name.

    The mock provider runs offline.
    The Claude provider needs the anthropic package and an API key.
    """
    key = name.lower()
    if key == "mock":
        return MockProvider()
    if key == "claude":
        # The import is local, so the mock demo does not need the package.
        from .claude import ClaudeProvider

        return ClaudeProvider()
    raise ValueError(f"Unknown provider: {name}")
