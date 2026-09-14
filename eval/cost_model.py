"""The cost and scaling model.

This script produces the efficiency half of the MIME result.
It reports input tokens and cost for a full-context baseline and for MIME.
It shows the scaling curve, because the curve is the real architecture claim.
It shows induction amortization across many runs of one blueprint.

The token count is deterministic. It uses a fixed characters-per-token estimate.
Pass --exact to count with the Anthropic tokenizer instead, when a key is present.
The scaling relationship is exact regardless of the token estimate.

Two baselines appear on purpose:
- naive_full: re-send every document in full for each section, one frontier model, no cache.
- naive_cached: the same, but cache the shared corpus prefix across sections.
The cached baseline is the competent comparator. MIME must beat that one to matter.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from mime.induction import induce_blueprint  # noqa: E402
from mime.extraction import extract_facts  # noqa: E402
from mime.pdf import load_folder  # noqa: E402
from mime.providers.mock import MockProvider  # noqa: E402

# --- token estimate ---------------------------------------------------------

# English text runs about four characters per token.
# This is an estimate, not the exact Anthropic tokenizer.
# The scaling shape does not depend on this constant. Only the absolute cost does.
CHARS_PER_TOKEN = 4.0


def est_tokens(text: str) -> int:
    """Return an estimated token count for a text."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


def exact_tokens(text: str) -> int:
    """Return the exact token count from the Anthropic tokenizer.

    This needs the anthropic package and an API key.
    """
    import anthropic

    client = anthropic.Anthropic()
    result = client.messages.count_tokens(
        model="claude-opus-5",
        messages=[{"role": "user", "content": text}],
    )
    return result.input_tokens


# --- price table ------------------------------------------------------------

# Prices are US dollars per one million tokens. Update the date when they change.
PRICES_DATE = "2026-09-13"
PRICE = {
    "opus": {"in": 5.0, "out": 25.0},   # Claude Opus 5
    "haiku": {"in": 1.0, "out": 5.0},   # Claude Haiku 4.5
}
CACHE_READ = 0.1    # a cached read costs about one tenth of the input price
CACHE_WRITE = 1.25  # writing the cache costs about 1.25 times the input price
BATCH = 0.5         # the Batch API costs half price


def _usd(tokens: float, price_per_mtok: float) -> float:
    """Return the dollar cost for a token count at a per-million price."""
    return tokens * price_per_mtok / 1_000_000.0


# --- the model --------------------------------------------------------------
#
# C   = corpus size in tokens (all source documents)
# N   = number of report sections
# L   = ledger tokens the composer reads per section (the compact facts)
# The composer sees the whole ledger each section here, which is the pessimistic case for MIME.


def model_naive_full(C: int, N: int, out_sec: int, instr: int = 200) -> dict:
    """Model the full-context baseline with no cache."""
    in_tokens = N * (C + instr)
    out_tokens = N * out_sec
    cost = _usd(in_tokens, PRICE["opus"]["in"]) + _usd(out_tokens, PRICE["opus"]["out"])
    return {"input_tokens": in_tokens, "cost": cost}


def model_naive_cached(C: int, N: int, out_sec: int, instr: int = 200) -> dict:
    """Model the full-context baseline that caches the shared corpus."""
    # The corpus is identical each section, so cache it: write once, read after.
    effective_in = C * CACHE_WRITE + (N - 1) * C * CACHE_READ + N * instr
    out_tokens = N * out_sec
    cost = _usd(effective_in, PRICE["opus"]["in"]) + _usd(out_tokens, PRICE["opus"]["out"])
    # The raw (uncached-equivalent) token volume is still N*(C+instr); report that too.
    return {"input_tokens": N * (C + instr), "cost": cost}


def model_mime(
    C: int,
    N: int,
    L: int,
    out_sec: int,
    ledger_out: int,
    template: int = 500,
    extraction_reads: float = 1.0,
    cascade: bool = True,
    batch: bool = True,
    cache: bool = True,
) -> dict:
    """Model the MIME pipeline.

    Extraction reads the corpus once on a cheap model, optionally in a batch.
    Composition reads the compact ledger per section on the strong model.
    """
    # Extraction: corpus in, ledger out, on the cheap model, optionally batched.
    ext_model = "haiku" if cascade else "opus"
    ext_mult = BATCH if batch else 1.0
    ext_in_tokens = C * extraction_reads
    ext_cost = (
        _usd(ext_in_tokens, PRICE[ext_model]["in"]) * ext_mult
        + _usd(ledger_out, PRICE[ext_model]["out"]) * ext_mult
    )

    # Composition: template plus the ledger per section, on the strong model.
    if cache:
        comp_in_effective = template * CACHE_WRITE + (N - 1) * template * CACHE_READ + N * L
    else:
        comp_in_effective = N * template + N * L
    comp_cost = _usd(comp_in_effective, PRICE["opus"]["in"]) + _usd(N * out_sec, PRICE["opus"]["out"])

    # Report the raw input token volume that MIME actually feeds the models.
    input_tokens = int(ext_in_tokens + N * (template + L))
    return {
        "input_tokens": input_tokens,
        "cost": ext_cost + comp_cost,
        "extraction_cost": ext_cost,
        "composition_cost": comp_cost,
    }


