from __future__ import annotations

import ipaddress
import os
from pathlib import Path

import pytest

from geofeed_quality import MAX_DATA_ROWS, DataRowLimitError, SourceDecodeError, analyze_file
from geofeed_quality.analyzer import _is_fully_public
from geofeed_quality.models import (
    FindingCategory,
    ParseStatus,
    RelationshipType,
    RowKind,
    RowState,
)

FIXTURES = Path(__file__).parent / "fixtures"
GO_PRODUCTION_DENY_PREFIXES = (
    "0.0.0.0/8",
    "0.0.0.0/32",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.0.0.0/24",
    "192.0.0.0/29",
    "192.0.0.8/32",
    "192.0.0.9/32",
    "192.0.0.10/32",
    "192.0.0.170/32",
    "192.0.0.171/32",
    "192.0.2.0/24",
    "192.31.196.0/24",
    "192.52.193.0/24",
    "192.88.99.0/24",
    "192.88.99.2/32",
    "192.168.0.0/16",
    "192.175.48.0/24",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "240.0.0.0/4",
    "255.255.255.255/32",
    "::1/128",
    "::/128",
    "::ffff:0:0/96",
    "64:ff9b::/96",
    "64:ff9b:1::/48",
    "100::/64",
    "100:0:0:1::/64",
    "2001::/23",
    "2001::/32",
    "2001:1::1/128",
    "2001:1::2/128",
    "2001:1::3/128",
    "2001:2::/48",
    "2001:3::/32",
    "2001:4:112::/48",
    "2001:10::/28",
    "2001:20::/28",
    "2001:30::/28",
    "2001:db8::/32",
    "2002::/16",
    "3fff::/20",
    "5f00::/16",
    "2620:4f:8000::/48",
    "fc00::/7",
    "fe80::/10",
)


def _feed(tmp_path: Path, text: str, *, name: str = "feed.csv") -> Path:
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    os.utime(path, (1_700_000_000, 1_700_000_000))
    return path


def test_valid_ipv4_ipv6_host_and_case_normalization() -> None:
    analysis = analyze_file(FIXTURES / "valid.csv")
    data = [row for row in analysis.rows if row.kind == RowKind.DATA]

    assert [row.prefix.canonical for row in data if row.prefix] == [
        "8.8.8.0/24",
        "2606:4700::/48",
        "1.1.1.1/32",
    ]
    assert data[0].location is not None
    assert (data[0].location.country, data[0].location.region) == ("US", "US-CA")
    assert data[1].location is not None
    assert (data[1].location.country, data[1].location.region) == ("GB", "GB-ENG")
    assert data[2].prefix is not None and data[2].prefix.authored_as_host
    assert data[2].location is not None and data[2].location.country == "ZZ"
    assert data[2].state == RowState.VALID_DO_NOT_GEOLOCATE
    assert data[0].state == RowState.VALID_UNRESOLVED
    assert analysis.statistics.resolved_rows == 0
    assert analysis.enrichment.observations == []
    assert analysis.corrections.proposals == []


def test_comments_blanks_inline_comments_and_bom_preserve_lines(tmp_path: Path) -> None:
    path = tmp_path / "bom.csv"
    path.write_bytes(
        b"\xef\xbb\xbf"
        + "# heading\r\n\r\n8.8.8.8,BR,BR-SP,São Paulo, # note\r\n  # comment\r\n".encode()
    )
    analysis = analyze_file(path)

    assert analysis.source.had_utf8_bom
    assert analysis.statistics.physical_lines == 4
    assert analysis.statistics.data_rows == 1
    assert analysis.statistics.comment_lines == 2
    assert analysis.statistics.blank_lines == 1
    assert [row.line_number for row in analysis.rows] == [1, 2, 3, 4]
    assert [row.kind for row in analysis.rows] == [
        RowKind.COMMENT,
        RowKind.BLANK,
        RowKind.DATA,
        RowKind.COMMENT,
    ]
    assert analysis.rows[2].raw_line.endswith("# note")
    assert "# note" not in analysis.rows[2].effective_line
    assert analysis.rows[2].location is not None
    assert analysis.rows[2].location.city == "São Paulo"


