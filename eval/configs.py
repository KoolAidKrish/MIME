"""The config registry.

A config is one architecture variant under test.
The registry maps a config name to a factory that builds its provider.
The runner and the trials harness both read this registry.
This keeps the set of variants in one place.

A config also states whether it is deterministic.
A deterministic config gives the same output every run.
Repeated trials of a deterministic config show zero variance.
Variance appears when a config uses a real language model, such as Claude.
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from typing import Callable

# Make the mime package importable when a script runs from the project root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mime.providers.base import ProviderAdapter  # noqa: E402
from mime.providers.mock import MockProvider  # noqa: E402

from naive_provider import NaiveProvider  # noqa: E402


@dataclass
class Config:
    """One architecture variant under test."""

    name: str
    build: Callable[[], ProviderAdapter]
    deterministic: bool
    description: str


def _build_claude() -> ProviderAdapter:
    """Build the Claude provider on demand.

    The import is local, so the offline configs do not need the anthropic package.
    """
    from mime.providers.claude import ClaudeProvider

    return ClaudeProvider()


CONFIGS: dict[str, Config] = {
    "baseline_naive": Config(
        name="baseline_naive",
        build=NaiveProvider,
        deterministic=True,
        description="Loose-keyword skim. The dumb floor. Runs offline.",
    ),
    "structured": Config(
        name="structured",
        build=MockProvider,
        deterministic=True,
        description="Anchored-hint extraction plus compute-in-code. Runs offline.",
    ),
    # The Claude config needs the anthropic package and the ANTHROPIC_API_KEY variable.
    # It is stochastic, so repeated trials show real variance.
    "structured_claude": Config(
        name="structured_claude",
        build=_build_claude,
        deterministic=False,
        description="The structured pipeline on Claude. Needs an API key.",
    ),
}
