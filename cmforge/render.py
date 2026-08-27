"""Report rendering.

The renderer turns the memo and the gap report into Markdown.
Markdown is easy to read and easy to convert later.
A real system also renders a DOCX file or a PDF file.
"""
from __future__ import annotations

from .models import GapReport, Memo


def render_markdown(memo: Memo, gaps: GapReport) -> str:
    """Return the memo and the gap report as Markdown."""
    lines: list[str] = []
    lines.append(f"# {memo.report_type}")
    lines.append("")

    # The gap report goes first, so a reviewer sees the limits at once.
    lines.append("## Feasibility and gaps")
    if gaps.satisfiable:
        lines.append("The system can produce a complete report from the provided documents.")
    else:
        for gap in gaps.capability_gaps:
            lines.append(f"- Capability gap: {gap}")
        for gap in gaps.data_gaps:
            lines.append(f"- Data gap: {gap}")
        for gap in gaps.computation_gaps:
            lines.append(f"- Computation gap: {gap}")
    lines.append("")

    # The policy results give a quick pass or fail view.
    if memo.policy_results:
        lines.append("## Policy checks")
        for result in memo.policy_results:
            mark = "PASS" if result.passed else "FAIL"
            lines.append(f"- [{mark}] {result.rule} - {result.detail}")
        lines.append("")

    # Each section shows the narrative and the citations.
    for section in memo.sections:
        lines.append(f"## {section.title}")
        lines.append(section.narrative)
        if section.citations:
            lines.append("")
            lines.append("_Sources:_")
            for citation in section.citations:
                lines.append(f"- {citation}")
        lines.append("")

    if memo.warnings:
        lines.append("## Warnings")
        for warning in memo.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    return "\n".join(lines)
