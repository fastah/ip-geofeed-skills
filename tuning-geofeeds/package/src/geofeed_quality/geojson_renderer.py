# Copyright 2026 Fastah Inc.
"""Rich per-row GeoJSON projection of validated Analysis IR.

One feature is emitted for every row that has a canonical prefix. Each feature
carries the row's declared geography, a declaration-depth classification
(country/region/city/none), finding summaries, typed ASN/organization/routing
associations, and MCP H3 cell identifiers. Geometry follows the
regions-over-points principle: the MCP best-match bounding box is preferred and
the center point is the fallback, so coarse declarations render as areas rather
than false-precision points; geometry is null when no MCP evidence exists and
is never invented. The property set remains an allowlist: source URLs and
comments, publisher and RDAP identifiers, raw MCP messages, correction data,
rank, radius, and population weight are never projected.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from .models import (
    AddressFamily,
    Analysis,
    ASNOrganizationAssociation,
    ASNRegistrationAssociation,
    McpObservation,
    McpPlaceMatch,
    Model,
    PrefixValue,
    RoutingOriginAssociation,
    RowRecord,
)
from .schema import validate_document

GEOJSON_ATTRIBUTION = "Contains information derived from GeoNames (https://www.geonames.org/)."


class GeoJsonGeometry(Model):
    type: Literal["Point", "Polygon"]
    coordinates: list[Any]

    @model_validator(mode="after")
    def validate_coordinates(self) -> GeoJsonGeometry:
        if self.type == "Point":
            if not _valid_point(self.coordinates):
                raise ValueError("GeoJSON Point must be a valid [longitude, latitude] pair")
        elif not _valid_polygon(self.coordinates):
            raise ValueError("GeoJSON Polygon must be a closed valid bounding-box ring")
        return self


class GeoJsonDeclaredLocation(Model):
    country: str = ""
    region: str = ""
    city: str = ""
    postalCode: str = ""


class GeoJsonFindingSummary(Model):
    ruleId: str
    category: str
    severity: Literal["error", "warning", "info"]


class GeoJsonOriginGroup(Model):
    asns: list[int]
    asSet: bool = False


class GeoJsonAsnAssociation(Model):
    kind: Literal["routing_origin_snapshot", "asn_organization_snapshot", "asn_registration"]
    matchedPrefix: str | None = None
    originGroups: list[GeoJsonOriginGroup] = Field(default_factory=list)
    asn: int | None = Field(default=None, ge=0, le=4_294_967_295)
    asName: str | None = None
    organizationName: str | None = None
    organizationCountry: str | None = None
    asnSourceRegistry: str | None = None


class GeoJsonMcpEvidence(Model):
    status: str
    placeType: str
    placeName: str
    countryName: str
    countryCode: str
    regionName: str
    regionCode: str
    timezone: str
    centerLongLat: list[float] = Field(default_factory=list)


class GeoJsonProperties(Model):
    # Local Analysis row identifier; this is not the Fastah MCP wire rowKey.
    rowId: str = Field(pattern="^row-[0-9]+$")
    prefix: str
    addressFamily: Literal["ipv4", "ipv6"] | None = None
    parseStatus: str
    rowState: str
    declared: GeoJsonDeclaredLocation = Field(default_factory=GeoJsonDeclaredLocation)
    declarationDepth: Literal["none", "country", "region", "city"]
    geometryRole: Literal["best_match_point", "best_match_bounding_box", "none"]
    findingCount: int = Field(ge=0)
    highestSeverity: Literal["error", "warning", "info", "none"]
    findings: list[GeoJsonFindingSummary] = Field(default_factory=list)
    asnAssociations: list[GeoJsonAsnAssociation] = Field(default_factory=list)
    h3Cells: list[str] = Field(default_factory=list)
    mcp: GeoJsonMcpEvidence | None = None


class GeoJsonFeature(Model):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: GeoJsonGeometry | None = None
    properties: GeoJsonProperties


class GeoJsonFeatureCollection(Model):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[GeoJsonFeature]
    attribution: list[str] = Field(default_factory=lambda: [GEOJSON_ATTRIBUTION])


def _valid_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _valid_point(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(_valid_number(item) for item in value)
        and -180 <= value[0] <= 180
        and -90 <= value[1] <= 90
    )


def _valid_bbox(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 4
        and all(_valid_number(item) for item in value)
        and -180 <= value[0] <= value[2] <= 180
        and -90 <= value[1] <= value[3] <= 90
    )


def _valid_polygon(value: object) -> bool:
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], list):
        return False
    ring = value[0]
    return len(ring) == 5 and ring[0] == ring[-1] and all(_valid_point(point) for point in ring)


def _bbox_polygon(bbox: list[float]) -> list[list[list[float]]]:
    west, south, east, north = bbox
    return [[[west, south], [east, south], [east, north], [west, north], [west, south]]]


def _highest_severity(
    severities: dict[str, str], finding_ids: list[str]
) -> Literal["error", "warning", "info", "none"]:
    for severity in ("error", "warning", "info"):
        if any(severities.get(finding_id) == severity for finding_id in finding_ids):
            return severity
    return "none"


def _declared_location(row: RowRecord) -> GeoJsonDeclaredLocation:
    location = row.location
    if location is None:
        return GeoJsonDeclaredLocation()
    return GeoJsonDeclaredLocation(
        country=location.country,
        region=location.region,
        city=location.city,
        postalCode=location.postal_code,
    )


def declaration_depth(row: RowRecord) -> Literal["none", "country", "region", "city"]:
    """Publisher declaration depth for a row, shared by all visual projections."""
    location = row.location
    if location is None:
        return "none"
    if location.city:
        return "city"
    if location.region:
        return "region"
    if location.country:
        return "country"
    return "none"


def _address_family(prefix: PrefixValue) -> Literal["ipv4", "ipv6"] | None:
    if prefix.address_family == AddressFamily.IPV4:
        return "ipv4"
    if prefix.address_family == AddressFamily.IPV6:
        return "ipv6"
    return None


def _asn_associations(
    association_ids: list[str], associations_by_id: dict[str, Any]
) -> list[GeoJsonAsnAssociation]:
    projected: list[GeoJsonAsnAssociation] = []
    for association_id in association_ids:
        association = associations_by_id[association_id]
        if isinstance(association, RoutingOriginAssociation):
            projected.append(
                GeoJsonAsnAssociation(
                    kind=association.kind,
                    matchedPrefix=association.matched_prefix,
                    originGroups=[
                        GeoJsonOriginGroup(asns=group.asns, asSet=group.as_set)
                        for group in association.origin_groups
                    ],
                )
            )
        elif isinstance(association, ASNOrganizationAssociation):
            projected.append(
                GeoJsonAsnAssociation(
                    kind=association.kind,
                    asn=association.asn,
                    asName=association.as_name,
                    organizationName=association.organization_name,
                    organizationCountry=association.organization_country,
                    asnSourceRegistry=association.asn_source_registry,
                )
            )
        elif isinstance(association, ASNRegistrationAssociation):
            projected.append(
                GeoJsonAsnAssociation(
                    kind=association.kind,
                    asn=association.asn,
                    organizationName=association.organization_name,
                )
            )
    return projected


def _mcp_evidence(observation: McpObservation, match: McpPlaceMatch) -> GeoJsonMcpEvidence:
    return GeoJsonMcpEvidence(
        status=observation.status.value,
        placeType=match.place_type.value,
        placeName=match.place_name,
        countryName=match.country_name,
        countryCode=match.country_code,
        regionName=match.region_name,
        regionCode=match.region_code,
        timezone=match.timezone,
        centerLongLat=list(match.center_long_lat),
    )


def export_geojson_analysis(analysis: Analysis) -> GeoJsonFeatureCollection:
    features: list[GeoJsonFeature] = []
    severities = {finding.id: finding.severity.value for finding in analysis.findings}
    findings_by_id = {finding.id: finding for finding in analysis.findings}
    associations_by_id = {
        association.id: association for association in analysis.enrichment.asn_associations
    }
    mcp_by_row = {
        observation.target_row_id: observation
        for observation in analysis.enrichment.mcp_observations
    }
    for row in analysis.rows:
        prefix_value = row.prefix
        prefix = prefix_value.canonical if prefix_value and prefix_value.canonical else None
        if prefix is None or prefix_value is None:
            continue
        finding_summaries = [
            GeoJsonFindingSummary(
                ruleId=findings_by_id[finding_id].rule_id,
                category=findings_by_id[finding_id].category.value,
                severity=findings_by_id[finding_id].severity.value,
            )
            for finding_id in row.finding_ids
            if finding_id in findings_by_id
        ]
        observation = mcp_by_row.get(row.id)
        match = observation.matches[0] if observation and observation.matches else None
        geometry: GeoJsonGeometry | None = None
        geometry_role: Literal["best_match_point", "best_match_bounding_box", "none"] = "none"
        if match is not None:
            # Regions over points: render the declared/matched extent as an area
            # first so coarse declarations keep their statistical honesty; the
            # center point is only a fallback when no usable bbox exists.
            if _valid_bbox(match.bounding_box):
                geometry = GeoJsonGeometry(
                    type="Polygon", coordinates=_bbox_polygon(match.bounding_box)
                )
                geometry_role = "best_match_bounding_box"
            elif _valid_point(match.center_long_lat):
                geometry = GeoJsonGeometry(type="Point", coordinates=list(match.center_long_lat))
                geometry_role = "best_match_point"
        properties = GeoJsonProperties(
            rowId=row.id,
            prefix=prefix,
            addressFamily=_address_family(prefix_value),
            parseStatus=row.parse_status.value,
            rowState=row.state.value,
            declared=_declared_location(row),
            declarationDepth=declaration_depth(row),
            geometryRole=geometry_role,
            findingCount=len(row.finding_ids),
            highestSeverity=_highest_severity(severities, row.finding_ids),
            findings=finding_summaries,
            asnAssociations=_asn_associations(row.asn_association_ids, associations_by_id),
            h3Cells=list(match.h3_cells) if match is not None else [],
            mcp=_mcp_evidence(observation, match) if observation is not None and match else None,
        )
        features.append(GeoJsonFeature(id=row.id, geometry=geometry, properties=properties))
    return GeoJsonFeatureCollection(features=features)


def export_geojson_document(document: Any) -> dict[str, Any]:
    validate_document(document)
    analysis = Analysis.model_validate(document)
    return export_geojson_analysis(analysis).model_dump(mode="json")


def export_geojson_file(path: Path | str) -> dict[str, Any]:
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    return export_geojson_document(document)
