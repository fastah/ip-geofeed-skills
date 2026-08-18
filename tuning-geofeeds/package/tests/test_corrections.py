from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from geofeed_quality import MAX_DATA_ROWS, analyze_file
from geofeed_quality.cli import main
from geofeed_quality.corrections import (
    export_corrected_csv,
    materialize_corrected_bytes,
    propose_corrections,
    record_approval,
)
from geofeed_quality.errors import CorrectionError
from geofeed_quality.html_renderer import render_html_document
from geofeed_quality.mcp_exchange import (
    export_request_batches,
    export_request_exchange,
    import_response_batches,
    request_document,
)
from geofeed_quality.models import (
    Analysis,
    CorrectionAction,
    CorrectionApproval,
    CorrectionCategory,
    CorrectionConfidence,
    CorrectionPlan,
)
from geofeed_quality.renderer import render_markdown_document
from geofeed_quality.schema import (
    check_all_schemas,
    correction_approval_schema_text,
    correction_plan_schema_text,
    validate_correction_approval_document,
    validate_correction_plan_document,
    validate_document,
)

FIXTURES = Path(__file__).parent / "fixtures"
DECIDED_AT = datetime(2026, 8, 15, 12, 30, tzinfo=UTC)


def _feed(tmp_path: Path, content: bytes, name: str = "source.csv") -> Path:
    path = tmp_path / name
    path.write_bytes(content)
    os.utime(path, (1_700_000_000, 1_700_000_000))
    return path


def _proposed(path: Path) -> tuple[Analysis, CorrectionPlan]:
    return propose_corrections(analyze_file(path))


def _approve(plan: CorrectionPlan, *proposal_ids: str) -> CorrectionApproval:
    return record_approval(plan, "review-session-7", list(proposal_ids), [], DECIDED_AT)


def _fixture_response() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((FIXTURES / "mcp-response-v1.json").read_text(encoding="utf-8")),
    )


def test_proposals_are_deterministic_typed_and_do_not_mutate_authored_values(
    tmp_path: Path,
) -> None:
    source = _feed(tmp_path, b"8.8.8.0/24,us,us-ca,Mountain View,94043\n")
    base = analyze_file(source)
    proposed, plan = propose_corrections(base)

    assert base.corrections.proposals == []
    assert [item.category for item in proposed.corrections.proposals] == [
        CorrectionCategory.DETERMINISTIC_NORMALIZATION,
        CorrectionCategory.DETERMINISTIC_NORMALIZATION,
        CorrectionCategory.DEPRECATED_FIELD_REMOVAL,
    ]
    assert [item.confidence for item in proposed.corrections.proposals] == [
        CorrectionConfidence.DETERMINISTIC,
        CorrectionConfidence.DETERMINISTIC,
        CorrectionConfidence.DETERMINISTIC,
    ]
    assert [item.proposed_value for item in proposed.corrections.proposals] == ["US", "US-CA", ""]
    assert proposed.rows[0].raw_fields == ["8.8.8.0/24", "us", "us-ca", "Mountain View", "94043"]
    assert plan.proposals == proposed.corrections.proposals
    validate_document(proposed.model_dump(mode="json"))
    validate_correction_plan_document(plan.model_dump(mode="json"))
    assert propose_corrections(proposed) == (proposed, plan)


def test_approval_requires_explicit_unique_known_decisions_and_user_timestamp(
    tmp_path: Path,
) -> None:
    _, plan = _proposed(_feed(tmp_path, b"8.8.8.0/24,us,us-ca,City,\n"))
    first, second = [proposal.id for proposal in plan.proposals]

    with pytest.raises(CorrectionError, match="at least one explicit"):
        record_approval(plan, "reviewer", [], [], DECIDED_AT)
    with pytest.raises(CorrectionError, match="duplicate"):
        record_approval(plan, "reviewer", [first], [first], DECIDED_AT)
    with pytest.raises(CorrectionError, match="unknown"):
        record_approval(plan, "reviewer", ["proposal-0000000000000000"], [], DECIDED_AT)
    with pytest.raises(ValidationError, match="timezone"):
        record_approval(plan, "reviewer", [first], [], datetime(2026, 1, 1))

    approval = record_approval(plan, "reviewer", [first], [second], DECIDED_AT)
    assert [decision.action for decision in approval.decisions] == [
        CorrectionAction.APPROVE,
        CorrectionAction.REJECT,
    ]
    assert approval.decided_at == DECIDED_AT
    validate_correction_approval_document(approval.model_dump(mode="json"))


