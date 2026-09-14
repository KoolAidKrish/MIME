# MIME — Make It More Efficient

MIME turns a set of source documents into a standard report.
It learns a report format from one example. It then applies that format to new documents.
The prototype targets credit memos. The design fits any standard report.
The name is a backronym: Make It More Efficient.

## Result in one line

MIME builds the report at **O(corpus + N x ledger)** input cost, against **O(N x corpus)** for a full-context baseline.
On a 50-document, 15-section memo that is about **14x fewer input tokens** and about **11x lower cost** than a cached baseline.
Quality holds: on the live model, field extraction accuracy is 97%, numeric error is bounded by extraction error, and 0 of 77 numbers in the prose were untraceable to the ledger.
The efficiency numbers are deterministic and reproducible. The quality numbers cover both the live model and the offline test double.

## What the prototype shows

The prototype demonstrates five ideas:

1. **A compiler and a runtime.** The system learns a report format once. It runs that format many times.
2. **Extract once.** The system reads each document one time. Later steps use a compact fact store.
3. **A provider abstraction.** The system runs on a mock model or on Claude. A customer with no Claude agreement selects a different provider.
4. **Gap detection.** The system reports what it cannot do before it starts. It fails loudly and early.
5. **Code for numbers, model for prose.** Code computes every ratio and checks every policy. The model writes only the narrative.

## Efficiency

MIME reads each document once, then builds the report from a compact fact ledger.
A naive approach re-reads every document for each section.
This changes how the cost grows with the report.

### The baselines

Two baselines, on purpose. Pin them down, or a multiple means nothing.

- **naive_full** — re-send every source document in full as context for each of the N sections. One frontier model. No cache.
- **naive_cached** — the same, but cache the shared corpus across sections. This is the competent baseline. MIME must beat it to matter.

The `baseline_naive` config in the eval is a different thing. It tests fact quality, not cost. Do not confuse the two.

### The scaling law

This is the real claim. A single multiple is one point. The curve is the argument.

- Naive cost grows as **O(N x corpus)**. It re-reads the whole corpus for every section.
- MIME cost grows as **O(corpus + N x ledger)**. It reads the corpus once, then a small ledger per section.

Modeled at a 50-document, 15-section memo. The corpus is 500,000 tokens. The ledger is 2,000 tokens per section. Prices are dated 2026-09-13.

| Approach | Input tokens | Cost per memo |
| --- | --- | --- |
| naive_full | 7,503,000 | $37.70 |
| naive_cached | 7,503,000 | $6.83 |
| MIME | 537,500 | $0.60 |

MIME uses about **14x fewer input tokens**. It costs about **11x less than the cached baseline**, and about 63x less than the uncached one.

Cost against section count (chart: [`eval/reports/scaling.svg`](eval/reports/scaling.svg)):

| Sections | naive_full $ | naive_cached $ | MIME $ |
| --- | --- | --- | --- |
| 1 | 2.51 | 3.14 | 0.28 |
| 5 | 12.57 | 4.19 | 0.37 |
| 15 | 37.70 | 6.83 | 0.60 |
| 30 | 75.41 | 10.78 | 0.94 |
| 50 | 125.67 | 16.05 | 1.40 |

Naive cost climbs with every section. MIME stays nearly flat.

### Why cost falls faster than tokens

The token count drops about 14x. The cost drops more, so the two multiples are not the same number.
MIME runs the extraction pass on a cheap model, Haiku instead of Opus, and in a batch at half price.
The same tokens therefore cost less. That gap is the reason, and it is worth stating before a reviewer asks.

### Induction amortizes to near zero

The blueprint compiles once per report format. Here that costs about $0.04.
That one-time cost spreads across every run. At 1 run the memo costs $0.64. At 100 runs it costs $0.60.
Runtime dominates, so the amortization is small. This is an honest note, not a headline.

### Method

Token counts use a fixed estimate of 4 characters per token.
The scaling shape does not depend on this estimate. Only the absolute cost does.
Run `python eval/cost_model.py` to reproduce every number here.
Run `python eval/cost_model.py --exact` to count with the Anthropic tokenizer instead.

## Quality: what the evaluation found

