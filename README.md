# MIME (Make it More Efficient)

MIME turns a set of source documents into a standard report.
It learns a report format from one example. It then applies that format to new documents.
The prototype targets credit memos. The design fits any standard report.

## What the prototype shows

The prototype demonstrates five ideas:

1. **A compiler and a runtime.** The system learns a report format once. It runs that format many times.
2. **Extract once.** The system reads each document one time. Later steps use a compact fact store.
3. **A provider abstraction.** The system runs on a mock model or on Claude. A customer with no Claude agreement selects a different provider.
4. **Gap detection.** The system reports what it cannot do before it starts. It fails loudly and early.
5. **Code for numbers, model for prose.** Code computes every ratio and checks every policy. The model writes only the narrative.

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
python -m cmforge.cli induce examples/exemplar_memo.md --out blueprint.json
```

The `run` command builds a report from a document folder:

```bash
python -m cmforge.cli run blueprint.json examples/sample_docs --out report.md
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
| Induction | `cmforge/induction.py` | Turn an example report into a blueprint. |
| Feasibility | `cmforge/feasibility.py` | Report the gaps before any model work. |
| Extraction | `cmforge/extraction.py` | Pull each value from its source document. |
| Computation | `cmforge/computation.py` | Compute ratios and check policy in code. |
| Composition | `cmforge/composition.py` | Write each section from the fact ledger. |
| Render | `cmforge/render.py` | Turn the result into Markdown. |
| Pipeline | `cmforge/pipeline.py` | Run the runtime stages in order. |

## How to extend the system

You extend the system in three ways.
Each way changes data or one small module. The engine stays the same.

**Add a new report format.**
Write an example report. Run the `induce` command. Review the blueprint.
You write no code for a new format.

**Add a new document type.**
Add the type to the capability registry in `cmforge/capabilities.py`.
Teach the extractor how to find the values.
The feasibility check then stops reporting a capability gap for that type.

**Add a new provider.**
Write a class that fills the `ProviderAdapter` interface in `cmforge/providers/base.py`.
Report the capabilities that the provider supports.
Add the provider to the factory in `cmforge/providers/registry.py`.

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
credit-memo-forge/
  cmforge/
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
