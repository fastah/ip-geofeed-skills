# Copyright 2026 Fastah Inc.
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import ValidationError
from pydantic import ValidationError as PydanticValidationError

from geofeed_quality import analyze_file
from geofeed_quality.models import Analysis, FindingCategory, RdapAssessment, Severity
from geofeed_quality.renderer import render_markdown_document, render_markdown_file
from geofeed_quality.schema import check_schema, schema_text, validate_document

FIXTURES = Path(__file__).parent / "fixtures"


def test_models_roundtrip_and_document_validates_against_committed_schema() -> None:
    analysis = analyze_file(FIXTURES / "relationships.csv")
    document = analysis.model_dump(mode="json")
    validate_document(document)
    assert Analysis.model_validate_json(analysis.model_dump_json()) == analysis


def test_committed_schema_has_no_drift_and_is_draft_2020_12() -> None:
    assert check_schema()
    schema = json.loads(schema_text())
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["$id"].endswith("analysis-0.5.0.json")
    assert schema["$defs"]["FindingCategory"]["enum"] == [
        member.value for member in FindingCategory
    ]
    assert schema["$defs"]["Severity"]["enum"] == [member.value for member in Severity]
    assert schema["$defs"]["RdapAssessment"]["enum"] == [member.value for member in RdapAssessment]


def test_schema_drift_check_fails_for_changed_artifact(tmp_path: Path) -> None:
    drifted = tmp_path / "analysis.schema.json"
    drifted.write_text(schema_text() + " ", encoding="utf-8")
    assert not check_schema(drifted)


def test_schema_rejects_unknown_contract_fields() -> None:
    document = analyze_file(FIXTURES / "valid.csv").model_dump(mode="json")
    document["unknown"] = True
    with pytest.raises(ValidationError):
        validate_document(document)


def test_renderer_accepts_only_validated_ir_and_uses_ir_counters(tmp_path: Path) -> None:
    analysis = analyze_file(FIXTURES / "relationships.csv")
    document = analysis.model_dump(mode="json")
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    rendered = render_markdown_file(path)
    assert f"| Data rows | {analysis.statistics.data_rows} |" in rendered
    assert f"| Findings | {len(analysis.findings)} |" in rendered
    assert "RFC8805.DUPLICATE_PREFIX" in rendered
    assert "conflicting_geolocation" in rendered

    document["statistics"]["data_rows"] = 321
    with pytest.raises(PydanticValidationError, match=r"statistics\.data_rows"):
        render_markdown_document(document)


def test_analysis_rejects_dangling_and_inconsistent_record_graphs() -> None:
    document = analyze_file(FIXTURES / "relationships.csv").model_dump(mode="json")
    tampered: list[dict[str, object]] = []

    dangling_row_evidence = copy.deepcopy(document)
    dangling_row_evidence["rows"][0]["evidence_ids"].append("evidence-999999")
    tampered.append(dangling_row_evidence)

    invalid_finding_target = copy.deepcopy(document)
    invalid_finding_target["findings"][0]["target_ids"] = ["row-999999"]
    tampered.append(invalid_finding_target)

    invalid_relationship_row = copy.deepcopy(document)
    invalid_relationship_row["relationships"][0]["source_row_id"] = "row-999999"
    tampered.append(invalid_relationship_row)

    duplicate_evidence = copy.deepcopy(document)
    duplicate_evidence["evidence"][1]["id"] = duplicate_evidence["evidence"][0]["id"]
    tampered.append(duplicate_evidence)

    wrong_finding_count = copy.deepcopy(document)
    wrong_finding_count["statistics"]["finding_counts"]["rfc8805_violation"] += 1
    tampered.append(wrong_finding_count)

    for candidate in tampered:
        with pytest.raises(PydanticValidationError):
            Analysis.model_validate(candidate)


def test_renderer_rejects_csv_or_invalid_json_shape() -> None:
    with pytest.raises(ValidationError):
        render_markdown_document({"rows": []})
