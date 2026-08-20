# Copyright 2026 Fastah Inc.
from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from geofeed_quality import MAX_DATA_ROWS, analyze_file
from geofeed_quality.geojson_renderer import (
    GEOJSON_ATTRIBUTION,
    GeoJsonFeatureCollection,
    export_geojson_analysis,
    export_geojson_document,
)
from geofeed_quality.html_renderer import MapboxOptions, render_html_analysis, render_html_document
from geofeed_quality.mcp_exchange import (
    McpResponseBatch,
    export_request_exchange,
    import_response_batches,
)
from geofeed_quality.renderer import render_markdown_document

FIXTURES = Path(__file__).parent / "fixtures"


def _enriched_analysis() -> Any:
    analysis = analyze_file(FIXTURES / "valid.csv")
    response = McpResponseBatch.model_validate_json(
        (FIXTURES / "mcp-response-v1.json").read_text(encoding="utf-8")
    )
    mapping = export_request_exchange(analysis, 1_000)[1]
    return import_response_batches(analysis, [response], mapping, 1_000)


class _DashboardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))


def _script_data(html: str, element_id: str) -> dict[str, Any]:
    match = re.search(
        rf'<script id="{re.escape(element_id)}" type="application/json">(.*?)</script>', html
    )
    assert match
    return cast(dict[str, Any], json.loads(match.group(1)))


def test_geojson_projects_only_supported_best_match_geometry() -> None:
    geojson = export_geojson_analysis(_enriched_analysis())
    assert GeoJsonFeatureCollection.model_validate_json(geojson.model_dump_json()) == geojson
    assert [feature.id for feature in geojson.features] == ["mcp-000001-point", "mcp-000001-bbox"]
    assert geojson.features[0].geometry.coordinates == [-122.08385, 37.38605]
    assert geojson.features[1].geometry.coordinates == [
        [[-122.2, 37.3], [-122.0, 37.3], [-122.0, 37.5], [-122.2, 37.5], [-122.2, 37.3]]
    ]
    assert geojson.attribution == [GEOJSON_ATTRIBUTION]
    assert (
        export_geojson_analysis(_enriched_analysis()).model_dump_json() == geojson.model_dump_json()
    )


def test_geojson_is_an_explicit_privacy_allowlist() -> None:
    analysis = _enriched_analysis()
    encoded = export_geojson_analysis(analysis).model_dump_json()
    allowed = {
        "rowId",
        "prefix",
        "mcpStatus",
        "placeType",
        "placeName",
        "countryCode",
        "regionCode",
        "geometryRole",
        "findingCount",
        "highestSeverity",
    }
    assert all(
        set(feature.properties.model_dump()) == allowed
        for feature in export_geojson_analysis(analysis).features
    )
    for prohibited in (
        "Representative public",
        "source.csv",
        "publisher_profile",
        "selected_entities",
        "response_sha256",
        "Place matches found",
        "corrections",
        "population_weight",
        "approximate_radius",
    ):
        assert prohibited not in encoded


def test_geojson_empty_and_invalid_geometry_are_safe() -> None:
    assert export_geojson_analysis(analyze_file(FIXTURES / "valid.csv")).features == []
    analysis = _enriched_analysis()
    analysis.enrichment.mcp_observations[0].matches[0].center_long_lat[:] = [181, 91]
    analysis.enrichment.mcp_observations[0].matches[0].bounding_box[:] = [0, 30, 20, 10]
    assert export_geojson_analysis(analysis).features == []


def test_renderers_reject_tampered_imported_ir() -> None:
    document = analyze_file(FIXTURES / "valid.csv").model_dump(mode="json")
    document["statistics"]["data_rows"] = 99
    with pytest.raises(ValidationError, match=r"statistics\.data_rows does not match"):
        render_html_document(document)
    with pytest.raises(ValidationError, match=r"statistics\.data_rows does not match"):
        export_geojson_document(document)


