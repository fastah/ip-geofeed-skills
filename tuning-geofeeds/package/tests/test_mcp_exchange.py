# Copyright 2026 Fastah Inc.
from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError as PydanticValidationError

from geofeed_quality import analyze_file
from geofeed_quality.errors import McpExchangeError
from geofeed_quality.mcp_exchange import (
    McpRequestBatch,
    McpResponseBatch,
    export_request_batches,
    export_request_exchange,
    opaque_row_key,
    request_document,
)
from geofeed_quality.mcp_exchange import (
    import_response_batches as _import_response_batches,
)
from geofeed_quality.models import (
    Analysis,
    McpRowStatus,
    McpSearchMode,
    PublisherProfile,
    RowKind,
    RowState,
)
from geofeed_quality.schema import (
    check_all_schemas,
    mcp_request_schema_text,
    mcp_response_schema_text,
    validate_document,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _wire_row_key(index: int) -> str:
    return f"test-row-key-{index:020d}"


def _fixture_response() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((FIXTURES / "mcp-response-v1.json").read_text(encoding="utf-8")),
    )


def _many_rows_analysis(tmp_path: Path, count: int) -> Analysis:
    feed = tmp_path / "many.csv"
    feed.write_text(
        "\n".join(f"2606:4700:{index:x}::/48,US,US-CA,City {index}," for index in range(count)),
        encoding="utf-8",
    )
    return analyze_file(feed)


def _base_row_content(analysis: Analysis) -> list[dict[str, Any]]:
    return [
        row.model_dump(mode="json", exclude={"finding_ids", "evidence_ids"})
        for row in analysis.rows
    ]


def import_response_batches(
    analysis: Analysis,
    responses: list[dict[str, Any] | McpResponseBatch],
    batch_limit: int,
    search_mode: McpSearchMode = McpSearchMode.AUTO,
) -> Analysis:
    _, mapping = export_request_exchange(analysis, batch_limit, search_mode)
    return _import_response_batches(analysis, responses, mapping, batch_limit, search_mode)


def test_export_uses_discovered_batch_limit_at_boundaries(tmp_path: Path) -> None:
    analysis = _many_rows_analysis(tmp_path, 1_001)
    batches = export_request_batches(analysis, 1_000)
    assert [len(batch.rows) for batch in batches] == [1_000, 1]
    assert [len(batch.rows) for batch in export_request_batches(analysis, 1)] == [1] * 1_001
    with pytest.raises(McpExchangeError, match="must be positive"):
        export_request_batches(analysis, 0)


def test_export_deduplicates_exact_tuples_in_first_seen_order_and_maps_targets(
    tmp_path: Path,
) -> None:
    feed = tmp_path / "duplicates.csv"
    feed.write_text(
        "8.8.8.0/24,US,US-CA,Mountain View,\n"
        "1.1.1.0/24,US,US-NY,New York,\n"
        "9.9.9.0/24,US,US-CA,Mountain View,\n"
        "4.4.4.0/24,US,US-TX,Austin,\n"
        "5.5.5.0/24,US,US-CA,Mountain View,\n",
        encoding="utf-8",
    )
    analysis = analyze_file(feed)
    batches, mapping = export_request_exchange(analysis, 2)
    assert [[row.city_name for row in batch.rows] for batch in batches] == [
        ["Mountain View", "New York"],
        ["Austin"],
    ]
    first = mapping.batches[0].targets[0]
    assert first.target_source_row_ids == ["row-000001", "row-000003", "row-000005"]
    assert first.target_opaque_row_keys == [
        opaque_row_key(analysis, analysis.rows[index]) for index in (0, 2, 4)
    ]
    assert mapping.batches[0].representative_row_keys[0] == first.target_opaque_row_keys[0]
    encoded_requests = json.dumps([request_document(batch) for batch in batches])
    encoded_mapping = mapping.model_dump_json(by_alias=True)
    for prefix in ("8.8.8.0/24", "1.1.1.0/24", "9.9.9.0/24"):
        assert prefix not in encoded_requests
        assert prefix not in encoded_mapping


