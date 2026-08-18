from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError as PydanticValidationError

from geofeed_quality import analyze_file
from geofeed_quality.models import (
    Analysis,
    PublisherProfile,
    RdapAssessment,
    RdapFailureCode,
)
from geofeed_quality.rdap import (
    AuthoritativeRdapClient,
    BootstrapRegistry,
    HttpResponse,
    RdapRequestError,
    RdapRuntimeConfig,
    enrich_analysis,
)
from geofeed_quality.schema import validate_document

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

IPV4_BOOTSTRAP = {
    "services": [
        [["8.0.0.0/8"], ["https://rdap.arin.example/registry/", "http://ignored/"]],
        [["8.8.0.0/16"], ["https://rdap.apnic.example/"]],
        [["9.0.0.0/8"], ["http://insecure.example/"]],
    ]
}
IPV6_BOOTSTRAP = {"services": [[["2606:4700::/32"], ["https://rdap.arin.example/registry/"]]]}


def _network_document(
    *,
    start: str = "8.8.0.0",
    end: str = "8.8.255.255",
    organization: str = "Example Networks",
) -> dict[str, object]:
    return {
        "objectClassName": "ip network",
        "startAddress": start,
        "endAddress": end,
        "ipVersion": "v4",
        "handle": "NET-8-8-0-0-1",
        "name": "EXAMPLE-NET",
        "type": "DIRECT ALLOCATION",
        "entities": [
            {
                "handle": "EXAMPLE-ORG",
                "roles": ["registrant"],
                "vcardArray": [
                    "vcard",
                    [
                        ["fn", {}, "text", organization],
                        ["org", {}, "text", organization],
                        ["email", {}, "text", "sensitive@example.test"],
                        ["tel", {}, "text", "+1-555-0100"],
                    ],
                ],
                "publicIds": [
                    {"type": "Autnum", "identifier": "AS15169"},
                    {"type": "Domain", "identifier": "example.net"},
                    {"type": "Email", "identifier": "private@example.test"},
                ],
            }
        ],
        "remarks": [{"description": ["irrelevant payload must not persist"]}],
    }


class FixtureTransport:
    def __init__(self, responses: dict[str, HttpResponse | RdapRequestError]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str, config: RdapRuntimeConfig) -> HttpResponse:
        self.calls.append(url)
        for fragment, response in self.responses.items():
            if fragment in url:
                if isinstance(response, RdapRequestError):
                    raise response
                return response
        raise AssertionError(f"unexpected URL: {url}")


def _response(
    document: object,
    *,
    status: int = 200,
    content_type: str = "application/rdap+json",
    **headers: str,
) -> HttpResponse:
    return HttpResponse(
        url="https://rdap.apnic.example/ip/8.8.8.0/24",
        status_code=status,
        headers={"content-type": content_type, **headers},
        content=json.dumps(document).encode(),
    )


def _client(transport: FixtureTransport) -> AuthoritativeRdapClient:
    return AuthoritativeRdapClient(
        BootstrapRegistry.from_documents(IPV4_BOOTSTRAP, IPV6_BOOTSTRAP),
        transport,
        config=RdapRuntimeConfig(max_concurrency=2, min_interval_per_rir_seconds=0),
        now=lambda: NOW,
    )


def test_iana_bootstrap_selects_ipv4_ipv6_and_longest_match() -> None:
    registry = BootstrapRegistry.from_documents(IPV4_BOOTSTRAP, IPV6_BOOTSTRAP)
    ipv4_specific = registry.select("8.8.8.0/24")
    ipv4_general = registry.select("8.7.0.0/16")
    ipv6 = registry.select("2606:4700::/48")
    assert ipv4_specific is not None and ipv4_specific.endpoint == "https://rdap.apnic.example/"
    assert (
        ipv4_general is not None and ipv4_general.endpoint == "https://rdap.arin.example/registry/"
    )
    assert ipv6 is not None and ipv6.endpoint == "https://rdap.arin.example/registry/"
    insecure = registry.select("9.0.0.0/24")
    assert insecure is not None and insecure.insecure_only