def test_only_crlf_lf_and_cr_split_physical_lines(tmp_path: Path) -> None:
    embedded = "A\u0085B\u2028C\u2029D\vE\fF"
    path = _feed(
        tmp_path,
        f"8.8.8.0/24,US,US-CA,{embedded},\r\n"
        f"1.1.1.0/24,US,US-NY,{embedded},\n"
        f"9.9.9.0/24,US,US-VA,{embedded},\r",
    )
    analysis = analyze_file(path)

    assert analysis.statistics.physical_lines == 3
    assert analysis.statistics.data_rows == 3
    assert analysis.source.physical_line_count == 3
    assert [row.line_number for row in analysis.rows] == [1, 2, 3]
    assert all(row.location is not None and row.location.city == embedded for row in analysis.rows)


@pytest.mark.parametrize("terminal", ["\n", "\r", "\r\n"])
def test_terminal_physical_delimiter_does_not_create_a_row(tmp_path: Path, terminal: str) -> None:
    analysis = analyze_file(_feed(tmp_path, f"8.8.8.0/24,US,US-CA,City,{terminal}"))
    assert analysis.statistics.physical_lines == 1
    assert analysis.statistics.data_rows == 1


def test_unicode_separators_cannot_fabricate_rows_or_cross_data_limit(tmp_path: Path) -> None:
    separators = "\u0085\u2028\u2029\v\f" * (MAX_DATA_ROWS + 1)
    analysis = analyze_file(_feed(tmp_path, f"# one physical comment {separators}"))
    assert analysis.statistics.physical_lines == 1
    assert analysis.statistics.comment_lines == 1
    assert analysis.statistics.data_rows == 0


