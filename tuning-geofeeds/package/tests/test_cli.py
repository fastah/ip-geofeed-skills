from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from geofeed_quality.cli import main
from geofeed_quality.models import (
    RdapAssessment,
    RdapEntitySummary,
    RdapNetworkSummary,
    RdapPublicIdentifier,
)
from geofeed_quality.rdap import RdapLookupResult, RdapRuntimeConfig

FIXTURES = Path(__file__).parent / "fixtures"


def test_analyze_then_render_cli(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.json"
    report_path = tmp_path / "analysis.md"
    assert main(["analyze", str(FIXTURES / "valid.csv"), "--output", str(analysis_path)]) == 0
    assert main(["render", str(analysis_path), "--output", str(report_path)]) == 0
    assert json.loads(analysis_path.read_text())["schema_version"] == "0.4.0"
    assert report_path.read_text().startswith("# Geofeed quality analysis\n")


def test_html_and_geojson_cli_consume_analysis_json(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.json"
    html_path = tmp_path / "dashboard.html"
    geojson_path = tmp_path / "analysis.geojson"
    assert main(["analyze", str(FIXTURES / "valid.csv"), "--output", str(analysis_path)]) == 0
    assert main(["render-html", str(analysis_path), "--output", str(html_path)]) == 0
    assert main(["export-geojson", str(analysis_path), "--output", str(geojson_path)]) == 0
    assert html_path.read_text(encoding="utf-8").startswith("<!doctype html>")
    assert json.loads(geojson_path.read_text(encoding="utf-8")) == {
        "type": "FeatureCollection",
        "features": [],
        "attribution": ["Contains information derived from GeoNames (https://www.geonames.org/)."],
    }


def test_html_cli_reads_explicit_mapbox_token_file(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.json"
    html_path = tmp_path / "dashboard.html"
    token_path = tmp_path / "token"
    token = "pk." + "x" * 40
    token_path.write_text(token, encoding="utf-8")
    assert main(["analyze", str(FIXTURES / "valid.csv"), "--output", str(analysis_path)]) == 0
    assert (
        main(
            [
                "render-html",
                str(analysis_path),
                "--output",
                str(html_path),
                "--mapbox-token-file",
                str(token_path),
                "--mapbox-style",
                "mapbox://styles/mapbox/streets-v12",
            ]
        )
        == 0
    )
    assert token in html_path.read_text(encoding="utf-8")


def test_schema_check_cli() -> None:
    assert main(["schema", "check"]) == 0


class _FixtureRdapClient:
    config = RdapRuntimeConfig(max_concurrency=1, min_interval_per_rir_seconds=0)

    def lookup(self, prefix: str) -> RdapLookupResult:
        if ":" in prefix:
            network = RdapNetworkSummary(
                start_address="2606:4700::",
                end_address="2606:4700:ffff:ffff:ffff:ffff:ffff:ffff",
                ip_version="v6",
            )
        else:
            network = RdapNetworkSummary(
                start_address="1.0.0.0", end_address="8.255.255.255", ip_version="v4"
            )
        return RdapLookupResult(
            requested_prefix=prefix,
            queried_at=datetime(2026, 1, 2, tzinfo=UTC),
            rir="FIXTURE-RIR",
            endpoint="https://rdap.fixture.example/",
            http_status=200,
            network=network,
        )


def test_cli_rdap_is_explicit_opt_in_and_accepts_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis_path = tmp_path / "analysis.json"
    profile_path = tmp_path / "publisher.json"
    profile_path.write_text('{"organization_name":"Example Networks","asn":"15169"}')

    def fixture_client(**_kwargs: object) -> _FixtureRdapClient:
        return _FixtureRdapClient()

    monkeypatch.setattr("geofeed_quality.cli.AuthoritativeRdapClient.from_iana", fixture_client)
    assert (
        main(
            [
                "analyze",
                str(FIXTURES / "valid.csv"),
                "--output",
                str(analysis_path),
                "--rdap",
                "--publisher-profile",
                str(profile_path),
            ]
        )
        == 0
    )
    document = json.loads(analysis_path.read_text())
    assert document["configuration"]["enrichment_enabled"] is True
    assert document["enrichment"]["publisher_profile"]["asn"] == "AS15169"
    assert len(document["enrichment"]["observations"]) == 3


def test_cli_offline_path_does_not_construct_rdap_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis_path = tmp_path / "analysis.json"

    def fail(**_kwargs: object) -> None:
        raise AssertionError("offline analysis attempted RDAP")

    monkeypatch.setattr("geofeed_quality.cli.AuthoritativeRdapClient.from_iana", fail)
    assert main(["analyze", str(FIXTURES / "valid.csv"), "--output", str(analysis_path)]) == 0
    document = json.loads(analysis_path.read_text())
    assert document["configuration"]["enrichment_enabled"] is False
    assert document["enrichment"]["observations"] == []


class _MalformedFixtureRdapClient(_FixtureRdapClient):
    def lookup(self, prefix: str) -> RdapLookupResult:
        result = super().lookup(prefix)
        if ":" not in prefix:
            return result
        malformed_domain = f"{'z' * 64}.example"
        return RdapLookupResult(
            requested_prefix=result.requested_prefix,
            queried_at=result.queried_at,
            rir=result.rir,
            endpoint=result.endpoint,
            http_status=result.http_status,
            network=result.network,
            entities=(
                RdapEntitySummary(
                    roles=["registrant"],
                    public_ids=[RdapPublicIdentifier(type="domain", identifier=malformed_domain)],
                ),
            ),
        )


def test_cli_preserves_output_when_one_rdap_assessment_is_malformed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    analysis_path = tmp_path / "analysis.json"
    profile_path = tmp_path / "publisher.json"
    profile_path.write_text('{"domain":"example.net"}')
    monkeypatch.setattr(
        "geofeed_quality.cli.AuthoritativeRdapClient.from_iana",
        lambda **_kwargs: _MalformedFixtureRdapClient(),
    )

    assert (
        main(
            [
                "analyze",
                str(FIXTURES / "valid.csv"),
                "--output",
                str(analysis_path),
                "--rdap",
                "--publisher-profile",
                str(profile_path),
            ]
        )
        == 0
    )
    document = json.loads(analysis_path.read_text())
    observations = document["enrichment"]["observations"]
    assert len(observations) == 3
    assert any(item["assessment"] == RdapAssessment.UNAVAILABLE for item in observations)
    assert "z" * 64 not in analysis_path.read_text()


def test_cli_mcp_export_and_import_are_host_mediated(tmp_path: Path) -> None:
    analysis_path = tmp_path / "analysis.json"
    batches_path = tmp_path / "batches"
    enriched_path = tmp_path / "enriched.json"
    response_path = FIXTURES / "mcp-response-v1.json"
    assert main(["analyze", str(FIXTURES / "valid.csv"), "--output", str(analysis_path)]) == 0
    assert (
        main(
            [
                "mcp-export",
                str(analysis_path),
                "--output-dir",
                str(batches_path),
                "--batch-limit",
                "1000",
                "--search-mode",
                "prefer_larger_population_center",
            ]
        )
        == 0
    )
    request = json.loads((batches_path / "batch-000001.json").read_text())
    assert set(request) == {"rows"}
    assert len(request["rows"]) == 3

    assert (
        main(
            [
                "mcp-import",
                str(analysis_path),
                str(response_path),
                "--mapping",
                str(batches_path / "mapping.json"),
                "--output",
                str(enriched_path),
                "--batch-limit",
                "1000",
                "--search-mode",
                "prefer_larger_population_center",
            ]
        )
        == 0
    )
    enriched = json.loads(enriched_path.read_text())
    assert enriched["configuration"]["mcp"] == {
        "contract_version": "1.0",
        "server_advertised_batch_limit": 1000,
        "transport": "host_mediated",
    }
    assert len(enriched["enrichment"]["mcp_observations"]) == 3
    assert all(
        item["search_mode"] == "prefer_larger_population_center"
        for item in enriched["enrichment"]["mcp_observations"]
    )


def test_user_facing_outputs_refuse_existing_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    analysis_path = tmp_path / "analysis.json"
    batches_path = tmp_path / "batches"
    assert main(["analyze", str(FIXTURES / "valid.csv"), "--output", str(analysis_path)]) == 0
    assert (
        main(
            [
                "mcp-export",
                str(analysis_path),
                "--output-dir",
                str(batches_path),
                "--batch-limit",
                "1000",
            ]
        )
        == 0
    )
    capsys.readouterr()

    commands = [
        ["analyze", str(FIXTURES / "valid.csv")],
        ["render", str(analysis_path)],
        ["render-html", str(analysis_path)],
        ["export-geojson", str(analysis_path)],
        [
            "mcp-import",
            str(analysis_path),
            str(FIXTURES / "mcp-response-v1.json"),
            "--mapping",
            str(batches_path / "mapping.json"),
            "--batch-limit",
            "1000",
        ],
    ]
    for index, command in enumerate(commands):
        output = tmp_path / f"existing-{index}"
        output.write_text("preserve this content", encoding="utf-8")
        assert main([*command, "--output", str(output)]) == 2
        assert output.read_text(encoding="utf-8") == "preserve this content"
        assert f"error: output already exists: {output}" in capsys.readouterr().err