def test_insecure_bootstrap_service_is_rejected_without_http_request() -> None:
    transport = FixtureTransport({})
    result = _client(transport).lookup("9.0.0.0/24")
    assert result.failure_code == RdapFailureCode.INSECURE_SERVICE_URL
    assert transport.calls == []


def test_per_rir_scheduler_enforces_configured_start_interval() -> None:
    transport = FixtureTransport({"rdap.apnic.example": _response(_network_document())})
    current = [0.0]
    sleeps: list[float] = []

    def monotonic() -> float:
        return current[0]

    def sleep(delay: float) -> None:
        sleeps.append(delay)
        current[0] += delay

    client = AuthoritativeRdapClient(
        BootstrapRegistry.from_documents(IPV4_BOOTSTRAP, IPV6_BOOTSTRAP),
        transport,
        config=RdapRuntimeConfig(max_concurrency=2, min_interval_per_rir_seconds=2),
        now=lambda: NOW,
        monotonic=monotonic,
        sleep=sleep,
    )
    assert client.lookup("8.8.8.0/24").failure_code is None
    assert client.lookup("8.8.9.0/24").failure_code is None
    assert sleeps == [2.0]


def test_profile_normalization_and_identifier_consistency() -> None:
    profile = PublisherProfile(
        organization_name="  EXAMPLE   Networks ",
        asn="15169",
        rdap_entity_handle="example-org",
        rir_organization_id=" example-org ",
        domain="EXAMPLE.NET.",
    )
    assert profile.model_dump() == {
        "version": "1",
        "organization_name": "example networks",
        "asn": "AS15169",
        "rdap_entity_handle": "EXAMPLE-ORG",
        "rir_organization_id": "EXAMPLE-ORG",
        "domain": "example.net",
        "evidence_ids": [],
    }
    transport = FixtureTransport({"rdap.apnic.example": _response(_network_document())})
    enriched = enrich_analysis(
        analyze_file(FIXTURES / "relationships.csv"), _client(transport), profile
    )
    observation = next(
        item for item in enriched.enrichment.observations if item.requested_prefix == "8.8.8.0/24"
    )
    assert observation.assessment == RdapAssessment.CONSISTENT
    assert observation.conflicting_profile_fields == []
    assert set(observation.matched_profile_fields) == {
        "organization_name",
        "asn",
        "rdap_entity_handle",
        "rir_organization_id",
        "domain",
    }
    assert "does not prove legal ownership" in observation.explanation


def test_no_profile_is_unverified_and_absence_is_not_conflict() -> None:
    transport = FixtureTransport({"rdap.apnic.example": _response(_network_document())})
    analysis = analyze_file(FIXTURES / "relationships.csv")
    no_profile = enrich_analysis(analysis, _client(transport))
    assert no_profile.enrichment.observations[0].assessment == RdapAssessment.UNVERIFIED

    no_comparable = PublisherProfile(domain="publisher-without-rdap-domain.example")
    sparse_transport = FixtureTransport(
        {"rdap.apnic.example": _response({**_network_document(), "entities": []})}
    )
    sparse = enrich_analysis(analysis, _client(sparse_transport), no_comparable)
    assert sparse.enrichment.observations[0].assessment == RdapAssessment.UNVERIFIED
    assert sparse.enrichment.observations[0].conflicting_profile_fields == []


@pytest.mark.parametrize("nested", [False, True])
def test_roleless_entities_are_not_comparable_or_retained(nested: bool) -> None:
    document = _network_document(organization="Roleless Sensitive Organization")
    entities = cast(list[dict[str, Any]], document["entities"])
    roleless = entities[0]
    roleless.pop("roles")
    if nested:
        document["entities"] = [{"roles": ["technical"], "entities": [roleless]}]
    transport = FixtureTransport({"rdap.apnic.example": _response(document)})
    enriched = enrich_analysis(
        analyze_file(FIXTURES / "relationships.csv"),
        _client(transport),
        PublisherProfile(organization_name="Roleless Sensitive Organization"),
    )

    observation = enriched.enrichment.observations[0]
    assert observation.assessment == RdapAssessment.UNVERIFIED
    assert observation.selected_entities == []
    assert observation.matched_profile_fields == []
    assert observation.conflicting_profile_fields == []
    serialized = enriched.model_dump_json()
    assert "Roleless Sensitive Organization" not in serialized
    assert "sensitive@example.test" not in serialized