def test_export_preserves_order_comments_blanks_bom_utf8_columns_and_line_endings(
    tmp_path: Path,
) -> None:
    original = (
        b"\xef\xbb\xbf# heading\r\n"
        b"\r"
        + "8.8.8.0/24,us,us-ca,São Paulo,90210 # keep\n".encode()
        + "2606:4700::/48,gb,gb-eng,Café\r".encode()
        + b"# tail"
    )
    source = _feed(tmp_path, original)
    proposed, plan = _proposed(source)
    approval = _approve(plan, *(proposal.id for proposal in plan.proposals))
    output = tmp_path / "corrected.csv"
    finalized_path = tmp_path / "final-analysis.json"

    finalized, remaining = export_corrected_csv(proposed, approval, source, output, finalized_path)
    corrected = output.read_bytes()
    assert corrected.startswith(b"\xef\xbb\xbf# heading\r\n\r")
    assert corrected.endswith("2606:4700::/48,GB,GB-ENG,Café\r# tail".encode())
    assert "8.8.8.0/24,US,US-CA,São Paulo,# keep\n".encode() in corrected
    assert [row.line_ending for row in analyze_file(output).rows] == ["\r\n", "\r", "\n", "\r", ""]
    assert analyze_file(output).rows[3].parsed_field_count == 4
    assert "RFC8805.POSTAL_DEPRECATED" not in remaining
    assert finalized.statistics.approved_corrections == len(plan.proposals)
    assert finalized.corrections.approvals == [approval]
    assert Analysis.model_validate_json(finalized_path.read_text()) == finalized


def test_export_refuses_no_approval_wrong_binding_tampering_and_reapplication(
    tmp_path: Path,
) -> None:
    source = _feed(tmp_path, b"8.8.8.0/24,us,us-ca,City,\n")
    proposed, plan = _proposed(source)
    rejected = record_approval(plan, "reviewer", [], [plan.proposals[0].id], DECIDED_AT)
    with pytest.raises(CorrectionError, match="at least one explicit approval"):
        materialize_corrected_bytes(proposed, rejected)

    approval = _approve(plan, plan.proposals[0].id)
    changed_binding = approval.model_copy(update={"source_sha256": "0" * 64})
    with pytest.raises(CorrectionError, match="approval ID"):
        materialize_corrected_bytes(proposed, changed_binding)

    tampered = proposed.model_dump(mode="json")
    tampered["corrections"]["proposals"][0]["proposed_value"] = "CA"
    with pytest.raises(ValidationError, match="does not match its content"):
        Analysis.model_validate(tampered)

    output = tmp_path / "corrected.csv"
    finalized_path = tmp_path / "final.json"
    finalized, _ = export_corrected_csv(proposed, approval, source, output, finalized_path)
    with pytest.raises(CorrectionError, match="already applied"):
        materialize_corrected_bytes(finalized, approval)


def test_export_fails_closed_for_paths_source_changes_and_unrepresentable_values(
    tmp_path: Path,
) -> None:
    source = _feed(tmp_path, b"8.8.8.0/24,us,US-CA,City,\n")
    proposed, plan = _proposed(source)
    approval = _approve(plan, plan.proposals[0].id)

    with pytest.raises(CorrectionError, match="must not overwrite"):
        export_corrected_csv(proposed, approval, source, source, tmp_path / "final.json")
    existing = tmp_path / "existing.csv"
    existing.write_text("do not replace", encoding="utf-8")
    with pytest.raises(CorrectionError, match="already exists"):
        export_corrected_csv(proposed, approval, source, existing, tmp_path / "final.json")
    assert existing.read_text() == "do not replace"
    source.write_bytes(b"8.8.8.0/24,US,US-CA,changed,\n")
    with pytest.raises(CorrectionError, match="digest"):
        export_corrected_csv(
            proposed, approval, source, tmp_path / "out.csv", tmp_path / "final.json"
        )
    assert not (tmp_path / "out.csv").exists()
    assert not (tmp_path / "final.json").exists()

    unsafe = proposed.model_dump(mode="json")
    unsafe_proposal = unsafe["corrections"]["proposals"][0]
    unsafe_proposal["proposed_value"] = "US\nCA"
    with pytest.raises(ValidationError, match="does not match its content"):
        Analysis.model_validate(unsafe)