def induction_cost(exemplar_tokens: int, blueprint_out: int = 1500) -> float:
    """Return the one-time cost to compile a blueprint from an exemplar."""
    # Induction runs once per report format on the strong model.
    return _usd(exemplar_tokens, PRICE["opus"]["in"]) + _usd(blueprint_out, PRICE["opus"]["out"])


# --- measurement on the real examples ---------------------------------------


def measure_examples(counter) -> dict:
    """Measure the corpus and ledger tokens on examples/sample_docs."""
    docs_dir = os.path.join(_ROOT, "examples", "sample_docs")
    exemplar_path = os.path.join(_ROOT, "examples", "exemplar_memo.md")
    provider = MockProvider()

    with open(exemplar_path, "r", encoding="utf-8") as handle:
        exemplar_text = handle.read()
    blueprint = induce_blueprint(exemplar_text, provider, report_type="Credit Memo")
    documents = load_folder(docs_dir)

    corpus_tokens = sum(counter(doc.text) for doc in documents)
    ledger = extract_facts(blueprint, documents, provider)
    ledger_tokens = counter(json.dumps([f.model_dump() for f in ledger.facts]))

    return {
        "corpus_tokens": corpus_tokens,
        "ledger_tokens": ledger_tokens,
        "sections": len(blueprint.sections),
        "exemplar_tokens": counter(exemplar_text),
        "documents": len(documents),
    }


# --- reports ----------------------------------------------------------------