def test_affirmative_identifier_mismatch_is_conflicting() -> None:
    transport = FixtureTransport({"rdap.apnic.example": _response(_network_document())})
    enriched = enrich_analysis(
        analyze_file(FIXTURES / "relationships.csv"),
        _client(transport),
        PublisherProfile(rdap_entity_handle="OTHER-ORG"),
    )
    observation = enriched.enrichment.observations[0]
    assert observation.assessment == RdapAssessment.CONFLICTING
    assert observation.conflicting_profile_fields == ["rdap_entity_handle"]
    assert "not a legal ownership conclusion" in observation.explanation


@pytest.mark.parametrize(
    ("response", "code", "retryable"),
    [
        (
            RdapRequestError(RdapFailureCode.TIMEOUT, "timeout", retryable=True),
            RdapFailureCode.TIMEOUT,
            True,
        ),
        (
            _response({}, status=429, **{"retry-after": "120"}),
            RdapFailureCode.RATE_LIMITED,
            True,
        ),
        (
            _response({}, content_type="text/html"),
            RdapFailureCode.INVALID_CONTENT_TYPE,
            False,
        ),
        (
            _response({}, status=404),
            RdapFailureCode.HTTP_ERROR,
            False,
        ),
        (
            _response(["not", "an", "object"]),
            RdapFailureCode.MALFORMED_RESPONSE,
            False,
        ),
        (
            RdapRequestError(RdapFailureCode.RESPONSE_TOO_LARGE, "oversized"),
            RdapFailureCode.RESPONSE_TOO_LARGE,
            False,
        ),
    ],
)
def test_failures_are_sanitized_unavailable_and_retry_aware(
    response: HttpResponse | RdapRequestError, code: RdapFailureCode, retryable: bool
) -> None:
    result = _client(FixtureTransport({"rdap.apnic.example": response})).lookup("8.8.8.0/24")
    assert result.failure_code == code
    assert result.retryable is retryable
    if code == RdapFailureCode.RATE_LIMITED:
        assert result.retry_after_seconds == 120


def test_oversized_transport_response_is_rejected_by_client_boundary() -> None:
    response = HttpResponse(
        url="https://rdap.apnic.example/ip/8.8.8.0/24",
        status_code=200,
        headers={"content-type": "application/rdap+json"},
        content=b"x" * 33,
    )
    client = AuthoritativeRdapClient(
        BootstrapRegistry.from_documents(IPV4_BOOTSTRAP, IPV6_BOOTSTRAP),
        FixtureTransport({"rdap.apnic.example": response}),
        config=RdapRuntimeConfig(response_byte_limit=32, min_interval_per_rir_seconds=0),
        now=lambda: NOW,
    )
    assert client.lookup("8.8.8.0/24").failure_code == RdapFailureCode.RESPONSE_TOO_LARGE


def test_covering_non_network_object_is_malformed() -> None:
    document = _network_document()
    document["objectClassName"] = "entity"
    result = _client(FixtureTransport({"rdap.apnic.example": _response(document)})).lookup(
        "8.8.8.0/24"
    )
    assert result.failure_code == RdapFailureCode.MALFORMED_RESPONSE
    assert result.network is None
    assert result.entities == ()


def test_malformed_response_domain_identifier_is_isolated_and_not_retained() -> None:
    malformed_domain = f"{'a' * 64}.example"
    document = _network_document()
    entities = cast(list[dict[str, Any]], document["entities"])
    public_ids = cast(list[dict[str, str]], entities[0]["publicIds"])
    public_ids[1]["identifier"] = malformed_domain
    result = _client(FixtureTransport({"rdap.apnic.example": _response(document)})).lookup(
        "8.8.8.0/24"
    )

    assert result.failure_code == RdapFailureCode.MALFORMED_RESPONSE
    assert result.network is None
    assert result.entities == ()
    assert malformed_domain not in repr(result)


