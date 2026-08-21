# Copyright 2026 Fastah Inc.
"""Offline CAIDA routing-origin and AS-organization enrichment."""

from __future__ import annotations

import gzip
import hashlib
import ipaddress
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, cast

import maxminddb
from pydantic import JsonValue

from .models import (
    Analysis,
    ASNAssociationProvenance,
    ASNOrganizationAssociation,
    ASNOriginGroup,
    Evidence,
    EvidenceType,
    RoutingOriginAssociation,
)

ROUTE_SOURCE_NAME = "CAIDA RouteViews Prefix-to-AS snapshot"
ROUTE_SOURCE_URL = "https://publicdata.caida.org/datasets/routing/routeviews-prefix2as/README.txt"
ORG_SOURCE_NAME = "CAIDA AS Organizations snapshot"
ORG_SOURCE_URL = "https://catalog.caida.org/dataset/as_organizations/README.txt"


@dataclass(frozen=True)
class OriginGroup:
    asns: tuple[int, ...]
    as_set: bool


@dataclass(frozen=True)
class RouteMatch:
    matched_prefix: str
    origin_groups: tuple[OriginGroup, ...]


@dataclass(frozen=True)
class ASNRecord:
    asn: int
    as_name: str
    org_id: str
    source: str


@dataclass(frozen=True)
class OrganizationRecord:
    org_id: str
    name: str
    country: str
    source: str


class CaidaLookup(Protocol):
    route_provenance: ASNAssociationProvenance
    organization_provenance: ASNAssociationProvenance

    def route_origins(self, address: str) -> RouteMatch | None: ...

    def asn_info(self, asn: int) -> ASNRecord | None: ...

    def organization_info(self, org_id: str) -> OrganizationRecord | None: ...


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_datetime(snapshot_id: str) -> datetime:
    return datetime.strptime(snapshot_id, "%Y%m%d").replace(tzinfo=UTC)