def test_search_mode_is_part_of_exact_deduplication_key(tmp_path: Path) -> None:
    analysis = _many_rows_analysis(tmp_path, 1)
    auto = export_request_exchange(analysis, 1_000, McpSearchMode.AUTO)[1]
    larger = export_request_exchange(analysis, 1_000, McpSearchMode.PREFER_LARGER_AREA)[1]
    assert auto.batches[0].request_sha256 != larger.batches[0].request_sha256
    assert auto.integrity_sha256 != larger.integrity_sha256


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        ("matched", "MATCH_FOUND", False),
        ("do_not_geolocate", "DO_NOT_GEOLOCATE", False),
        ("no_match", "NO_MATCH", False),
        ("invalid_input", "INVALID_CITY_NAME", False),
        ("backend_unavailable", "BACKEND_UNAVAILABLE", True),
    ],
)
def test_every_status_fans_out_to_unique_exactly_once_observations(
    tmp_path: Path, status: str, code: str, retryable: bool
) -> None:
    feed = tmp_path / "fanout.csv"
    feed.write_text(
        "8.8.8.0/24,US,US-CA,Mountain View,\n9.9.9.0/24,US,US-CA,Mountain View,\n",
        encoding="utf-8",
    )
    analysis = analyze_file(feed)
    base = _base_row_content(analysis)
    batches, mapping = export_request_exchange(analysis, 1_000)
    result = copy.deepcopy(_fixture_response()["results"][0])
    result.update(
        rowKey=batches[0].rows[0].row_key,
        status=status,
        code=code,
        retryable=retryable,
    )
    if status != "matched":
        result["matches"] = []
    summary = {
        "total": 1,
        "matched": int(status == "matched"),
        "doNotGeolocate": int(status == "do_not_geolocate"),
        "noMatch": int(status == "no_match"),
        "invalidInput": int(status == "invalid_input"),
        "backendUnavailable": int(status == "backend_unavailable"),
        "retryable": int(retryable),
    }
    response = {
        "contractVersion": "1.0",
        "batchLimit": 1_000,
        "summary": summary,
        "results": [result],
    }
    enriched = _import_response_batches(analysis, [response], mapping, 1_000)
    observations = enriched.enrichment.mcp_observations
    assert len(observations) == 2
    assert len({item.opaque_row_id for item in observations}) == 2
    assert len({item.target_row_id for item in observations}) == 2
    assert {item.status.value for item in observations} == {status}
    assert len({item.representative_opaque_row_id for item in observations}) == 1
    assert _base_row_content(enriched) == base


def test_import_rejects_tampered_and_stale_mapping(tmp_path: Path) -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    _, mapping = export_request_exchange(analysis, 1_000)
    tampered = mapping.model_dump(mode="json", by_alias=True)
    tampered["batches"][0]["requestSha256"] = "f" * 64
    with pytest.raises(McpExchangeError, match="integrity digest"):
        _import_response_batches(analysis, [_fixture_response()], tampered, 1_000)

    other = _many_rows_analysis(tmp_path, 3)
    with pytest.raises(McpExchangeError, match="does not match this analysis"):
        _import_response_batches(other, [_fixture_response()], mapping, 1_000)


def test_opaque_row_keys_are_deterministic_unique_and_not_location_only() -> None:
    first = analyze_file(FIXTURES / "valid.csv")
    second = first.model_copy(deep=True)
    eligible = [row for row in first.rows if row.kind == RowKind.DATA]
    ids = [opaque_row_key(first, row) for row in eligible]
    assert ids == [opaque_row_key(second, row) for row in eligible]
    assert len(ids) == len(set(ids))
    assert all(value.startswith("fq-") and len(value) == 35 for value in ids)

    duplicated_location = eligible[0].model_copy(deep=True, update={"id": "row-999999"})
    assert opaque_row_key(first, eligible[0]) != opaque_row_key(first, duplicated_location)


def test_export_is_a_mechanical_privacy_allowlist() -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    analysis.enrichment.publisher_profile = PublisherProfile(
        organization_name="Sensitive Publisher"
    )
    document = request_document(export_request_batches(analysis, 1_000)[0])
    assert set(document) == {"rows"}
    allowed = {"rowKey", "countryCode", "regionCode", "cityName", "searchMode"}
    assert all(set(row) <= allowed for row in document["rows"])
    encoded = json.dumps(document)
    for prohibited in (
        "8.8.8.0/24",
        "2606:4700::/48",
        "Representative public",
        "Sensitive Publisher",
        "sha256",
        "rdap",
        "source",
    ):
        assert prohibited not in encoded