def test_dedup_cache_privacy_and_schema_roundtrip() -> None:
    transport = FixtureTransport({"rdap.apnic.example": _response(_network_document())})
    client = _client(transport)
    analysis = enrich_analysis(
        analyze_file(FIXTURES / "relationships.csv"),
        client,
        PublisherProfile(organization_name="Example Networks"),
    )
    assert len(analysis.enrichment.observations) == 3
    assert sum("8.8.8.0/24" in call for call in transport.calls) == 1
    assert client.lookup("8.8.8.0/24").cached
    assert analysis.enrichment.publisher_profile is not None
    assert analysis.enrichment.publisher_profile.evidence_ids
    serialized = analysis.model_dump_json()
    for prohibited in (
        "sensitive@example.test",
        "private@example.test",
        "+1-555-0100",
        "irrelevant payload must not persist",
        "vcardArray",
        '"fn"',
    ):
        assert prohibited not in serialized
    validate_document(analysis.model_dump(mode="json"))
    assert Analysis.model_validate_json(serialized) == analysis

    tampered = analysis.model_dump(mode="json")
    tampered["enrichment"]["observations"][0]["target_row_ids"] = ["row-999999"]
    with pytest.raises(PydanticValidationError, match="invalid row target"):
        Analysis.model_validate(tampered)


def test_partial_success_does_not_change_base_row_validity(tmp_path: Path) -> None:
    feed = tmp_path / "partial.csv"
    feed.write_text("8.8.8.0/24,US,US-CA,City,\n2606:4700::/48,US,US-CA,City,\n")
    transport = FixtureTransport(
        {
            "8.8.8.0/24": _response(_network_document()),
            "2606:4700::/48": RdapRequestError(
                RdapFailureCode.TIMEOUT, "secret upstream detail", retryable=True
            ),
        }
    )
    base = analyze_file(feed)
    enriched = enrich_analysis(base, _client(transport))
    assert [item.assessment for item in enriched.enrichment.observations] == [
        RdapAssessment.UNVERIFIED,
        RdapAssessment.UNAVAILABLE,
    ]
    assert [row.state for row in enriched.rows] == [row.state for row in base.rows]
    assert "secret upstream detail" not in enriched.model_dump_json()


def test_malformed_rdap_prefix_does_not_abort_other_prefixes_or_output(tmp_path: Path) -> None:
    malformed_domain = f"{'x' * 64}.example"
    malformed = _network_document(
        start="2606:4700::", end="2606:4700:ffff:ffff:ffff:ffff:ffff:ffff"
    )
    malformed["ipVersion"] = "v6"
    malformed_entities = cast(list[dict[str, Any]], malformed["entities"])
    malformed_ids = cast(list[dict[str, str]], malformed_entities[0]["publicIds"])
    malformed_ids[1]["identifier"] = malformed_domain
    feed = tmp_path / "mixed-malformed.csv"
    feed.write_text("8.8.8.0/24,US,US-CA,City,\n2606:4700::/48,US,US-CA,City,\n")
    transport = FixtureTransport(
        {
            "8.8.8.0/24": _response(_network_document()),
            "2606:4700::/48": _response(malformed),
        }
    )
    base = analyze_file(feed)
    enriched = enrich_analysis(base, _client(transport), PublisherProfile(domain="example.net"))

    assert [item.assessment for item in enriched.enrichment.observations] == [
        RdapAssessment.CONSISTENT,
        RdapAssessment.UNAVAILABLE,
    ]
    assert enriched.enrichment.observations[1].failure_code == RdapFailureCode.MALFORMED_RESPONSE
    assert [row.state for row in enriched.rows] == [row.state for row in base.rows]
    serialized = enriched.model_dump_json()
    assert malformed_domain not in serialized
    assert "sensitive@example.test" not in serialized
    validate_document(enriched.model_dump(mode="json"))
    assert Analysis.model_validate_json(serialized) == enriched


@pytest.mark.live
@pytest.mark.skipif(os.environ.get("FASTAH_RDAP_LIVE") != "1", reason="set FASTAH_RDAP_LIVE=1")
def test_live_rdap_smoke_is_opt_in() -> None:
    client = AuthoritativeRdapClient.from_iana(
        config=RdapRuntimeConfig(max_concurrency=1, min_interval_per_rir_seconds=1)
    )
    result = client.lookup("8.8.8.0/24")
    assert result.failure_code is None
    assert result.network is not None
