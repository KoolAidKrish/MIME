"""Run one config over the frozen cases.

Usage:

    python eval/run_eval.py baseline_naive
    python eval/run_eval.py structured --overwrite
    python eval/run_eval.py all

The script writes output to eval/outputs/<config>/<case>.json.
It skips a case that already has output, unless you pass --overwrite.
"""
from __future__ import annotations

import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from configs import CONFIGS  # noqa: E402
from harness import OUTPUTS_DIR, run_config_into  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    """Run the eval for one config or for all configs."""
    parser = argparse.ArgumentParser(description="Run the credit memo eval")
    parser.add_argument("config", help="a config name, or 'all'")
    parser.add_argument("--overwrite", action="store_true", help="rerun cases that already have output")
    args = parser.parse_args(argv)

    if args.config == "all":
        names = list(CONFIGS.keys())
    elif args.config in CONFIGS:
        names = [args.config]
    else:
        print(f"Unknown config: {args.config}")
        print(f"Known configs: {', '.join(CONFIGS)}")
        return 1

    for name in names:
        config = CONFIGS[name]
        print(f"\nConfig: {name} - {config.description}")
        out_dir = os.path.join(OUTPUTS_DIR, name)
        try:
            run_config_into(config, out_dir, overwrite=args.overwrite)
        except Exception as error:  # noqa: BLE001
            # One config's failure must not abort the others.
            # A keyless Claude config fails here, and 'all' still runs the rest.
            print(f"  [skip] config {name} did not run: {error}")

    print("\nDone. Score the runs with: python eval/score.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
