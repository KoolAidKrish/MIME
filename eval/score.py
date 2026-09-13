"""Score every config against the frozen answer key.

The scorer reads eval/outputs/<config>/<case>.json.
It compares each output against eval/answer_key.json.
It prints one comparison table for all configs.

The scorer reports both raw error and normalized error for the ratios.
It warns loudly when a config does not cover the full case set.
It checks that no eval document duplicates the induction exemplar.

The headline metric is 'final-correct-but-facts-wrong'.
That metric counts a right-looking ratio built from wrong inputs.
A scorer that checks only the final number would miss this.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from harness import CASES_DIR, OUTPUTS_DIR, load_blueprint  # noqa: E402

ANSWER_KEY_PATH = os.path.join(_HERE, "answer_key.json")
EXEMPLAR_PATH = os.path.join(_HERE, "..", "examples", "exemplar_memo.md")


def _num_match(a, b, rel: float) -> bool:
    """Return True when two numbers match within a relative tolerance."""
    try:
        a = float(a)
        b = float(b)
    except (TypeError, ValueError):
        return str(a).strip().casefold() == str(b).strip().casefold()
    if b == 0:
        return abs(a) < 1e-9
    return abs(a - b) / abs(b) <= rel


def _ratio_match(a, b, abs_tol: float) -> bool:
    """Return True when two ratios match within an absolute tolerance."""
    try:
        return abs(float(a) - float(b)) <= abs_tol
    except (TypeError, ValueError):
        return False


def _normalize(text: str) -> str:
    """Return text without commas, dollar signs, or spaces, in lower case."""
    return text.replace(",", "").replace("$", "").replace(" ", "").casefold()


def _grounded(value, source_quote: str) -> bool:
    """Return True when the value text appears in the source text.

    The check normalizes both sides the same way, so spacing does not matter.
    """
    needle = str(value)
    if isinstance(value, float) and value.is_integer():
        needle = str(int(value))
    return _normalize(needle) in _normalize(source_quote)


def _hash(path: str) -> str:
    """Return the SHA-256 hash of a file."""
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def check_no_exemplar_collision() -> None:
    """Assert that no eval document duplicates the induction exemplar.

    A duplicate would let a system 'know' an eval case in advance.
    That would inflate every downstream number.
    """
    if not os.path.exists(EXEMPLAR_PATH):
        return
    exemplar_hash = _hash(EXEMPLAR_PATH)
    for doc_path in glob.glob(os.path.join(CASES_DIR, "*", "*.txt")):
        assert _hash(doc_path) != exemplar_hash, (
            f"Collision: eval document {doc_path} equals the induction exemplar."
        )


def score_config(config_name: str, answer_key: dict, blueprint, out_dir: str | None = None) -> dict:
    """Return the metrics for one config.

    Pass ``out_dir`` to score a specific directory, such as one trial run.
    """
    tol = answer_key["tolerance"]
    ratio_inputs = answer_key["ratio_inputs"]
    cases = answer_key["cases"]

    out_dir = out_dir or os.path.join(OUTPUTS_DIR, config_name)
    records = {}
    for path in glob.glob(os.path.join(out_dir, "*.json")):
        with open(path, "r", encoding="utf-8") as handle:
            record = json.load(handle)
        records[record["case"]] = record

    # Warn loudly on an incomplete or mismatched case set.
    missing = set(cases) - set(records)
    extra = set(records) - set(cases)
    if missing:
        print(f"  [WARN] {config_name}: missing outputs for {sorted(missing)}")
    if extra:
        print(f"  [WARN] {config_name}: extra outputs not in the key: {sorted(extra)}")

    field_correct = field_total = 0
    comp_correct = comp_total = 0
    ratio_raw_errors: list[float] = []
    ratio_norm_errors: list[float] = []
    gap_match = gap_total = 0
    final_correct_facts_wrong = 0
    fabrications = 0
    ungrounded = 0

    for case_name, truth in cases.items():
        record = records.get(case_name)
        if record is None:
            continue
        facts = record.get("facts", {})

        # Field extraction accuracy over the extractable fields.
        for name, truth_value in truth["fields"].items():
            field_total += 1
            got = facts.get(name, {}).get("value")
            if isinstance(truth_value, str):
                ok = got is not None and str(got).strip().casefold() == truth_value.strip().casefold()
            else:
                ok = got is not None and _num_match(got, truth_value, tol["number_rel"])
            if ok:
                field_correct += 1

        # Grounding check over non-computed facts.
        for name, fact in facts.items():
            if fact.get("computed"):
                continue
            if not _grounded(fact.get("value"), fact.get("source_quote", "")):
                ungrounded += 1

        # Computation accuracy plus raw and normalized error.
        for name, truth_value in truth["computed"].items():
            comp_total += 1
            got = facts.get(name, {}).get("value")
            if got is not None and _ratio_match(got, truth_value, tol["ratio_abs"]):
                comp_correct += 1
            if got is not None:
                ratio_raw_errors.append(abs(float(got) - float(truth_value)))
                if truth_value:
                    ratio_norm_errors.append(abs(float(got) - float(truth_value)) / abs(float(truth_value)))

        # Fabrication check for values that should be absent.
        for name in truth["expected_absent_computed"]:
            if name in facts:
                fabrications += 1

        # Gap detection exact match.
        gap_total += 1
        if set(record.get("detected_data_gap_types", [])) == set(truth["expected_data_gaps"]):
            gap_match += 1

        # The adversarial metric: a right-looking ratio built from wrong inputs.
        for ratio_name, inputs in ratio_inputs.items():
            truth_ratio = truth["computed"].get(ratio_name)
            got_ratio = facts.get(ratio_name, {}).get("value")
            if truth_ratio is None or got_ratio is None:
                continue
            if not _ratio_match(got_ratio, truth_ratio, tol["ratio_abs"]):
                continue
            # The ratio matches. Now check the inputs.
            inputs_wrong = False
            for input_name in inputs:
                input_truth = truth["fields"].get(input_name)
                if input_truth is None:
                    continue
                got_input = facts.get(input_name, {}).get("value")
                if got_input is None or not _num_match(got_input, input_truth, tol["number_rel"]):
                    inputs_wrong = True
            if inputs_wrong:
                final_correct_facts_wrong += 1

    return {
        "field_accuracy": (field_correct, field_total),
        "computation_accuracy": (comp_correct, comp_total),
        "ratio_raw_error_mean": sum(ratio_raw_errors) / len(ratio_raw_errors) if ratio_raw_errors else 0.0,
        "ratio_norm_error_mean": sum(ratio_norm_errors) / len(ratio_norm_errors) if ratio_norm_errors else 0.0,
        "gap_exact_match": (gap_match, gap_total),
        "final_correct_but_facts_wrong": final_correct_facts_wrong,
        "fabrications": fabrications,
        "ungrounded_facts": ungrounded,
    }


def _pct(pair: tuple[int, int]) -> str:
    """Return a correct/total pair as a percent string."""
    correct, total = pair
    if total == 0:
        return "n/a"
    return f"{100.0 * correct / total:5.1f}% ({correct}/{total})"


def main() -> int:
    """Score every config that has output and print the table."""
    check_no_exemplar_collision()

    with open(ANSWER_KEY_PATH, "r", encoding="utf-8") as handle:
        answer_key = json.load(handle)
    blueprint = load_blueprint()

    if not os.path.isdir(OUTPUTS_DIR):
        print("No outputs found. Run: python eval/run_eval.py all")
        return 1

    config_names = []
    for name in sorted(os.listdir(OUTPUTS_DIR)):
        path = os.path.join(OUTPUTS_DIR, name)
        # 'trials' is the trials root, not a config. Skip it.
        if not os.path.isdir(path) or name == "trials":
            continue
        # Skip a directory with no case output, such as a config that could not run.
        if not glob.glob(os.path.join(path, "*.json")):
            print(f"  [skip] {name}: directory has no case output")
            continue
        config_names.append(name)
    if not config_names:
        print("No config outputs found. Run: python eval/run_eval.py all")
        return 1

    print("Scoring configs:", ", ".join(config_names))
    print()
    results = {name: score_config(name, answer_key, blueprint) for name in config_names}

    rows = [
        ("Field extraction accuracy", lambda r: _pct(r["field_accuracy"])),
        ("Computation accuracy", lambda r: _pct(r["computation_accuracy"])),
        ("Ratio raw error (mean)", lambda r: f"{r['ratio_raw_error_mean']:.4f}"),
        ("Ratio norm error (mean)", lambda r: f"{100 * r['ratio_norm_error_mean']:.2f}%"),
        ("Gap detection exact match", lambda r: _pct(r["gap_exact_match"])),
        ("Final-correct-but-facts-wrong", lambda r: str(r["final_correct_but_facts_wrong"])),
        ("Fabricated values", lambda r: str(r["fabrications"])),
        ("Ungrounded facts", lambda r: str(r["ungrounded_facts"])),
    ]

    label_w = max(len(label) for label, _ in rows) + 2
    col_w = max(18, max(len(n) for n in config_names) + 2)
    header = "Metric".ljust(label_w) + "".join(n.ljust(col_w) for n in config_names)
    print(header)
    print("-" * len(header))
    for label, fn in rows:
        line = label.ljust(label_w) + "".join(fn(results[n]).ljust(col_w) for n in config_names)
        print(line)

    print()
    print("Note: 'final-correct-but-facts-wrong' is the adversarial metric.")
    print("It counts a ratio that matches the answer key while an input fact is wrong.")
    print("A final-answer-only check would score those cases as correct.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
