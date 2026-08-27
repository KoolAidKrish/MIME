"""Document loading.

The loader reads a source file into a document reference.
It reads a PDF when the PyMuPDF package is present.
It reads a plain text file in every case.
The demo uses text files, so it runs with no extra package.

The loader infers the document type from the file name prefix.
A real system stores the type as metadata or classifies it with a model.
"""
from __future__ import annotations

import os

from .models import DocumentRef

# The prefix of a file name gives its document type in the demo.
# Example: 'financial_statements_2023.txt' has type 'financial_statements'.
_KNOWN_TYPES = [
    "loan_application",
    "financial_statements",
    "debt_schedule",
    "appraisal_report",
    "guarantor_financials",
    "environmental_report",
]


def infer_doc_type(file_name: str) -> str:
    """Return the document type from a file name."""
    base = os.path.basename(file_name).lower()
    for doc_type in _KNOWN_TYPES:
        if base.startswith(doc_type):
            return doc_type
    return "unknown"


def _read_pdf(path: str) -> str:
    """Return the text of a PDF file."""
    try:
        import fitz  # PyMuPDF
    except ImportError as error:
        raise RuntimeError(
            "The PyMuPDF package is not installed. "
            "Run 'pip install pymupdf' to read PDF files."
        ) from error
    parts: list[str] = []
    with fitz.open(path) as document:
        for page in document:
            parts.append(page.get_text())
    return "\n".join(parts)


def load_document(path: str, doc_type: str | None = None) -> DocumentRef:
    """Return a document reference for a file."""
    name = os.path.basename(path)
    kind = doc_type or infer_doc_type(name)
    if path.lower().endswith(".pdf"):
        text = _read_pdf(path)
    else:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    return DocumentRef(name=name, doc_type=kind, text=text, path=path)


def load_folder(folder: str) -> list[DocumentRef]:
    """Return a document reference for each file in a folder."""
    documents: list[DocumentRef] = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if os.path.isfile(path):
            documents.append(load_document(path))
    return documents
