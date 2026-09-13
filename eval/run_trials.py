"""Run N independent trials of one or more configs.

Usage:

    python eval/run_trials.py baseline_naive structured --trials 3
    python eval/run_trials.py structured_claude --trials 5

The script writes each trial to eval/outputs/trials/<config>/run<N>/.
It skips a trial that already has output, so a stopped run resumes.

A deterministic config gives the same output on every trial.
Its variance is zero, so a single trial already tells you its score.
Run many trials only when a config uses a real model, such as Claude.
The harness still records the trials, so the aggregate step works for both.
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

TRIALS_DIR = os.path.join(OUTPUTS_DIR, "trials")


def main(argv: list[str] | None = None) -> int:
    """Run repeated trials of the named configs."""
    parser = argparse.ArgumentParser(description="Run repeated eval trials")
    parser.add_argument("configs", nargs="+", help="one or more config names")
    parser.add_argument("--trials", type=int, default=3, help="number of trials per config")
    parser.add_argument("--overwrite", action="store_true", help="rerun trials that already have output")
    args = parser.parse_args(argv)

    for name in args.configs:
        if name not in CONFIGS:
            print(f"Unknown config: {name}. Known: {', '.join(CONFIGS)}")
            return 1
        config = CONFIGS[name]
        if config.deterministic and args.trials > 1:
            print(f"Note: {name} is deterministic. Every trial gives the same output.")
        for trial in range(1, args.trials + 1):
            out_dir = os.path.join(TRIALS_DIR, name, f"run{trial}")
            print(f"\nConfig {name}, trial {trial}/{args.trials}")
            run_config_into(config, out_dir, overwrite=args.overwrite)

    print("\nDone. Aggregate with: python eval/aggregate_trials.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