def test_invalid_utf8_is_typed_feed_error(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_bytes(b"8.8.8.0/24,US,,,\xff")
    with pytest.raises(SourceDecodeError, match="byte offset"):
        analyze_file(path)


def test_malformed_csv_and_column_counts_are_retained(tmp_path: Path) -> None:
    path = _feed(
        tmp_path,
        '8.8.8.0/24,US,US-CA,"unterminated\n'
        "1.1.1.0/24,US\n"
        "9.9.9.0/24,US,US-NY,New York,,future,field\n",
    )
    analysis = analyze_file(path)

    assert analysis.statistics.data_rows == 3
    assert analysis.rows[0].parse_status == ParseStatus.MALFORMED
    assert analysis.rows[1].parse_status == ParseStatus.VALID
    assert analysis.rows[2].ignored_fields == ["future", "field"]
    rules = [finding.rule_id for finding in analysis.findings]
    assert "RFC8805.CSV_INVALID" in rules
    assert rules.count("RFC8805.COLUMN_COUNT") == 2
    assert {
        finding.message
        for finding in analysis.findings
        if finding.rule_id == "RFC8805.COLUMN_COUNT"
    } == {
        "RFC 8805 rows should contain four commas to denote five fields, even if the non-IP "
        "Prefix columns are empty"
    }
    assert "OPS.EXTRA_COLUMNS_IGNORED" in rules


def test_host_bits_invalid_but_non_public_is_separate_quality_policy(tmp_path: Path) -> None:
    path = _feed(
        tmp_path,
        "8.8.8.7/24,US,US-CA,City,\n"
        "10.0.0.0/8,US,US-CA,City,\n"
        "2001:db8::/32,US,US-CA,City,\n"
        "126.0.0.0/7,US,US-CA,City,\n"
        "not-a-prefix,US,US-CA,City,\n",
    )
    analysis = analyze_file(path)

    assert analysis.rows[0].prefix is not None
    assert analysis.rows[0].prefix.canonical == "8.8.8.0/24"
    assert analysis.rows[0].state == RowState.INVALID
    host_finding = next(f for f in analysis.findings if f.rule_id == "RFC8805.PREFIX_HOST_BITS")
    assert host_finding.category == FindingCategory.RFC8805_VIOLATION
    policy_findings = [f for f in analysis.findings if f.rule_id == "FASTAH.PREFIX_NOT_PUBLIC"]
    assert len(policy_findings) == 3
    assert all(f.category == FindingCategory.FASTAH_QUALITY_RECOMMENDATION for f in policy_findings)
    assert analysis.rows[1].parse_status == ParseStatus.VALID
    assert analysis.rows[3].prefix is not None
    assert analysis.rows[3].prefix.is_publicly_routable is False
    assert analysis.rows[4].prefix is not None
    assert analysis.rows[4].prefix.canonical is None
    assert analysis.rows[4].state == RowState.INVALID
    assert "RFC8805.PREFIX_INVALID" in {finding.rule_id for finding in analysis.findings}


@pytest.mark.parametrize("prefix", ["240.0.0.0/4", "4000::/3"])
def test_stdlib_reserved_prefixes_are_not_public(prefix: str) -> None:
    network = ipaddress.ip_network(prefix, strict=True)
    assert network.is_reserved
    assert not _is_fully_public(network)


@pytest.mark.parametrize(
    "prefix",
    [
        "192.31.196.0/24",
        "192.52.193.0/24",
        "192.88.99.0/24",
        "192.88.99.2/32",
        "192.175.48.0/24",
        "2620:4f:8000::/48",
    ],
)
def test_go_policy_parity_gaps_are_not_public(prefix: str) -> None:
    assert not _is_fully_public(ipaddress.ip_network(prefix, strict=True))


@pytest.mark.parametrize("prefix", ["8.8.8.0/24", "2606:4700::/48"])
def test_ordinary_public_prefixes_remain_public(prefix: str) -> None:
    assert _is_fully_public(ipaddress.ip_network(prefix, strict=True))


def test_all_production_go_deny_entries_are_not_public() -> None:
    assert len(GO_PRODUCTION_DENY_PREFIXES) == 51
    for prefix in GO_PRODUCTION_DENY_PREFIXES:
        network = ipaddress.ip_network(prefix, strict=True)
        assert not _is_fully_public(network), prefix


def test_duplicate_containment_and_conflict_graph_is_deterministic() -> None:
    analysis = analyze_file(FIXTURES / "relationships.csv")
    types = [relationship.type for relationship in analysis.relationships]

    assert types.count(RelationshipType.DUPLICATE) == 1
    assert types.count(RelationshipType.EQUAL) == 1
    assert types.count(RelationshipType.CONFLICTING_GEOLOCATION) == 1
    assert types.count(RelationshipType.PARENT) == 2
    assert types.count(RelationshipType.CARVED_CHILD) == 2
    parent_pairs = {
        (relation.source_prefix, relation.target_prefix)
        for relation in analysis.relationships
        if relation.type == RelationshipType.PARENT
    }
    assert parent_pairs == {
        ("8.8.0.0/16", "8.8.8.0/24"),
        ("8.8.8.0/24", "8.8.8.0/25"),
    }
    assert "OPS.CONFLICTING_GEOLOCATION" in {f.rule_id for f in analysis.findings}
    duplicate_rows = [
        row for row in analysis.rows if row.prefix and row.prefix.canonical == "8.8.8.0/24"
    ]
    assert len(duplicate_rows) == 3
    assert all(row.state == RowState.INVALID for row in duplicate_rows)


def test_equal_normalized_host_and_prefix_are_not_silently_overwritten(tmp_path: Path) -> None:
    path = _feed(tmp_path, "8.8.8.8,US,US-CA,City,\n8.8.8.8/32,US,US-CA,City,\n")
    analysis = analyze_file(path)
    assert len(analysis.rows) == 2
    assert analysis.relationships[0].type == RelationshipType.EQUAL
    assert analysis.statistics.invalid_rows == 2


def test_output_is_deterministic_for_unchanged_source(tmp_path: Path) -> None:
    path = _feed(tmp_path, "8.8.8.0/24,US,US-CA,City,\n")
    first = analyze_file(path).model_dump_json(indent=2)
    second = analyze_file(path).model_dump_json(indent=2)
    assert first == second


def test_60_000_rows_are_accepted_with_linear_graph_bound(tmp_path: Path) -> None:
    lines = [f"2606:4700:{index:x}::/48,US,US-CA,City," for index in range(MAX_DATA_ROWS)]
    path = _feed(tmp_path, "\n".join(lines) + "\n", name="sixty-thousand.csv")
    analysis = analyze_file(path)

    assert analysis.statistics.data_rows == MAX_DATA_ROWS
    assert analysis.statistics.valid_rows == MAX_DATA_ROWS
    assert len(analysis.relationships) <= analysis.configuration.relationship_limit
    assert len({row.prefix.canonical for row in analysis.rows if row.prefix}) == MAX_DATA_ROWS


def test_60_001_rows_are_rejected_before_ir(tmp_path: Path) -> None:
    line = "8.8.8.8,US,US-CA,City,"
    path = _feed(tmp_path, "\n".join([line] * (MAX_DATA_ROWS + 1)), name="too-large.csv")
    with pytest.raises(DataRowLimitError) as raised:
        analyze_file(path)
    assert raised.value.limit == MAX_DATA_ROWS
    assert raised.value.observed == MAX_DATA_ROWS + 1
    assert raised.value.line_number == MAX_DATA_ROWS + 1
