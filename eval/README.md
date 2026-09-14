# Eval harness

This harness puts verifiable numbers on the credit memo pipeline.
It follows a fixed methodology. The methodology produces defensible numbers, not vibes.

## The method in one line

Freeze a small answer key before you score anything.
Then run a dumb baseline and the real pipeline against the same key with the same scorer.
Never trust one run.

## Import note

The harness lives inside the MIME project, next to the `mime` package.
It finds the package on its own. You do not set `PYTHONPATH`.
Run every command from the MIME project root:

```bash
python eval/run_eval.py all
python eval/score.py
```

## The frozen set

The set has 11 cases in `cases/`. A human wrote the answer key in `answer_key.json` from the documents.
The key came before any scoring. A failing case is data about the system. It is not a bug in the key.

Each case tests one thing:

| Case | Purpose |
| --- | --- |
| case01_clean | Happy path. Clean labels. |
| case02_missing_debt_schedule | A document is absent. The DSCR is not computable. |
| case03_distractor_revenue | A prior-year line sits before the real revenue. A skim grabs the wrong number. |
| case04_adversarial_canceling | Two extraction errors cancel in the ratio. The DSCR looks correct while both inputs are wrong. |
| case05_reworded_labels | The labels differ from the hints. The exact-hint extractor misses. |
| case06_missing_guarantor | A document is absent. One field is not extractable. |
| case07_format_M_suffix | A $4.2M short form breaks the number parser. |
| case08_clean_variant | A second happy path with different values. |
| case09_missing_appraisal | The appraisal is absent. The LTV is not computable. |
| case10_missing_two | Two documents are absent. The DSCR is not computable. |
| case11_present_but_empty | The debt schedule is present but empty. Feasibility flags nothing, yet the field is missing. |

`case04_adversarial_canceling` is the important one.
It is the case that separates a real verifier from a check of the final answer.

## The configs

A config is one architecture variant. The registry lives in `configs.py`.

| Config | What it is |
| --- | --- |
| baseline_naive | A loose-keyword skim. The dumb floor. It runs offline. |
| structured | Anchored-hint extraction plus compute-in-code. It runs offline. |
| structured_claude | The structured pipeline on Claude. It needs an API key. |

The offline `baseline_naive` provider is a deterministic caricature of a dumb single-call model.
It lets the harness run and produce numbers with no API key.
The fair language-model baseline uses `structured_claude` with a single-call variant.

## How to run

Run one config, or all of them:

```bash
python eval/run_eval.py baseline_naive
python eval/run_eval.py all --overwrite
```

Score every config that has output:

```bash
python eval/score.py
```

Run repeated trials, then aggregate:

```bash
python eval/run_trials.py baseline_naive structured --trials 3
python eval/aggregate_trials.py
```

The runner skips a case that already has output. Pass `--overwrite` to rerun it.
The runner wraps each case in a try block. One failure does not lose the earlier work.

## The metrics

The scorer reports these numbers per config:

- **Field extraction accuracy** — the fraction of extractable fields with the correct value.
- **Computation accuracy** — the fraction of ratios with the correct value.
- **Ratio raw error** and **ratio normalized error** — two views of the same ratio miss.
- **Gap detection exact match** — the fraction of cases where the detected gap set is exact.
- **Gap precision / recall** — over document types, with the false-negative count. A false negative is a missing document the check did not flag.
- **Field-level silent proceeds** — a required field ends up missing and no document gap explains it. Feasibility checks documents, not fields, so this class slips past it.
- **Final-correct-but-facts-wrong** — the headline. It counts a correct ratio built from wrong inputs.
- **Fabricated values** — a value the provider produced that should be absent.
- **Ungrounded facts** — a ledger value that does not appear in its source text.
- **Unsourced-assertion rate** — a number in the composed prose that does not trace to a ledger value. Measured by `assertion_tracer.py`.

## The result (offline, mock providers)

| Metric | baseline_naive | structured |
| --- | --- | --- |
| Field extraction accuracy | 94.4% (67/71) | 95.8% (68/71) |
| Computation accuracy | 94.4% (17/18) | 88.9% (16/18) |
| Ratio raw error (mean) | 0.0389 | 0.0412 |
| Ratio normalized error (mean) | 5.56% | 5.88% |
| Gap detection exact match | 100% (11/11) | 100% (11/11) |
| Gap precision / recall (false negatives) | 100% / 100% (0) | 100% / 100% (0) |
| Field-level silent proceeds | 1 | 3 |
| Unsourced-assertion rate (prose) | 1/78 | 1/75 |
| Final-correct-but-facts-wrong | 1 | 0 |
| Fabricated values | 0 | 0 |
| Ungrounded facts | 0 | 0 |

## How to read the result

The headline is the adversarial metric.
The structured pipeline never builds a correct-looking ratio from wrong inputs. The count is 0.
The naive baseline does so once. That is `case04`, the canceling-errors case.
A check of the final DSCR alone would score that case as correct. The fact-level check catches it.

The raw accuracy numbers are close. That is itself a finding.
Final-answer accuracy alone does not separate a sound pipeline from a fooled one.
You need the fact-level check.

The harness does not flatter the pipeline. Two honest negatives show this:

- The structured config scores lower on computation accuracy, 86.7% against 93.3%.
  The cause is `case05`. The mock uses exact-hint matching, so a reworded label makes it miss.
  This is a limit of the offline test double, not of the architecture.
  A real language model reads a reworded label with ease.
- Both configs fail `case07`. The number parser reads `$4.2M` as 4.2, not 4,200,000.
  This is a real parser limit. The eval records it as a number, not a claim.

## Variance and significance

The mock providers are deterministic. Every trial gives the same output. The variance is zero.
Repeated trials of a deterministic config do not add information.
The trials harness still records them, so the flow is ready for a stochastic provider.

Point the harness at `structured_claude` to get real variance.
A language model gives a different sample on each run.
Then the mean, the standard deviation, and the range become meaningful.

For a clean separation, the harness reports an exact one-sided p-value.
A clean separation means every sample of one config beats every sample of the other.
The exact p-value is `1 / C(n1 + n2, n1)`. See `stats.py`.
For 5 samples against 4, the value is `1 / C(9, 5)`, which is about 0.008.
The harness prints this p-value only when the samples vary. It never prints it for identical repeats.

## Files

```
eval/
  answer_key.json       Frozen ground truth, written before scoring
  blueprint_eval.json   Frozen, reviewed blueprint
  cases/                11 document sets
  configs.py            The config registry
  naive_provider.py     The dumb baseline provider
  harness.py            Runs one config over the cases, resumable
  run_eval.py           Run one config or all configs
  score.py              Score every config, warn on gaps, print the table
  run_trials.py         Run N trials per config
  aggregate_trials.py   Mean, stdev, min, max, and exact p-value
  stats.py              The exact separation p-value
  cost_model.py         Token and cost model, scaling curve, amortization
  assertion_tracer.py   Unsourced-assertion rate in the composed prose
  reports/              Generated scaling artifacts (csv, md, svg)
```