def test_html_is_deterministic_offline_secure_and_semantic() -> None:
    analysis = _enriched_analysis()
    html = render_html_analysis(analysis)
    assert render_html_analysis(analysis) == html
    assert "default-src 'none'" in html
    assert "connect-src 'none'" in html
    assert "worker-src 'none'" in html
    assert '<meta name="referrer" content="no-referrer">' in html
    assert "api.mapbox.com/mapbox-gl-js" not in html
    assert "GeoNames" in html and "Mapbox" in html
    assert "Radius and population weight are not confidence" in html
    assert "does not prove legal ownership" in html
    assert "prefers-reduced-motion:reduce" in html
    assert ":focus-visible" in html
    assert "innerHTML" not in html
    assert not re.search(r"\son[a-z]+=", html, re.IGNORECASE)

    parser = _DashboardParser()
    parser.feed(html)
    tags = [tag for tag, _attrs in parser.tags]
    assert all(tag in tags for tag in ("header", "main", "section", "aside", "footer", "table"))
    assert sum(tag == "h1" for tag in tags) == 1
    assert any(tag == "caption" for tag in tags)
    assert any(tag == "th" and attrs.get("scope") == "col" for tag, attrs in parser.tags)
    assert any(tag == "input" and attrs.get("type") == "search" for tag, attrs in parser.tags)
    assert all(attrs.get("type") == "button" for tag, attrs in parser.tags if tag == "button")

    metrics = _script_data(html, "metrics-data")
    assert metrics["summary"]["dataRows"] == analysis.statistics.data_rows
    assert metrics["denominators"]["findingCategories"] == len(analysis.findings)
    assert sum(metrics["findingCategories"].values()) == len(analysis.findings)
    assert metrics["denominators"]["mcpStatuses"] == 3
    assert sum(metrics["mcpStatuses"].values()) == 3
    assert set(metrics["mcpStatuses"]) == {
        "matched",
        "do_not_geolocate",
        "no_match",
        "invalid_input",
        "backend_unavailable",
    }
    assert set(metrics["rdapAssessments"]) == {
        "consistent",
        "conflicting",
        "unverified",
        "unavailable",
    }
    assert "duplicate" in metrics["relationships"]


def test_html_escapes_untrusted_script_breakout_and_unicode_separators(tmp_path: Path) -> None:
    payload = '</script><img src=x onerror="alert(1)">\u2028\u2029\u0085\'"&'
    feed = tmp_path / "hostile.csv"
    feed.write_text(f"8.8.8.0/24,US,US-CA,{payload},\n", encoding="utf-8")
    analysis = analyze_file(feed)
    html = render_html_analysis(analysis)
    assert "</script><img" not in html
    assert "<img src=x" not in html
    embedded = _script_data(html, "analysis-data")
    assert embedded == analysis.model_dump(mode="json")
    assert "\\u2028" in html and "\\u2029" in html and "\\u0085" in html


def test_html_projects_relationship_records_without_recomputing_them(tmp_path: Path) -> None:
    feed = tmp_path / "relationships.csv"
    feed.write_text(
        "8.8.0.0/16,US,US-CA,Parent,\n"
        "8.8.8.0/24,US,US-NY,Carved child,\n"
        "8.8.8.0/24,US,US-NY,Carved child,\n",
        encoding="utf-8",
    )
    analysis = analyze_file(feed)
    assert analysis.relationships
    embedded = _script_data(render_html_analysis(analysis), "analysis-data")
    assert embedded["relationships"] == [
        relationship.model_dump(mode="json") for relationship in analysis.relationships
    ]


def test_mapbox_configuration_is_explicit_and_token_is_isolated() -> None:
    analysis = _enriched_analysis()
    token = "pk." + "x" * 40
    options = MapboxOptions(token, "mapbox://styles/mapbox/streets-v12")
    html = render_html_analysis(analysis, options)
    assert token in html
    assert '<meta name="referrer" content="origin">' in html
    assert "https://api.mapbox.com/mapbox-gl-js/v3.28.1/mapbox-gl.js" in html
    assert "connect-src https://api.mapbox.com https://events.mapbox.com" in html
    assert "worker-src blob:" in html
    assert "attributionControl:true" in html
    assert "performanceMetricsCollection:false" in html
    assert token not in analysis.model_dump_json()
    assert token not in export_geojson_analysis(analysis).model_dump_json()
    assert token not in render_markdown_document(analysis.model_dump(mode="json"))
    with pytest.raises(ValueError, match="public token"):
        MapboxOptions("sk.secret", "mapbox://styles/mapbox/streets-v12")
    with pytest.raises(ValueError, match="style"):
        MapboxOptions(token, "javascript:alert(1)")


def test_dashboard_size_and_initial_dom_work_are_bounded_at_maximum_rows(tmp_path: Path) -> None:
    feed = tmp_path / "maximum-rows.csv"
    feed.write_text(
        "\n".join(
            f"2606:4700:{index:x}::/48,US,US-CA,City {index}," for index in range(MAX_DATA_ROWS)
        ),
        encoding="utf-8",
    )
    analysis = analyze_file(feed)
    html = render_html_analysis(analysis)
    assert "rows.slice(page*100,(page+1)*100)" in html
    assert html.count("<tr>") == 1
    assert len(html.encode()) < 72_000_000
