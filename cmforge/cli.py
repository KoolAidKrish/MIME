"""The command line interface.

The interface runs the two phases from the shell.
The 'induce' command builds a blueprint from an example report.
The 'run' command builds a report from a document folder.
"""
from __future__ import annotations

import argparse
import json
import sys

from .capabilities import default_registry
from .induction import induce_blueprint
from .models import Blueprint
from .pdf import load_folder
from .pipeline import run
from .providers.registry import get_provider


def _cmd_induce(args: argparse.Namespace) -> int:
    """Build a blueprint from an example report."""
    with open(args.exemplar, "r", encoding="utf-8") as handle:
        exemplar_text = handle.read()
    provider = get_provider(args.provider)
    blueprint = induce_blueprint(exemplar_text, provider, report_type=args.report_type)
    with open(args.out, "w", encoding="utf-8") as handle:
        handle.write(blueprint.model_dump_json(indent=2))
    print(f"Wrote blueprint to {args.out}.")
    print("Review the blueprint before you run a report.")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    """Build a report from a document folder."""
    with open(args.blueprint, "r", encoding="utf-8") as handle:
        blueprint = Blueprint.model_validate(json.load(handle))
    documents = load_folder(args.docs)
    provider = get_provider(args.provider)
    registry = default_registry()
    result = run(blueprint, documents, provider, registry)
    output = result.to_markdown()
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(output)
        print(f"Wrote report to {args.out}.")
    else:
        print(output)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the command line interface."""
    parser = argparse.ArgumentParser(prog="cmforge", description="Credit Memo Forge")
    parser.add_argument("--provider", default="mock", help="provider name: mock or claude")
    sub = parser.add_subparsers(dest="command", required=True)

    induce = sub.add_parser("induce", help="build a blueprint from an example report")
    induce.add_argument("exemplar", help="path to the example report")
    induce.add_argument("--out", default="blueprint.json", help="path for the blueprint")
    induce.add_argument("--report-type", default="Credit Memo", help="name of the report type")
    induce.set_defaults(func=_cmd_induce)

    run_cmd = sub.add_parser("run", help="build a report from a document folder")
    run_cmd.add_argument("blueprint", help="path to the blueprint")
    run_cmd.add_argument("docs", help="path to the document folder")
    run_cmd.add_argument("--out", default="", help="path for the report")
    run_cmd.set_defaults(func=_cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
