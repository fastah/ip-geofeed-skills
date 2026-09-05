# Copyright 2026 Fastah Inc.
"""Markdown projection of an already serialized and validated analysis IR."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import Analysis, RowKind
from .schema import validate_document


def _cell(value: object) -> str:
    return html.escape(str(value)).replace("|", "\\|").replace("\n", " ")


ROW_STATE_GLOSSARY = (
    "Row states: `valid_unresolved` — parsed successfully and carries a declared "
    "location; external geocode checks are recorded separately when run. "
    "`valid_do_not_geolocate` — the publisher declared that this prefix must not "
    "be geolocated. `invalid` — the row failed validation and is retained as "
    "authored. `not_applicable` — comment or blank line."
)

RELATIONSHIP_PREVIEW_LIMIT = 50

_ENDING_LABELS = {"\r\n": "CRLF", "\n": "LF", "\r": "CR"}


def source_format_summary(analysis: Analysis) -> str:
    """One-line normalization report derived from per-row IR fields."""
    data_rows = [row for row in analysis.rows if row.kind == RowKind.DATA]
    endings: Counter[str] = Counter(row.line_ending for row in data_rows if row.line_ending)
    field_counts: Counter[int] = Counter(
        row.parsed_field_count for row in data_rows if row.parsed_field_count is not None
    )
    ignored_rows = sum(1 for row in data_rows if row.ignored_fields)
    if not endings:
        ending_text = "line endings not recorded"
    elif len(endings) == 1:
        ending_text = f"{_ENDING_LABELS.get(next(iter(endings)), 'mixed')} line endings"
    else:
        ending_text = "mixed line endings"
    if len(field_counts) == 1:
        field_text = f"all rows parse {next(iter(field_counts))} fields"
    else:
        field_text = ", ".join(
            f"{count} rows with {fields} fields" for fields, count in sorted(field_counts.items())
        )
    ignored_text = (
        f"We skipped {ignored_rows} rows that carry extension fields"
        if ignored_rows
        else "We didn't skip any extension fields"
    )
    return (
        f"Your feed: {len(data_rows):,} data rows, {ending_text}, {field_text}. "
        f"The fifth field is the postal code — leaving it blank is totally fine, "
        f"not an error. {ignored_text}."
    )


def render_markdown_document(document: Any) -> str:
    validate_document(document)
    analysis = Analysis.model_validate(document)
    stats = analysis.statistics
    lines = [
        "# Geofeed quality analysis",
        "",
        f"- Analysis: `{analysis.analysis_id}`",
        f"- Source: `{_cell(analysis.source.display_name)}`",
        f"- SHA-256: `{analysis.source.sha256}`",
        f"- Schema: `{analysis.schema_version}`",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "|---|---:|",
        f"| Physical lines | {stats.physical_lines} |",
        f"| Data rows | {stats.data_rows} |",
        f"| Valid rows | {stats.valid_rows} |",
        f"| Invalid rows | {stats.invalid_rows} |",
        f"| Do not geolocate | {stats.do_not_geolocate_rows} |",
        f"| Unresolved | {stats.unresolved_rows} |",
        f"| Findings | {len(analysis.findings)} |",
        f"| Relationships | {len(analysis.relationships)} |",
        "",
        ROW_STATE_GLOSSARY,
        "",
        source_format_summary(analysis),
        "",
        "## Findings",
        "",
        "| ID | Category | Severity | Rule | Targets | Message |",
        "|---|---|---|---|---|---|",
    ]
    if analysis.findings:
        lines.extend(
            "| "
            + " | ".join(
                [
                    _cell(finding.id),
                    _cell(finding.category.value),
                    _cell(finding.severity.value),
                    _cell(finding.rule_id),
                    _cell(", ".join(finding.target_ids)),
                    _cell(finding.message),
                ]
            )
            + " |"
            for finding in analysis.findings
        )
    else:
        lines.append("| — | — | — | — | — | No findings |")
    lines.extend(
        [
            "",
            "## Prefix relationships",
            "",
        ]
    )
    if analysis.relationships:
        by_priority = {
            "conflicting_geolocation": 0,
            "duplicate": 1,
            "equal": 1,
            "parent": 2,
            "carved_child": 2,
            "overlap": 2,
        }
        ordered = sorted(
            analysis.relationships,
            key=lambda relation: (
                by_priority.get(relation.type.value, 3),
                not relation.geolocation_conflict,
                relation.id,
            ),
        )
        preview = ordered[:RELATIONSHIP_PREVIEW_LIMIT]
        type_counts = Counter(relation.type.value for relation in analysis.relationships)
        count_text = ", ".join(
            f"{relation_type}: {count}" for relation_type, count in sorted(type_counts.items())
        )
        lines.append(f"Relationships by type: {count_text}.")
        lines.append("")
        lines.append("| ID | Type | Source | Target | Conflict |")
        lines.append("|---|---|---|---|---|")
        lines.extend(
            "| "
            + " | ".join(
                [
                    relation.id,
                    relation.type.value,
                    f"{relation.source_row_id} `{relation.source_prefix}`",
                    f"{relation.target_row_id} `{relation.target_prefix}`",
                    "yes" if relation.geolocation_conflict else "no",
                ]
            )
            + " |"
            for relation in preview
        )
        if len(ordered) > RELATIONSHIP_PREVIEW_LIMIT:
            lines.append("")
            lines.append(
                f"Showing {RELATIONSHIP_PREVIEW_LIMIT} of {len(analysis.relationships)} "
                "relationships, prioritized for review (conflicts first). The HTML "
                "dashboard and Analysis JSON contain the complete set."
            )
    else:
        lines.append("| ID | Type | Source | Target | Conflict |")
        lines.append("|---|---|---|---|---|")
        lines.append("| — | — | — | — | — |")
    lines.extend(
        [
            "",
            "## Correction proposals and decisions",
            "",
            "Proposals are not applied unless an explicit approval artifact "
            "records an `approve` decision.",
            "",
            "| Proposal | Row / field | Old value | Proposed value | Confidence | Decision |",
            "|---|---|---|---|---|---|",
        ]
    )
    decisions = {
        decision.proposal_id: decision.action.value
        for approval in analysis.corrections.approvals
        for decision in approval.decisions
    }
    if analysis.corrections.proposals:
        lines.extend(
            "| "
            + " | ".join(
                [
                    proposal.id,
                    f"{proposal.row_id} / {proposal.field}",
                    _cell(proposal.old_value),
                    _cell(proposal.proposed_value),
                    proposal.confidence.value,
                    decisions.get(proposal.id, "pending"),
                ]
            )
            + " |"
            for proposal in analysis.corrections.proposals
        )
    else:
        lines.append("| — | — | — | — | — | No proposals |")
    return "\n".join(lines) + "\n"


def render_markdown_file(path: Path | str) -> str:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return render_markdown_document(document)