class CaidaSnapshotDatabase:
    """Read the assets packaged by gen2/pkg/ip-data-caida-asn-org."""

    def __init__(self, route_path: Path, organization_path: Path) -> None:
        route_bytes = route_path.read_bytes()
        if route_bytes.startswith(b"version https://git-lfs.github.com/spec/v1"):
            raise ValueError(f"CAIDA route MMDB is an unhydrated Git LFS pointer: {route_path}")
        self._reader = maxminddb.open_database(route_path)
        metadata = self._reader.metadata()
        if metadata.database_type != "Fastah-CAIDA-Route-Origin":
            self.close()
            raise ValueError("CAIDA route MMDB has an unexpected database type")
        route_snapshot = datetime.fromtimestamp(metadata.build_epoch, tz=UTC).strftime("%Y%m%d")
        route_sources = [
            source.strip()
            for source in metadata.description.get("sources", "").split(",")
            if source.strip()
        ] or [ROUTE_SOURCE_URL]
        with gzip.open(organization_path, "rt", encoding="utf-8") as source:
            indexes = cast(dict[str, Any], json.load(source))
        organization_snapshot = str(indexes["snapshot"])
        self._asns = {
            int(item["asn"]): ASNRecord(
                asn=int(item["asn"]),
                as_name=str(item.get("as_name", "")),
                org_id=str(item.get("org_id", "")),
                source=str(item.get("source", "")),
            )
            for item in cast(list[dict[str, Any]], indexes["asns"])
        }
        self._organizations = {
            str(item["org_id"]): OrganizationRecord(
                org_id=str(item["org_id"]),
                name=str(item.get("name", "")),
                country=str(item.get("country", "")),
                source=str(item.get("source", "")),
            )
            for item in cast(list[dict[str, Any]], indexes["orgs"])
        }
        self.route_provenance = ASNAssociationProvenance(
            source_name=ROUTE_SOURCE_NAME,
            source_url=ROUTE_SOURCE_URL,
            snapshot_sources=route_sources,
            snapshot_id=route_snapshot,
            snapshot_sha256=_sha256(route_path),
        )
        self.organization_provenance = ASNAssociationProvenance(
            source_name=ORG_SOURCE_NAME,
            source_url=ORG_SOURCE_URL,
            snapshot_sources=[ORG_SOURCE_URL],
            snapshot_id=organization_snapshot,
            snapshot_sha256=_sha256(organization_path),
        )

    def route_origins(self, address: str) -> RouteMatch | None:
        value, prefix_length = self._reader.get_with_prefix_len(address)
        if value is None:
            return None
        record = cast(Mapping[str, Any], value)
        network = ipaddress.ip_network(f"{address}/{prefix_length}", strict=False)
        groups = tuple(
            OriginGroup(
                asns=tuple(int(asn) for asn in cast(list[Any], group["asns"])),
                as_set=bool(group.get("as_set", False)),
            )
            for group in cast(list[Mapping[str, Any]], record["origins"])
        )
        return RouteMatch(str(network), groups)

    def asn_info(self, asn: int) -> ASNRecord | None:
        return self._asns.get(asn)

    def organization_info(self, org_id: str) -> OrganizationRecord | None:
        return self._organizations.get(org_id)

    def close(self) -> None:
        self._reader.close()

    def __enter__(self) -> CaidaSnapshotDatabase:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def enrich_analysis(analysis: Analysis, database: CaidaLookup) -> Analysis:
    """Attach snapshot evidence without changing RFC 8805 validity or location values."""
    if analysis.enrichment.asn_associations:
        return Analysis.model_validate(analysis.model_dump(mode="json"))
    enriched = analysis.model_copy(deep=True)
    enriched.configuration.enrichment_enabled = True
    for row in enriched.rows:
        if (
            not row.prefix
            or not row.prefix.canonical
            or row.prefix.is_publicly_routable is not True
        ):
            continue
        network = ipaddress.ip_network(row.prefix.canonical, strict=True)
        route = database.route_origins(str(network.network_address))
        if route is None:
            continue
        route_evidence = Evidence(
            id=f"evidence-{len(enriched.evidence) + 1:06d}",
            type=EvidenceType.ROUTING_ORIGIN,
            source=database.route_provenance.source_name,
            observed_at=_snapshot_datetime(database.route_provenance.snapshot_id),
            target_ids=[row.id],
            values={
                "matched_prefix": route.matched_prefix,
                "snapshot_id": database.route_provenance.snapshot_id,
                "snapshot_sha256": database.route_provenance.snapshot_sha256,
                "source_url": database.route_provenance.source_url,
                "snapshot_sources": cast(
                    list[JsonValue], database.route_provenance.snapshot_sources
                ),
            },
        )
        enriched.evidence.append(route_evidence)
        routing = RoutingOriginAssociation(
            id=f"asn-association-{len(enriched.enrichment.asn_associations) + 1:06d}",
            target_row_id=row.id,
            matched_prefix=route.matched_prefix,
            origin_groups=[
                ASNOriginGroup(asns=list(group.asns), as_set=group.as_set)
                for group in route.origin_groups
            ],
            provenance=database.route_provenance,
            evidence_ids=[route_evidence.id],
        )
        enriched.enrichment.asn_associations.append(routing)
        row.asn_association_ids.append(routing.id)
        row.evidence_ids.append(route_evidence.id)
        for asn in dict.fromkeys(asn for group in route.origin_groups for asn in group.asns):
            as_record = database.asn_info(asn)
            org_record = (
                database.organization_info(as_record.org_id)
                if as_record is not None and as_record.org_id
                else None
            )
            if as_record is None and org_record is None:
                continue
            org_evidence = Evidence(
                id=f"evidence-{len(enriched.evidence) + 1:06d}",
                type=EvidenceType.ASN_ORGANIZATION,
                source=database.organization_provenance.source_name,
                observed_at=_snapshot_datetime(database.organization_provenance.snapshot_id),
                target_ids=[row.id],
                values={
                    "asn": asn,
                    "snapshot_id": database.organization_provenance.snapshot_id,
                    "snapshot_sha256": database.organization_provenance.snapshot_sha256,
                    "source_url": database.organization_provenance.source_url,
                    "snapshot_sources": cast(
                        list[JsonValue], database.organization_provenance.snapshot_sources
                    ),
                },
            )
            enriched.evidence.append(org_evidence)
            organization = ASNOrganizationAssociation(
                id=f"asn-association-{len(enriched.enrichment.asn_associations) + 1:06d}",
                target_row_id=row.id,
                routing_association_id=routing.id,
                asn=asn,
                as_name=as_record.as_name or None if as_record else None,
                organization_id=as_record.org_id or None if as_record else None,
                organization_name=org_record.name or None if org_record else None,
                organization_country=org_record.country or None if org_record else None,
                asn_source_registry=as_record.source or None if as_record else None,
                organization_source_registry=org_record.source or None if org_record else None,
                provenance=database.organization_provenance,
                evidence_ids=[org_evidence.id],
            )
            enriched.enrichment.asn_associations.append(organization)
            row.asn_association_ids.append(organization.id)
            row.evidence_ids.append(org_evidence.id)

    enriched.statistics.asn_associations = len(enriched.enrichment.asn_associations)
    enriched.statistics.enrichment_observations = (
        len(enriched.enrichment.observations)
        + len(enriched.enrichment.mcp_observations)
        + len(enriched.enrichment.asn_associations)
    )
    return Analysis.model_validate(enriched.model_dump(mode="json"))
