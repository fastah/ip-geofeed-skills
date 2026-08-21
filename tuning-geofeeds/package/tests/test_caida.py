# Copyright 2026 Fastah Inc.
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from geofeed_quality import analyze_file
from geofeed_quality.caida import (
    ASNRecord,
    OrganizationRecord,
    OriginGroup,
    RouteMatch,
    enrich_analysis,
)
from geofeed_quality.models import Analysis, ASNAssociationProvenance


class FixtureDatabase:
    route_provenance = ASNAssociationProvenance(
        source_name="CAIDA RouteViews fixture",
        source_url="https://example.test/route-readme",
        snapshot_sources=["https://example.test/route-snapshot"],
        snapshot_id="20260819",
        snapshot_sha256="a" * 64,
    )
    organization_provenance = ASNAssociationProvenance(
        source_name="CAIDA AS Organizations fixture",
        source_url="https://example.test/org-readme",
        snapshot_sources=["https://example.test/org-snapshot"],
        snapshot_id="20260801",
        snapshot_sha256="b" * 64,
    )

    def route_origins(self, address: str) -> RouteMatch | None:
        if address == "8.8.8.0":
            return RouteMatch(
                "8.8.8.0/24",
                (OriginGroup((15169,), False), OriginGroup((64500, 64501), True)),
            )
        return None

    def asn_info(self, asn: int) -> ASNRecord | None:
        if asn == 15169:
            return ASNRecord(asn, "GOOGLE", "ORG-GOGL2-RIR", "ARIN")
        return None

    def organization_info(self, org_id: str) -> OrganizationRecord | None:
        if org_id == "ORG-GOGL2-RIR":
            return OrganizationRecord(org_id, "Google LLC", "US", "RIPE")
        return None


def _analysis(tmp_path: Path) -> Analysis:
    source = tmp_path / "feed.csv"
    source.write_text(
        "8.8.8.0/24,US,US-CA,Mountain View,\n2606:4700::/48,US,US-CA,City,\n",
        encoding="utf-8",
    )
    return analyze_file(source)


def test_caida_enrichment_preserves_origin_groups_and_links_orgs(tmp_path: Path) -> None:
    base = _analysis(tmp_path)
    enriched = enrich_analysis(base, FixtureDatabase())

    assert base.enrichment.asn_associations == []
    assert len(enriched.enrichment.asn_associations) == 2
    routing, organization = enriched.enrichment.asn_associations
    assert routing.kind == "routing_origin_snapshot"
    assert routing.matched_prefix == "8.8.8.0/24"
    assert [group.model_dump() for group in routing.origin_groups] == [
        {"asns": [15169], "as_set": False},
        {"asns": [64500, 64501], "as_set": True},
    ]
    assert organization.kind == "asn_organization_snapshot"
    assert organization.routing_association_id == routing.id
    assert organization.organization_name == "Google LLC"
    assert organization.asn_source_registry == "ARIN"
    assert organization.organization_source_registry == "RIPE"
    assert enriched.rows[0].asn_association_ids == [routing.id, organization.id]
    assert enriched.statistics.asn_associations == 2
    assert enriched.statistics.enrichment_observations == 2
    assert enrich_analysis(enriched, FixtureDatabase()) == enriched
    assert Analysis.model_validate_json(enriched.model_dump_json()) == enriched


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda document: document["rows"][0]["asn_association_ids"].append(
                "asn-association-000001"
            ),
            "duplicate ASN association",
        ),
        (
            lambda document: document["enrichment"]["asn_associations"][0].update(
                {"target_row_id": "row-999999"}
            ),
            "invalid row target",
        ),
        (
            lambda document: document["enrichment"]["asn_associations"][1].update(
                {"routing_association_id": "asn-association-999999"}
            ),
            "invalid routing association",
        ),
    ],
)
def test_caida_association_invariants(
    tmp_path: Path, mutation: Callable[[dict[str, Any]], None], message: str
) -> None:
    enriched = enrich_analysis(_analysis(tmp_path), FixtureDatabase())
    document = enriched.model_dump(mode="json")
    mutation(document)
    with pytest.raises(ValidationError, match=message):
        Analysis.model_validate(document)