def test_empty_and_zz_rows_receive_normalized_dng_outcomes_without_mutation(
    tmp_path: Path,
) -> None:
    feed = tmp_path / "do-not-geolocate.csv"
    feed.write_text("8.8.8.0/24,,,,\n1.1.1.0/24,zz,,,\n", encoding="utf-8")
    analysis = analyze_file(feed)
    batch = export_request_batches(analysis, 1_000)[0]
    assert [row.country_code for row in batch.rows] == ["", "ZZ"]
    assert all(row.state == RowState.VALID_DO_NOT_GEOLOCATE for row in analysis.rows)

    do_not_geolocate = cast(dict[str, Any], _fixture_response()["results"][2])
    results: list[dict[str, Any]] = []
    for request in batch.rows:
        result = copy.deepcopy(do_not_geolocate)
        result["rowKey"] = request.row_key
        results.append(result)
    response: dict[str, Any] = {
        "contractVersion": "1.0",
        "batchLimit": 1_000,
        "summary": {
            "total": 2,
            "matched": 0,
            "doNotGeolocate": 2,
            "noMatch": 0,
            "invalidInput": 0,
            "backendUnavailable": 0,
            "retryable": 0,
        },
        "results": results,
    }
    enriched = import_response_batches(analysis, [response], 1_000)

    assert _base_row_content(enriched) == _base_row_content(analysis)
    assert all(row.state == RowState.VALID_DO_NOT_GEOLOCATE for row in enriched.rows)
    assert [row.location.country for row in enriched.rows if row.location] == ["", "ZZ"]
    assert all(
        item.status == McpRowStatus.DO_NOT_GEOLOCATE
        for item in enriched.enrichment.mcp_observations
    )


def test_wire_schemas_are_closed_draft_2020_12_and_drift_checked() -> None:
    assert check_all_schemas()
    request_schema = json.loads(mcp_request_schema_text())
    response_schema = json.loads(mcp_response_schema_text())
    assert request_schema["$schema"].endswith("2020-12/schema")
    assert response_schema["$schema"].endswith("2020-12/schema")
    assert request_schema["additionalProperties"] is False
    assert response_schema["additionalProperties"] is False
    assert set(request_schema["$defs"]["McpRequestRow"]["properties"]) == {
        "rowKey",
        "countryCode",
        "regionCode",
        "cityName",
        "searchMode",
    }


def test_go_contract_fixture_validates_and_import_preserves_base_ir() -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    base_rows = _base_row_content(analysis)
    base_relationships = copy.deepcopy(analysis.relationships)
    base_findings = copy.deepcopy(analysis.findings)
    response = McpResponseBatch.model_validate(_fixture_response())

    enriched = import_response_batches(analysis, [response], 1_000)
    validate_document(enriched.model_dump(mode="json"))
    assert Analysis.model_validate_json(enriched.model_dump_json()) == enriched
    assert _base_row_content(enriched) == base_rows
    assert enriched.relationships == base_relationships
    assert enriched.findings[: len(base_findings)] == base_findings
    assert [item.status for item in enriched.enrichment.mcp_observations] == [
        McpRowStatus.MATCHED,
        McpRowStatus.BACKEND_UNAVAILABLE,
        McpRowStatus.DO_NOT_GEOLOCATE,
    ]
    match = enriched.enrichment.mcp_observations[0].matches[0]
    assert match.place_id_geonames == 5_375_480
    assert match.center_long_lat == [-122.08385, 37.38605]
    assert match.population_weight_percent == 0.02
    assert enriched.corrections.proposals == []
    assert enriched.statistics.resolved_rows == 0
    assert "confidence" not in enriched.model_dump_json()
    mcp_evidence = next(item for item in enriched.evidence if item.type.value == "mcp")
    assert mcp_evidence.values["message"] == "Place matches found, ordered best-first."


def test_analysis_rejects_dangling_or_inconsistent_mcp_references() -> None:
    enriched = import_response_batches(
        analyze_file(FIXTURES / "valid.csv"), [_fixture_response()], 1_000
    )

    dangling = enriched.model_dump(mode="json")
    dangling["enrichment"]["mcp_observations"][0]["target_row_id"] = "row-999999"
    with pytest.raises(PydanticValidationError, match="invalid row target"):
        Analysis.model_validate(dangling)

    inconsistent = enriched.model_dump(mode="json")
    inconsistent["configuration"]["mcp"]["server_advertised_batch_limit"] = 999
    with pytest.raises(PydanticValidationError, match="disagrees with MCP configuration"):
        Analysis.model_validate(inconsistent)


