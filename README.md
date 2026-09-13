# MIME — Make It More Efficient

MIME turns a set of source documents into a standard report.
It learns a report format from one example. It then applies that format to new documents.
The prototype targets credit memos. The design fits any standard report.
The name is a backronym: Make It More Efficient.

## What the prototype shows

The prototype demonstrates five ideas:

1. **A compiler and a runtime.** The system learns a report format once. It runs that format many times.
2. **Extract once.** The system reads each document one time. Later steps use a compact fact store.
3. **A provider abstraction.** The system runs on a mock model or on Claude. A customer with no Claude agreement selects a different provider.
4. **Gap detection.** The system reports what it cannot do before it starts. It fails loudly and early.
5. **Code for numbers, model for prose.** Code computes every ratio and checks every policy. The model writes only the narrative.

## What the evaluation found

The eval harness in `eval/` puts numbers on the pipeline.
It compares a dumb baseline against the structured pipeline on 8 frozen cases.
See `eval/README.md` for the method.

Offline result, mock providers:

| Metric | baseline_naive | structured |
| --- | --- | --- |
| Field extraction accuracy | 92.6% | 94.4% |
| Computation accuracy | 93.3% | 86.7% |
| Gap detection exact match | 100% | 100% |
| Final-correct-but-facts-wrong | 1 | 0 |
| Fabricated values | 0 | 0 |
| Ungrounded facts | 0 | 0 |

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
   The bug is now fixed. The full Claude numbers are pending a clean run.

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
