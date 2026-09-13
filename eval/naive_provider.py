"""The naive baseline provider.

This provider is the floor. It is the dumb version that every variant beats or ties.
It skims for a loose keyword and grabs the first number on that line.
It does not use the exact extraction hint.
A qualifier prefix, such as 'Prior Year' or 'Other', fools it.

The provider is a deterministic caricature of a dumb single-call model.
It lets the eval run offline and produce numbers with no API key.
The fair language-model baseline runs with '--provider claude' and a single-call config.
"""
from __future__ import annotations

import re
from typing import Any

from mime.providers.mock import MockProvider


class NaiveProvider(MockProvider):
    """A loose-keyword skim extractor. It is the baseline floor."""

    name = "naive"

    def _extract(self, context: dict) -> dict:
        """Find one value by a loose keyword skim.

        The method reuses the parent extractor for text fields.
        For a number field, it grabs the first number on the first line
        that contains the last word of the hint.
        """
        field: dict = context.get("field", {})
        ftype: str = field.get("type", "string")
        if ftype != "number":
            # Text fields are not the focus. Reuse the anchored parent extractor.
            return super()._extract(context)

        text: str = context.get("document_text", "")
        hint: str = field.get("extraction_hint", "")
        key = hint.split()[-1].lower() if hint else ""

        for line in text.splitlines():
            if key and key in line.lower():
                match = re.search(r"[-+]?\$?[\d,]+(?:\.\d+)?", line)
                if match:
                    raw = match.group().replace("$", "").replace(",", "")
                    start = text.find(line)
                    return {
                        "found": True,
                        "value": float(raw),
                        "source_quote": line.strip(),
                        "char_start": start,
                        "char_end": start + len(line),
                        "confidence": 0.5,
                    }

        # Fallback: grab the first number anywhere in the document.
        # The fallback prints a visible warning, so a bad grab is not silent.
        match = re.search(r"[-+]?\$?[\d,]+(?:\.\d+)?", text)
        if match:
            print(
                f"[warn] naive fallback: no line matched key '{key}'; "
                f"the provider grabbed the first number in the document"
            )
            raw = match.group().replace("$", "").replace(",", "")
            return {
                "found": True,
                "value": float(raw),
                "source_quote": "(fallback: first number in document)",
                "confidence": 0.2,
            }
        return {"found": False}
