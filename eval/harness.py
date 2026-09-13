"""The shared run harness.

The harness runs one config over the frozen cases.
It drives the pipeline stages directly, so it can capture the fact ledger.
The ledger holds the extracted values that the scorer needs.
The harness writes one JSON file per case.
It skips a case that already has output, unless the caller asks to overwrite.
It wraps each case in a try block, so one failure does not lose the earlier work.
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback

# Put the project root on the path before importing mime.
# This keeps the harness self-sufficient, whatever imports it first.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mime.capabilities import default_registry
from mime.computation import check_policy, compute_derived
from mime.extraction import extract_facts
from mime.feasibility import assess
from mime.models import Blueprint
from mime.pdf import load_folder
from mime.providers.base import ProviderAdapter

from configs import Config

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
BLUEPRINT_PATH = os.path.join(EVAL_DIR, "blueprint_eval.json")
CASES_DIR = os.path.join(EVAL_DIR, "cases")
OUTPUTS_DIR = os.path.join(EVAL_DIR, "outputs")

# The pattern pulls a quoted document type out of a gap message.
_QUOTED = re.compile(r"'([^']+)'")


def load_blueprint() -> Blueprint:
    """Return the frozen eval blueprint."""
    with open(BLUEPRINT_PATH, "r", encoding="utf-8") as handle:
        return Blueprint.model_validate(json.load(handle))


def list_cases() -> list[str]:
    """Return the sorted list of case names."""
    return sorted(
        name
        for name in os.listdir(CASES_DIR)
        if os.path.isdir(os.path.join(CASES_DIR, name))
    )


def _gap_types(messages: list[str]) -> list[str]:
    """Return the document types named in a list of gap messages."""
    types: list[str] = []
    for message in messages:
        match = _QUOTED.search(message)
        if match:
            types.append(match.group(1))
    return types


def run_one_case(
    provider: ProviderAdapter,
    blueprint: Blueprint,
    case_name: str,
) -> dict:
    """Run the pipeline stages for one case and return the output record."""
    registry = default_registry()
    documents = load_folder(os.path.join(CASES_DIR, case_name))

    gaps = assess(blueprint, documents, registry)
    ledger = extract_facts(blueprint, documents, provider)
    compute_derived(blueprint, ledger)
    policy_results = check_policy(ledger)
    # The scorer reads the ledger and the gaps, not the narrative.
    # So the eval skips composition on purpose. This saves a model call per case,
    # which matters when a config uses a paid model such as Claude.

    facts = {
        fact.field_name: {
            "value": fact.value,
            "source_doc": fact.source_doc,
            "source_quote": fact.source_quote,
            "computed": fact.computed,
        }
        for fact in ledger.facts
    }

    return {
        "case": case_name,
        "facts": facts,
        "detected_data_gap_types": _gap_types(gaps.data_gaps),
        "detected_capability_gap_types": _gap_types(gaps.capability_gaps),
        "policy": [r.model_dump() for r in policy_results],
    }


def run_config_into(config: Config, out_dir: str, overwrite: bool = False) -> None:
    """Run a config over every case and write the output into a directory."""
    # Build the provider first. A failed build must not leave an empty directory.
    provider = config.build()
    os.makedirs(out_dir, exist_ok=True)
    blueprint = load_blueprint()

    for case_name in list_cases():
        out_path = os.path.join(out_dir, f"{case_name}.json")
        if os.path.exists(out_path) and not overwrite:
            print(f"  skip {case_name} (output exists)")
            continue
        try:
            record = run_one_case(provider, blueprint, case_name)
            record["config"] = config.name
            with open(out_path, "w", encoding="utf-8") as handle:
                json.dump(record, handle, indent=2)
            print(f"  ran  {case_name}")
        except Exception as error:  # noqa: BLE001
            # One case failure must not lose the calls already spent on the batch.
            # Print a concise reason. Set MIME_EVAL_TRACE=1 for the full traceback.
            print(f"  FAIL {case_name}: {type(error).__name__}: {error}")
            if os.environ.get("MIME_EVAL_TRACE") == "1":
                traceback.print_exc()