The eval harness in `eval/` puts numbers on the pipeline over 11 frozen cases.
It compares three configs: a dumb baseline, the structured pipeline on the mock, and the structured pipeline on the live Claude model.
The mock is a deterministic test double for development. `structured_claude` is the real result.
See `eval/README.md` for the method.

| Metric | baseline_naive | structured (mock) | structured_claude (live) |
| --- | --- | --- | --- |
| Field extraction accuracy | 94.4% | 95.8% | **97.2%** |
| Computation accuracy | 94.4% | 88.9% | 88.9% |
| Gap detection exact match | 100% | 100% | 100% |
| Gap precision / recall (false negatives) | 100% / 100% (0) | 100% / 100% (0) | 100% / 100% (0) |
| Field-level silent proceeds | 1 | 3 | 2 |
| Unsourced-assertion rate (prose) | 1/78 | 1/75 | **0/77** |
| Final-correct-but-facts-wrong | 1 | 0 | 0 |
| Fabricated values | 0 | 0 | 0 |
| Ungrounded facts (ledger) | 0 | 0 | 0 |

The live model leads on field extraction, 97.2% against 95.8% for the mock, because it reads a reworded label the exact-hint mock misses.
Across 5 independent live trials, the field accuracy was identical every run (97.2%, standard deviation 0).
Extraction of labeled fields is stable, so there is no run-to-run variance to test, and the harness reports no p-value.

**Numeric error is bounded by extraction error.**
MIME computes every ratio in code, in `mime/computation.py`. The model never asserts a financial figure.
So a number can be wrong only when its input was extracted wrong. A ratio cannot drift on its own.
MIME fabricated 0 figures across the eval set. This turns a design choice into a measurable guarantee.

The conclusions:

1. **The fact-level check is the real difference.**
   On the adversarial case, the baseline built a correct-looking DSCR from two wrong inputs.
   The structured pipeline did not. The count of "final correct but facts wrong" is 1 against 0.
   A check of the final number alone would have passed the baseline.

2. **Top-line accuracy alone does not separate the two.**
   The field and computation scores are close. On computation the baseline even scores higher.
   A single accuracy number would hide the difference that matters. You need the fact-level check.

3. **The offline mock is brittle by design.**
   The structured mock uses exact-label matching. A reworded label makes it miss.
   That is why it scores lower on computation. This is a limit of the test double, not the architecture.
   A real model reads a reworded label with ease.

4. **A real parser gap exists.**
   Both configs fail the `$4.2M` short form. The parser reads 4.2, not 4,200,000.
   The eval records this as a number, not a claim.

5. **Gap detection is reliable.**
   Both configs report the exact set of missing documents on every case.

6. **Deterministic configs have no variance.**
   Three trials of each mock config gave a standard deviation of zero.
   The harness refused to print a significance value for identical repeats.
   Real variance needs a model provider.

7. **The live run caught a bug the offline path could not.**
   A first run against Claude failed with an API error.
   The structured-output schema used `additionalProperties: true`, which the API rejects.
   The mock never checked the schema, so it never saw the bug.
   This is the reason to test on the real provider, not only on a stand-in.
   The bug is now fixed and the live run is complete. On the live model, field extraction reached 97.2% and 0 of 77 prose numbers were untraceable.

8. **Gap detection is document-level, not field-level.**
   Over 11 cases, feasibility flags every missing document. Precision and recall are both 100%, with zero false negatives.
   A present-but-empty document is a different failure. The document is there, so feasibility flags nothing, yet the field stays missing.
   MIME shows 3 such field-level silent proceeds. They surface later as a missing-field warning, not in the upfront check.
   This is the same failure class as a truncated response that parses to a plausible wrong number. It is worth stating, not hiding.

9. **The composed prose stays sourced.**
   The assertion tracer reads every number in the memo prose and checks it against the ledger.
   On the mock, 74 of 75 numbers trace to a ledger value; the one exception is the case07 $4.2M display artifact, not an invented figure.
   On the live model, all 77 numbers trace to the ledger. The unsourced-assertion rate is 0.
   The tracer is the instrument that would catch an invented figure, and on this eval it found none.

Reproduce these numbers with `python eval/score.py` and `python eval/assertion_tracer.py`.

## Install

The demo needs only Pydantic:

```bash
pip install "pydantic>=2.0"
```

Two packages are optional.
Install `pymupdf` to read PDF files.
Install `anthropic` to use the Claude provider.

## Run the demo

The demo runs the full pipeline offline with the mock provider:

```bash
python run_demo.py
```

The demo prints each phase. It writes the report to `output_memo.md`.

## Run the two phases from the command line

The `induce` command builds a blueprint from an example report:

```bash
python -m mime.cli induce examples/exemplar_memo.md --out blueprint.json
```

The `run` command builds a report from a document folder:

```bash
python -m mime.cli run blueprint.json examples/sample_docs --out report.md
```

Add `--provider claude` to either command to use the Anthropic API.
The Claude provider needs the `anthropic` package and the `ANTHROPIC_API_KEY` environment variable.

## The two phases

The system splits work into a design-time phase and a run-time phase.

**Phase 1 — Induction (compile).**
The induction engine reads one example report.
It produces a blueprint. The blueprint lists the sections, the fields, and the source document types.
A human reviews the blueprint before the runtime uses it.
This phase runs once per report format.

**Phase 2 — Runtime (execute).**
The runtime checks feasibility, extracts facts, computes ratios, and writes the report.
This phase runs once per document set.

```
EXAMPLE REPORT --> [Induction] --> BLUEPRINT (human reviews)
                                       |
DOCUMENT SET --> [Extraction] --> Fact Ledger
                                       |
                                       v
                                 [Composition] --> DRAFT REPORT + GAP REPORT
```

## The pipeline stages

| Stage | File | Job |
| --- | --- | --- |
| Induction | `mime/induction.py` | Turn an example report into a blueprint. |
| Feasibility | `mime/feasibility.py` | Report the gaps before any model work. |
| Extraction | `mime/extraction.py` | Pull each value from its source document. |
| Computation | `mime/computation.py` | Compute ratios and check policy in code. |
| Composition | `mime/composition.py` | Write each section from the fact ledger. |
| Render | `mime/render.py` | Turn the result into Markdown. |
| Pipeline | `mime/pipeline.py` | Run the runtime stages in order. |

## How to extend the system

You extend the system in three ways.
Each way changes data or one small module. The engine stays the same.

**Add a new report format.**
Write an example report. Run the `induce` command. Review the blueprint.
You write no code for a new format.

**Add a new document type.**
Add the type to the capability registry in `mime/capabilities.py`.
Teach the extractor how to find the values.
The feasibility check then stops reporting a capability gap for that type.

**Add a new provider.**
Write a class that fills the `ProviderAdapter` interface in `mime/providers/base.py`.
Report the capabilities that the provider supports.
Add the provider to the factory in `mime/providers/registry.py`.

## The provider abstraction

The provider interface stays small. It has two core methods.
The `complete` method returns free text.
The `extract_structured` method returns data that matches a schema.

Each provider reports its capabilities.
The engine checks a capability before it uses the matching feature.
The engine falls back to a simpler method when the capability is absent.
This gives a floor and a ceiling.
The system runs on any provider. The system runs best on a provider with the strong features.

## What the prototype does not do

The prototype keeps a narrow scope. A production system needs more work:

- The mock provider uses simple keyword rules. It is a test double, not a model.
- The system does not resolve the same entity across documents.
- The system does not handle a scanned PDF with poor text. That case needs OCR.
- The blueprint review is manual. The prototype does not ship a review interface.
- The policy rules are small and fixed. A real system loads rules from credit policy.

## Layout

```
MIME/
  mime/
    models.py          Typed data models
    capabilities.py    The list of supported skills
    contextpack.py     The prompt context helpers
    providers/
      base.py          The provider interface
      mock.py          The offline test double
      claude.py        The Anthropic adapter
      registry.py      The provider factory
    induction.py       Compile an example into a blueprint
    feasibility.py     Report the gaps
    extraction.py      Pull facts from documents
    computation.py     Compute ratios and check policy
    composition.py     Write the report sections
    render.py          Render Markdown
    pdf.py             Load documents
    pipeline.py        Run the runtime stages
    cli.py             The command line interface
  examples/
    exemplar_memo.md   An example report
    sample_docs/       Sample source documents
  run_demo.py          A one-shot demo
```
