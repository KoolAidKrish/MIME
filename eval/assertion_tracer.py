"""The assertion tracer.

The tracer measures unsourced assertions in the composed memo prose.
It composes each case, then finds every number in the narrative.
It checks each number against the fact ledger.
A number that does not trace to a ledger value is an unsourced assertion.

This is the direct test of grounding in the output, not just in the ledger.
For the mock composer the rate is zero by construction, because the mock
writes only ledger values. The tracer becomes meaningful on a real model,
which can invent a figure. The tracer is the instrument that catches that.

Usage:

    python eval/assertion_tracer.py            # default config: structured (mock)
    python eval/assertion_tracer.py structured_claude
"""
from __future__ import annotations

import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_HERE, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from mime.composition import compose  # noqa: E402
from mime.computation import check_policy, compute_derived  # noqa: E402
from mime.extraction import extract_facts  # noqa: E402
from mime.pdf import load_folder  # noqa: E402

from configs import CONFIGS  # noqa: E402
from harness import CASES_DIR, list_cases, load_blueprint  # noqa: E402

# A number token: optional dollar sign, digits with commas, optional decimal,
# optional percent or times suffix. Examples: $4,200,000  1.50x  70.0%  1.25
_NUMBER = re.compile(r"\$?\d[\d,]*(?:\.\d+)?[%x]?")


def parse_number(token: str) -> float:
    """Return the numeric value of a prose number token.

    A percent becomes a fraction. A times suffix is dropped. Commas and dollars are dropped.
    """
    is_percent = token.endswith("%")
    core = token.rstrip("%x").replace("$", "").replace(",", "")
    value = float(core)
    if is_percent:
        value /= 100.0
    return value


def grounded_values(ledger) -> list[float]:
    """Return every numeric value in the ledger."""
    values: list[float] = []
    for fact in ledger.facts:
        try:
            values.append(float(fact.value))
        except (TypeError, ValueError):
            continue
    return values


def is_grounded(value: float, grounded: list[float]) -> bool:
    """Return True when a prose number matches a ledger value within tolerance."""
    for g in grounded:
        if abs(value - g) <= max(0.01, abs(g) * 0.005):
            return True
    return False


def trace_config(config_name: str) -> dict:
    """Compose every case and trace the numbers in the prose."""
    config = CONFIGS[config_name]
    provider = config.build()
    blueprint = load_blueprint()

    total = 0
    untraceable: list[dict] = []

    for case_name in list_cases():
        documents = load_folder(os.path.join(CASES_DIR, case_name))
        ledger = extract_facts(blueprint, documents, provider)
        compute_derived(blueprint, ledger)
        policy = check_policy(ledger)
        sections, _warnings = compose(blueprint, ledger, provider, policy)
        grounded = grounded_values(ledger)

        for section in sections:
            for sentence in re.split(r"(?<=[.!?])\s+", section.narrative):
                for token in _NUMBER.findall(sentence):
                    # Skip a bare token that is just punctuation noise.
                    if not any(ch.isdigit() for ch in token):
                        continue
                    total += 1
                    value = parse_number(token)
                    if not is_grounded(value, grounded):
                        untraceable.append(
                            {"case": case_name, "token": token, "sentence": sentence.strip()}
                        )

    return {"total": total, "untraceable": untraceable}


def main(argv: list[str] | None = None) -> int:
    config_name = argv[0] if argv else "structured"
    if config_name not in CONFIGS:
        print(f"Unknown config: {config_name}. Known: {', '.join(CONFIGS)}")
        return 1

    print(f"Assertion trace for config: {config_name}\n")
    result = trace_config(config_name)
    total = result["total"]
    bad = len(result["untraceable"])
    rate = (100.0 * bad / total) if total else 0.0

    print(f"Numeric assertions in composed prose: {total}")
    print(f"Untraceable to a ledger value:        {bad}")
    print(f"Unsourced-assertion rate:             {rate:.1f}%")
    print(f"\nResult: {bad} of {total} assertions untraceable.")

    if result["untraceable"]:
        print("\nUntraceable assertions:")
        for item in result["untraceable"]:
            print(f"  [{item['case']}] '{item['token']}' in: {item['sentence']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
