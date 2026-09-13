"""Aggregate the repeated trials.

The script globs every trial directory for each config.
It scores each trial and collects a scalar metric per trial.
It reports the mean, the standard deviation, the minimum, and the maximum.
It never trusts a single run.

When two configs separate cleanly, the script prints the exact p-value.
A clean separation means every sample of one config beats every sample of the other.
The exact p-value is 1 / C(n1 + n2, n1). See stats.py.
"""
from __future__ import annotations

import glob
import json
import os
import statistics
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from harness import load_blueprint  # noqa: E402
from score import ANSWER_KEY_PATH, score_config  # noqa: E402
from stats import exact_separation_pvalue, ranges_separate  # noqa: E402

TRIALS_DIR = os.path.join(_HERE, "outputs", "trials")

# The primary scalar for aggregation is the field extraction accuracy percent.
def _field_accuracy_pct(metrics: dict) -> float:
    correct, total = metrics["field_accuracy"]
    return 100.0 * correct / total if total else 0.0


def main() -> int:
    """Aggregate every config under the trials directory."""
    if not os.path.isdir(TRIALS_DIR):
        print("No trials found. Run: python eval/run_trials.py <configs> --trials N")
        return 1

    with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as handle:
        answer_key = json.load(handle)
    blueprint = load_blueprint()

    config_names = sorted(
        name for name in os.listdir(TRIALS_DIR)
        if os.path.isdir(os.path.join(TRIALS_DIR, name))
    )
    if not config_names:
        print("No trial configs found.")
        return 1

    samples: dict[str, list[float]] = {}
    print("Metric: field extraction accuracy (%)\n")
    print("Config".ljust(22) + "n   mean    stdev   min     max")
    print("-" * 58)
    for name in config_names:
        run_dirs = sorted(glob.glob(os.path.join(TRIALS_DIR, name, "run*")))
        scores = []
        for run_dir in run_dirs:
            metrics = score_config(name, answer_key, blueprint, out_dir=run_dir)
            scores.append(_field_accuracy_pct(metrics))
        if not scores:
            continue
        samples[name] = scores
        mean = statistics.mean(scores)
        stdev = statistics.stdev(scores) if len(scores) > 1 else 0.0
        print(
            f"{name.ljust(22)}{len(scores):<4}{mean:<8.2f}{stdev:<8.2f}"
            f"{min(scores):<8.2f}{max(scores):<8.2f}"
        )

    # Report the exact significance level for any clean separation.
    # The p-value is a valid significance claim only when the samples vary.
    # Deterministic configs repeat one number, so their separation is trivial.
    names = list(samples)
    printed_header = False
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = samples[names[i]], samples[names[j]]
            if not ranges_separate(a, b):
                continue
            if not printed_header:
                print("\nClean separations:")
                printed_header = True
            winner = names[i] if statistics.mean(a) > statistics.mean(b) else names[j]
            a_varies = len(a) > 1 and statistics.pstdev(a) > 0
            b_varies = len(b) > 1 and statistics.pstdev(b) > 0
            if a_varies or b_varies:
                p = exact_separation_pvalue(len(a), len(b))
                print(f"  {names[i]} vs {names[j]}: winner={winner}, exact one-sided p={p:.4f}")
            else:
                print(
                    f"  {names[i]} vs {names[j]}: winner={winner} on every run, "
                    f"but both configs are deterministic (stdev 0)."
                )
                print(
                    "    The repeats are identical, not independent draws, so no p-value applies. "
                    "Run a stochastic provider (Claude) for a real significance test."
                )

    if not printed_header:
        print("\nNo clean separation between configs on this metric.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