def test_second_atomic_output_failure_removes_first_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _feed(tmp_path, b"8.8.8.0/24,us,US-CA,City,\n")
    proposed, plan = _proposed(source)
    approval = _approve(plan, plan.proposals[0].id)
    output = tmp_path / "corrected.csv"
    finalized = tmp_path / "final.json"

    import geofeed_quality.corrections as corrections

    real_write = corrections._write_atomic_new
    calls = 0

    def fail_second(path: Path, content: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("fabricated finalized-analysis write failure")
        real_write(path, content)

    monkeypatch.setattr(corrections, "_write_atomic_new", fail_second)
    with pytest.raises(OSError, match="fabricated"):
        export_corrected_csv(proposed, approval, source, output, finalized)
    assert not output.exists()
    assert not finalized.exists()


def test_mcp_best_match_is_advisory_and_failures_never_propose(tmp_path: Path) -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    mapping = export_request_exchange(analysis, 1_000)[1]
    enriched = import_response_batches(analysis, [_fixture_response()], mapping, 1_000)
    enriched.enrichment.mcp_observations[0].matches[0].place_name = "Palo Alto"
    proposed, _ = propose_corrections(enriched)

    mcp = [
        proposal
        for proposal in proposed.corrections.proposals
        if proposal.category == CorrectionCategory.MCP_PLACE_SUGGESTION
    ]
    assert [(item.field, item.proposed_value, item.confidence) for item in mcp] == [
        ("city", "Palo Alto", CorrectionConfidence.NOT_ASSESSED)
    ]
    assert all(item.row_id != "row-000003" for item in mcp)  # backend unavailable
    assert all("rank" not in item.rationale.lower() for item in mcp)
    assert all("confidence" not in item.rationale.lower() for item in mcp)

    request = request_document(export_request_batches(proposed, 1_000)[0])
    assert all(
        set(row) <= {"rowId", "country", "region", "city", "searchMode"} for row in request["rows"]
    )
    encoded = json.dumps(request)
    assert "proposal-" not in encoded and "corrections" not in encoded and "rdap" not in encoded


def test_csv_quotes_approved_advisory_text_without_executing_or_splitting_it(
    tmp_path: Path,
) -> None:
    source = FIXTURES / "valid.csv"
    analysis = analyze_file(source)
    mapping = export_request_exchange(analysis, 1_000)[1]
    enriched = import_response_batches(analysis, [_fixture_response()], mapping, 1_000)
    malicious = '=HYPERLINK("https://invalid.example","x"), literal'
    enriched.enrichment.mcp_observations[0].matches[0].place_name = malicious
    proposed, plan = propose_corrections(enriched)
    city = next(
        item
        for item in plan.proposals
        if item.category == CorrectionCategory.MCP_PLACE_SUGGESTION and item.field == "city"
    )
    corrected, _ = materialize_corrected_bytes(proposed, _approve(plan, city.id))
    output = _feed(tmp_path, corrected, "quoted.csv")
    row = analyze_file(output).rows[1]
    assert row.raw_fields[3] == malicious
    escaped = malicious.replace('"', '""')
    assert f'"{escaped}"'.encode() in corrected


def test_plan_and_approval_schema_drift_and_model_tampering_are_rejected(tmp_path: Path) -> None:
    proposed, plan = _proposed(_feed(tmp_path, b"8.8.8.0/24,us,US-CA,City,\n"))
    assert check_all_schemas()
    plan_schema = json.loads(correction_plan_schema_text())
    approval_schema = json.loads(correction_approval_schema_text())
    assert plan_schema["$schema"].endswith("2020-12/schema")
    assert plan_schema["$id"].endswith("correction-plan-1.0.json")
    assert approval_schema["$id"].endswith("correction-approval-1.0.json")
    assert plan_schema["additionalProperties"] is False
    assert approval_schema["additionalProperties"] is False

    changed_plan = plan.model_dump(mode="json")
    changed_plan["proposals"][0]["proposed_value"] = "CA"
    with pytest.raises(ValidationError, match="proposal digest"):
        CorrectionPlan.model_validate(changed_plan)

    approval = _approve(plan, plan.proposals[0].id)
    changed_approval = approval.model_dump(mode="json")
    changed_approval["decisions"].append(copy.deepcopy(changed_approval["decisions"][0]))
    with pytest.raises(ValidationError, match="unique"):
        CorrectionApproval.model_validate(changed_approval)

    dangling = proposed.model_dump(mode="json")
    dangling["corrections"]["proposals"][0]["evidence_ids"] = ["evidence-999999"]
    with pytest.raises(ValidationError):
        Analysis.model_validate(dangling)


def test_renderers_display_proposals_but_are_not_approval_authorities(tmp_path: Path) -> None:
    proposed, plan = _proposed(_feed(tmp_path, b"8.8.8.0/24,us,US-CA,City,\n"))
    proposal_id = plan.proposals[0].id
    document = proposed.model_dump(mode="json")

    markdown = render_markdown_document(document)
    html = render_html_document(document)
    assert proposal_id in markdown
    assert "pending" in markdown
    assert "separate validated approval artifact" in html
    assert "renderCorrections" in html
    assert proposed.corrections.approvals == []


def test_cli_end_to_end_requires_explicit_decision_and_reanalyzes(tmp_path: Path) -> None:
    source = _feed(tmp_path, b"8.8.8.0/24,us,us-ca,City,90210\n")
    analysis_path = tmp_path / "analysis.json"
    proposed_path = tmp_path / "proposed.json"
    plan_path = tmp_path / "plan.json"
    approval_path = tmp_path / "approval.json"
    corrected_path = tmp_path / "corrected.csv"
    final_path = tmp_path / "final.json"

    assert main(["analyze", str(source), "--output", str(analysis_path)]) == 0
    assert (
        main(
            [
                "propose-corrections",
                str(analysis_path),
                "--output",
                str(proposed_path),
                "--plan",
                str(plan_path),
            ]
        )
        == 0
    )
    plan = CorrectionPlan.model_validate_json(plan_path.read_text())
    approval_args = [
        "record-approval",
        str(plan_path),
        "--approver",
        "cli-review",
        "--decided-at",
        DECIDED_AT.isoformat(),
        "--output",
        str(approval_path),
    ]
    for proposal in plan.proposals:
        approval_args.extend(["--approve", proposal.id])
    assert main(approval_args) == 0
    assert (
        main(
            [
                "export-csv",
                str(proposed_path),
                str(approval_path),
                "--source",
                str(source),
                "--output",
                str(corrected_path),
                "--final-analysis",
                str(final_path),
            ]
        )
        == 0
    )
    corrected_analysis = analyze_file(corrected_path)
    assert corrected_analysis.rows[0].raw_fields == ["8.8.8.0/24", "US", "US-CA", "City", ""]
    assert (
        hashlib.sha256(corrected_path.read_bytes()).hexdigest()
        != analyze_file(source).source.sha256
    )


def test_maximum_row_proposal_sanity_has_no_hidden_mutation(tmp_path: Path) -> None:
    content = "\n".join(
        f"2606:4700:{index:x}::/48,{'us' if index == 0 else 'US'},US-CA,City,"
        for index in range(MAX_DATA_ROWS)
    ).encode()
    source = _feed(tmp_path, content)
    analysis = analyze_file(source)
    proposed, plan = propose_corrections(analysis)
    assert proposed.statistics.data_rows == MAX_DATA_ROWS
    assert len(proposed.corrections.proposals) == 1
    corrected, _ = materialize_corrected_bytes(proposed, _approve(plan, plan.proposals[0].id))
    assert corrected.count(b"\n") == MAX_DATA_ROWS - 1
    assert corrected.startswith(b"2606:4700:0::/48,US,US-CA,City,")
    assert proposed.source.sha256 == hashlib.sha256(content).hexdigest()