def test_reimport_is_idempotent_and_conflicting_reimport_is_rejected() -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    response = _fixture_response()
    enriched = import_response_batches(analysis, [response], 1_000)
    assert import_response_batches(enriched, [response], 1_000) == enriched

    changed = copy.deepcopy(response)
    changed["results"][0]["message"] = "Different safe message"
    with pytest.raises(McpExchangeError, match="conflicting"):
        import_response_batches(enriched, [changed], 1_000)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(contractVersion="2.0"), "contractVersion"),
        (lambda value: value["summary"].update(total=4), "summary"),
        (lambda value: value.update(batchLimit=999), "host-discovered"),
        (lambda value: value["results"][0].update(code="NO_MATCH"), "invalid for status"),
        (lambda value: value["results"][1].update(retryable=False), "only backend"),
    ],
)
def test_import_rejects_contract_invariant_failures(
    mutation: Callable[[dict[str, Any]], None], message: str
) -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    response = _fixture_response()
    mutation(response)
    with pytest.raises(McpExchangeError, match=message):
        import_response_batches(analysis, [response], 1_000)


def test_import_rejects_unknown_duplicate_missing_and_reordered_keys() -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")

    unknown = _fixture_response()
    unknown["results"][0]["rowKey"] = _wire_row_key(999)
    with pytest.raises(McpExchangeError, match="unknown representative rowKey"):
        import_response_batches(analysis, [unknown], 1_000)

    duplicate = _fixture_response()
    duplicate["results"][1]["rowKey"] = duplicate["results"][0]["rowKey"]
    with pytest.raises(McpExchangeError, match=r"unique|duplicate"):
        import_response_batches(analysis, [duplicate], 1_000)

    missing = _fixture_response()
    missing["results"].pop()
    missing["summary"].update(total=2, doNotGeolocate=0)
    with pytest.raises(McpExchangeError, match="exported request batch"):
        import_response_batches(analysis, [missing], 1_000)

    reordered = _fixture_response()
    reordered["results"][0], reordered["results"][1] = (
        reordered["results"][1],
        reordered["results"][0],
    )
    with pytest.raises(McpExchangeError, match="exported request batch"):
        import_response_batches(analysis, [reordered], 1_000)


def test_all_statuses_validate_with_ordered_mixed_partial_results() -> None:
    rows = [
        {
            "rowKey": _wire_row_key(index),
            "status": status,
            "code": code,
            "message": "safe",
            "retryable": retryable,
            "matches": [],
        }
        for index, (status, code, retryable) in enumerate(
            [
                ("do_not_geolocate", "DO_NOT_GEOLOCATE", False),
                ("no_match", "NO_MATCH", False),
                ("invalid_input", "INVALID_CITY_NAME", False),
                ("backend_unavailable", "BACKEND_UNAVAILABLE", True),
            ],
            start=1,
        )
    ]
    matched = copy.deepcopy(_fixture_response()["results"][0])
    matched["rowKey"] = _wire_row_key(5)
    rows.append(matched)
    response = McpResponseBatch.model_validate(
        {
            "contractVersion": "1.0",
            "batchLimit": 5,
            "summary": {
                "total": 5,
                "matched": 1,
                "doNotGeolocate": 1,
                "noMatch": 1,
                "invalidInput": 1,
                "backendUnavailable": 1,
                "retryable": 1,
            },
            "results": rows,
        }
    )
    assert [row.status for row in response.results] == [
        McpRowStatus.DO_NOT_GEOLOCATE,
        McpRowStatus.NO_MATCH,
        McpRowStatus.INVALID_INPUT,
        McpRowStatus.BACKEND_UNAVAILABLE,
        McpRowStatus.MATCHED,
    ]


def test_request_model_rejects_unknown_fields_and_duplicate_row_keys() -> None:
    with pytest.raises(ValueError):
        McpRequestBatch.model_validate(
            {
                "rows": [
                    {
                        "rowKey": _wire_row_key(1),
                        "countryCode": "US",
                        "searchMode": "auto",
                        "prefix": "8.8.8.0/24",
                    }
                ]
            }
        )
    with pytest.raises(ValueError, match="unique"):
        McpRequestBatch.model_validate(
            {
                "rows": [
                    {
                        "rowKey": _wire_row_key(1),
                        "countryCode": "US",
                        "searchMode": "auto",
                    },
                    {
                        "rowKey": _wire_row_key(1),
                        "countryCode": "GB",
                        "searchMode": "auto",
                    },
                ]
            }
        )


def test_search_mode_is_recorded_but_never_applies_suggestions() -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    response = _fixture_response()
    enriched = import_response_batches(
        analysis,
        [response],
        1_000,
        McpSearchMode.PREFER_LARGER_POPULATION_CENTER,
    )
    assert all(
        observation.search_mode == McpSearchMode.PREFER_LARGER_POPULATION_CENTER
        for observation in enriched.enrichment.mcp_observations
    )
    assert _base_row_content(enriched) == _base_row_content(analysis)
