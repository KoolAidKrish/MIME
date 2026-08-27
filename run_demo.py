"""A one-shot demo of the full pipeline.

The script runs both phases end to end with the mock provider.
It needs no API key and no network.
It prints each phase, so you can see the flow.

Run the script from the project root:

    python run_demo.py
"""
from __future__ import annotations

import os

from cmforge.capabilities import default_registry
from cmforge.induction import induce_blueprint
from cmforge.pdf import load_folder
from cmforge.pipeline import run
from cmforge.providers.registry import get_provider

HERE = os.path.dirname(os.path.abspath(__file__))
EXEMPLAR = os.path.join(HERE, "examples", "exemplar_memo.md")
DOCS = os.path.join(HERE, "examples", "sample_docs")
OUT = os.path.join(HERE, "output_memo.md")


def banner(text: str) -> None:
    """Print a section banner."""
    print("\n" + "=" * 68)
    print(text)
    print("=" * 68)


def main() -> None:
    """Run the demo."""
    provider = get_provider("mock")
    registry = default_registry()

    # Phase 1: compile. Learn the report format from one example.
    banner("PHASE 1 - INDUCTION (compile the example into a blueprint)")
    with open(EXEMPLAR, "r", encoding="utf-8") as handle:
        exemplar_text = handle.read()
    blueprint = induce_blueprint(exemplar_text, provider, report_type="Credit Memo")
    print(f"Report type: {blueprint.report_type}")
    for section in blueprint.sections:
        field_names = ", ".join(f.name for f in section.required_fields)
        print(f"  Section '{section.title}': {field_names}")
    print("\nNote: a human reviews this blueprint before the runtime uses it.")

    # Phase 2: run. Build a report from the documents.
    banner("PHASE 2 - RUNTIME (build a report from the documents)")
    documents = load_folder(DOCS)
    print("Provided documents:")
    for document in documents:
        print(f"  {document.name} (type: {document.doc_type})")

    result = run(blueprint, documents, provider, registry)

    banner("GAP REPORT (what the system cannot do for this run)")
    if result.gaps.satisfiable:
        print("The system can produce a complete report.")
    else:
        for gap in result.gaps.capability_gaps:
            print(f"  Capability gap: {gap}")
        for gap in result.gaps.data_gaps:
            print(f"  Data gap: {gap}")
        for gap in result.gaps.computation_gaps:
            print(f"  Computation gap: {gap}")

    banner("OUTPUT REPORT")
    markdown = result.to_markdown()
    print(markdown)

    with open(OUT, "w", encoding="utf-8") as handle:
        handle.write(markdown)
    print(f"\nWrote the report to {OUT}.")


if __name__ == "__main__":
    main()