def scaling_rows(C: int, L: int, out_sec: int, ledger_out: int, section_counts: list[int]) -> list[dict]:
    """Return one row per section count for the scaling curve."""
    rows = []
    for n in section_counts:
        full = model_naive_full(C, n, out_sec)
        cached = model_naive_cached(C, n, out_sec)
        mime = model_mime(C, n, L, out_sec, ledger_out)
        rows.append(
            {
                "sections": n,
                "naive_full_cost": full["cost"],
                "naive_cached_cost": cached["cost"],
                "mime_cost": mime["cost"],
                "mime_input_tokens": mime["input_tokens"],
                "naive_full_input_tokens": full["input_tokens"],
            }
        )
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    """Write the scaling rows to a CSV file."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict], path: str) -> None:
    """Write the scaling rows as a Markdown table."""
    lines = [
        "| Sections | naive_full $ | naive_cached $ | MIME $ | MIME input tokens | naive_full input tokens |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['sections']} | {r['naive_full_cost']:.2f} | {r['naive_cached_cost']:.2f} "
            f"| {r['mime_cost']:.2f} | {r['mime_input_tokens']:,} | {r['naive_full_input_tokens']:,} |"
        )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def write_svg(rows: list[dict], path: str) -> None:
    """Write a simple line chart of cost against section count.

    The chart uses no external library. It plots three lines on a linear scale.
    """
    W, H = 640, 380
    ml, mr, mt, mb = 70, 150, 30, 50
    plot_w, plot_h = W - ml - mr, H - mt - mb
    xs = [r["sections"] for r in rows]
    series = {
        "naive_full": ("#c0392b", [r["naive_full_cost"] for r in rows]),
        "naive_cached": ("#e67e22", [r["naive_cached_cost"] for r in rows]),
        "MIME": ("#2e7d32", [r["mime_cost"] for r in rows]),
    }
    x_min, x_max = min(xs), max(xs)
    y_max = max(max(v) for _, v in series.values()) or 1.0

    def px(x: float) -> float:
        return ml + (x - x_min) / (x_max - x_min) * plot_w if x_max > x_min else ml

    def py(y: float) -> float:
        return mt + plot_h - (y / y_max) * plot_h

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="sans-serif" font-size="12">',
        f'<rect x="0" y="0" width="{W}" height="{H}" fill="white"/>',
        f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{mt+plot_h}" stroke="#333"/>',
        f'<line x1="{ml}" y1="{mt+plot_h}" x2="{ml+plot_w}" y2="{mt+plot_h}" stroke="#333"/>',
        f'<text x="{ml+plot_w/2}" y="{H-12}" text-anchor="middle">Report sections (N)</text>',
        f'<text x="18" y="{mt+plot_h/2}" text-anchor="middle" transform="rotate(-90 18 {mt+plot_h/2})">Cost per memo (USD)</text>',
        f'<text x="{ml}" y="{mt+plot_h+18}" text-anchor="middle">{x_min}</text>',
        f'<text x="{ml+plot_w}" y="{mt+plot_h+18}" text-anchor="middle">{x_max}</text>',
        f'<text x="{ml-8}" y="{mt+5}" text-anchor="end">{y_max:.0f}</text>',
        f'<text x="{ml-8}" y="{mt+plot_h}" text-anchor="end">0</text>',
    ]
    ly = mt + 10
    for name, (color, ys) in series.items():
        pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        parts.append(f'<rect x="{ml+plot_w+16}" y="{ly-9}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{ml+plot_w+32}" y="{ly+1}">{name}</text>')
        ly += 22
    parts.append("</svg>")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(parts))


# --- main -------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MIME cost and scaling model")
    parser.add_argument("--corpus-tokens", type=int, default=500_000, help="modeled corpus size C")
    parser.add_argument("--sections", type=int, default=15, help="modeled section count N")
    parser.add_argument("--ledger-tokens", type=int, default=2000, help="ledger tokens per section L")
    parser.add_argument("--out-sec", type=int, default=500, help="output tokens per section")
    parser.add_argument("--exact", action="store_true", help="count tokens with the Anthropic tokenizer")
    args = parser.parse_args(argv)

    counter = exact_tokens if args.exact else est_tokens
    method = "Anthropic tokenizer (exact)" if args.exact else f"estimate ({CHARS_PER_TOKEN} chars/token)"

    print(f"Token count method: {method}")
    print(f"Price table dated {PRICES_DATE}: "
          f"Opus 5 ${PRICE['opus']['in']}/{PRICE['opus']['out']}, "
          f"Haiku 4.5 ${PRICE['haiku']['in']}/{PRICE['haiku']['out']} per MTok; "
          f"batch x{BATCH}, cache read x{CACHE_READ}, write x{CACHE_WRITE}.")

    # 1. Measured on the real examples.
    print("\n== Measured on examples/sample_docs ==")
    m = measure_examples(counter)
    print(f"  documents: {m['documents']}, corpus tokens: {m['corpus_tokens']}, "
          f"ledger tokens: {m['ledger_tokens']}, sections: {m['sections']}")

    # 2. Modeled at realistic scale.
    C, N, L, out_sec = args.corpus_tokens, args.sections, args.ledger_tokens, args.out_sec
    ledger_out = L  # the extraction output is about one full ledger
    print(f"\n== Modeled at scale: C={C:,} tokens, N={N} sections, L={L} ledger tokens/section ==")
    full = model_naive_full(C, N, out_sec)
    cached = model_naive_cached(C, N, out_sec)
    mime = model_mime(C, N, L, out_sec, ledger_out)

    print(f"  naive_full   : {full['input_tokens']:>12,} input tokens   ${full['cost']:.2f}")
    print(f"  naive_cached : {cached['input_tokens']:>12,} input tokens   ${cached['cost']:.2f}  (corpus cached)")
    print(f"  MIME         : {mime['input_tokens']:>12,} input tokens   ${mime['cost']:.2f}  "
          f"(extract ${mime['extraction_cost']:.2f} + compose ${mime['composition_cost']:.2f})")

    tok_ratio = full["input_tokens"] / mime["input_tokens"]
    cost_ratio_full = full["cost"] / mime["cost"]
    cost_ratio_cached = cached["cost"] / mime["cost"]
    print(f"\n  Input-token reduction vs naive_full : {tok_ratio:.1f}x")
    print(f"  Cost reduction vs naive_full         : {cost_ratio_full:.1f}x")
    print(f"  Cost reduction vs naive_cached       : {cost_ratio_cached:.1f}x  (the fair baseline)")
    print(f"  Gap between token and cost multiples comes from the cheap extraction model "
          f"(Haiku vs Opus) and the batch discount.")

    # 3. Scaling curve.
    section_counts = [1, 3, 5, 10, 15, 20, 30, 50]
    rows = scaling_rows(C, L, out_sec, ledger_out, section_counts)
    reports = os.path.join(_HERE, "reports")
    os.makedirs(reports, exist_ok=True)
    write_csv(rows, os.path.join(reports, "scaling.csv"))
    write_markdown(rows, os.path.join(reports, "scaling.md"))
    write_svg(rows, os.path.join(reports, "scaling.svg"))
    print(f"\n== Scaling curve written to eval/reports/ (csv, md, svg) ==")
    print("  naive cost grows with N (re-reads the corpus each section).")
    print("  MIME cost stays nearly flat (reads the corpus once, then a small ledger per section).")

    # 4. Induction amortization.
    ind = induction_cost(m["exemplar_tokens"])
    print(f"\n== Induction amortization (blueprint compiles once, cost ${ind:.4f}) ==")
    for runs in (1, 10, 100):
        per_memo = (ind + runs * mime["cost"]) / runs
        print(f"  {runs:>3} runs: ${per_memo:.2f} per memo")
    return 0


if __name__ == "__main__":
    sys.exit(main())
