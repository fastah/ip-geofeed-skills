#!/usr/bin/env python3
"""Build or verify the deterministic public geofeed evaluation sample."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pycountry

SEED = "fastah-public-geofeed-sample-v1"
SOURCE_ORDER = ("cloudflare", "starlink")
STRATUM_ORDER = ("US", "non-US")
FINAL_ALLOCATION = {
    "cloudflare": {"US": 50, "non-US": 50},
    "starlink": {"US": 50, "non-US": 50},
}
FIXTURE_NAME = "public-cloudflare-starlink-sample.csv"
MANIFEST_NAME = "public-cloudflare-starlink-sample.manifest.json"


@dataclass(frozen=True)
class Candidate:
    source_id: str
    stratum: str
    physical_line: int
    raw_row: bytes
    raw_row_sha256: str
    half_selection_sha256: str
    cap_selection_sha256: str


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _selection_hash(stage: str, source_id: str, physical_line: int, raw_row: bytes) -> str:
    digest = hashlib.sha256()
    for value in (stage.encode(), SEED.encode(), source_id.encode(), str(physical_line).encode()):
        digest.update(value)
        digest.update(b"\0")
    digest.update(raw_row)
    return digest.hexdigest()


def _strip_line_ending(raw_line: bytes) -> bytes:
    if raw_line.endswith(b"\r\n"):
        return raw_line[:-2]
    if raw_line.endswith((b"\r", b"\n")):
        return raw_line[:-1]
    return raw_line


def _parse_source(source_id: str, path: Path) -> tuple[dict[str, list[Candidate]], dict[str, Any]]:
    pools: dict[str, list[Candidate]] = defaultdict(list)
    rejected: dict[str, list[int]] = defaultdict(list)
    physical_lines = data_rows = 0
    with path.open("rb") as source:
        for physical_line, raw_line in enumerate(source, 1):
            physical_lines = physical_line
            raw_row = _strip_line_ending(raw_line)
            try:
                text = raw_row.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                rejected["invalidUtf8"].append(physical_line)
                continue
            if not text.strip():
                rejected["blank"].append(physical_line)
                continue
            if text.lstrip().startswith("#"):
                rejected["comment"].append(physical_line)
                continue
            data_rows += 1
            try:
                parsed = list(csv.reader([text], strict=True))
            except csv.Error:
                rejected["malformedCsv"].append(physical_line)
                continue
            if len(parsed) != 1 or len(parsed[0]) != 5:
                rejected["fieldCountNotFive"].append(physical_line)
                continue
            if text.count(",") != 4:
                rejected["authoredRowNotFourCommas"].append(physical_line)
                continue
            country = parsed[0][1].strip().upper()
            if len(country) != 2 or pycountry.countries.get(alpha_2=country) is None:
                rejected["countryNotIsoAlpha2"].append(physical_line)
                continue
            stratum = "US" if country == "US" else "non-US"
            pools[stratum].append(
                Candidate(
                    source_id=source_id,
                    stratum=stratum,
                    physical_line=physical_line,
                    raw_row=raw_row,
                    raw_row_sha256=_sha256_bytes(raw_row),
                    half_selection_sha256=_selection_hash(
                        "half", source_id, physical_line, raw_row
                    ),
                    cap_selection_sha256=_selection_hash("cap", source_id, physical_line, raw_row),
                )
            )
    summary = {
        "physicalLines": physical_lines,
        "sourceDataRows": data_rows,
        "parseableCountryRows": sum(len(pool) for pool in pools.values()),
        "rejectedRows": {
            reason: {"count": len(lines), "physicalLines": lines}
            for reason, lines in sorted(rejected.items())
        },
    }
    return pools, summary


def _select(
    pools: dict[str, list[Candidate]], source_id: str
) -> tuple[list[Candidate], dict[str, Any]]:
    selected: list[Candidate] = []
    strata: dict[str, Any] = {}
    for stratum in STRATUM_ORDER:
        pool = pools[stratum]
        half_count = len(pool) // 2
        half = sorted(pool, key=lambda row: (row.half_selection_sha256, row.physical_line))[
            :half_count
        ]
        allocation = FINAL_ALLOCATION[source_id][stratum]
        if len(half) < allocation:
            raise ValueError(
                f"{source_id} {stratum} has {len(half)} half-selected rows, needs {allocation}"
            )
        capped = sorted(half, key=lambda row: (row.cap_selection_sha256, row.physical_line))[
            :allocation
        ]
        capped.sort(key=lambda row: row.physical_line)
        selected.extend(capped)
        strata[stratum] = {
            "eligibleRows": len(pool),
            "halfSelectionRows": half_count,
            "finalAllocationRows": allocation,
        }
    return selected, strata


def _safe_acquisition(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "requestedUrl": record["requestedUrl"],
        "finalUrl": record["finalUrl"],
        "retrievedAtUtc": record["retrievedAtUtc"],
        "completedAtUtc": record["completedAtUtc"],
        "safeResponseHeaders": record["safeResponseHeaders"],
        "rawSha256": record["rawSha256"],
        "rawBytes": record["rawBytes"],
        "declaredCharset": record["declaredCharset"],
        "utf8Status": record["utf8Status"],
        "redirectCount": len(record["redirectAndDnsChecks"]) - 1,
        "publicDnsValidatedHops": len(record["redirectAndDnsChecks"]),
    }


def build_fixture(snapshot_dir: Path, acquisition_path: Path, output_dir: Path) -> None:
    acquisition = {
        item["sourceId"]: item for item in json.loads(acquisition_path.read_text(encoding="utf-8"))
    }
    final_rows: list[Candidate] = []
    source_records: list[dict[str, Any]] = []
    for source_id in SOURCE_ORDER:
        snapshot = snapshot_dir / f"{source_id}.csv"
        raw = snapshot.read_bytes()
        record = acquisition[source_id]
        if len(raw) != record["rawBytes"] or _sha256_bytes(raw) != record["rawSha256"]:
            raise ValueError(f"{source_id} snapshot does not match acquisition metadata")
        raw.decode("utf-8", errors="strict")
        pools, summary = _parse_source(source_id, snapshot)
        selected, strata = _select(pools, source_id)
        selected_records = []
        for row in selected:
            selected_records.append(
                {
                    "sourcePhysicalLine": row.physical_line,
                    "sha256": row.raw_row_sha256,
                }
            )
        final_rows.extend(selected)
        source_records.append(
            {
                "sourceId": source_id,
                **_safe_acquisition(record),
                **summary,
                "strata": strata,
                "selectedRows": selected_records,
            }
        )

    fixture_bytes = b"".join(row.raw_row + b"\n" for row in final_rows)
    available_after_half = sum(
        stratum["halfSelectionRows"]
        for source in source_records
        for stratum in source["strata"].values()
    )
    fixture = output_dir / FIXTURE_NAME
    manifest_path = output_dir / MANIFEST_NAME
    fixture.write_bytes(fixture_bytes)
    manifest = {
        "schemaVersion": "1.0",
        "acquisitionControls": {
            "transport": "HTTPS only, including every redirect; downgrade forbidden",
            "publicDns": "Every resolved address at every hop required to be globally routable",
            "ambientCredentials": "disabled",
            "ambientProxy": "disabled",
            "redirectLimit": 3,
            "perReadTimeoutSeconds": 15,
            "overallDeadlineSeconds": 60,
            "maximumBytesPerSource": 67108864,
            "decoding": "Declared UTF-8 accepted; absent charset decoded as strict UTF-8",
        },
        "fixture": {
            "path": f"evals/files/{FIXTURE_NAME}",
            "bytes": len(fixture_bytes),
            "rows": len(final_rows),
            "sha256": _sha256_bytes(fixture_bytes),
        },
        "selection": {
            "seed": SEED,
            "algorithm": (
                "For each source and normalized ISO alpha-2 country stratum (US or non-US), "
                "select floor(50%) by the lowest SHA-256 of stage, seed, source ID, physical "
                "line number, and authored raw row bytes separated by NUL. Select the fixed "
                "final allocation from that half by the analogous cap-stage hash, restore "
                "physical-line order within each stratum, then concatenate sources in "
                "cloudflare/starlink order and strata in US/non-US order."
            ),
            "duplicateRows": (
                "Physical line number is hashed, so byte-identical rows remain distinct."
            ),
            "countryNormalization": (
                "Surrounding whitespace removed and alpha-2 uppercased for "
                "classification only; authored rows are unchanged."
            ),
            "availableAfterHalfSelectionRows": available_after_half,
            "preferredCapRows": 200,
            "finalCapRows": len(final_rows),
            "finalAllocation": FINAL_ALLOCATION,
            "capDecision": (
                "The preferred round 200-row cap is below the available half-selection total; "
                "50 rows per source-by-country stratum preserve both sources and both strata."
            ),
            "representativeness": (
                "The equal 50-row source-by-stratum allocation is a compact evaluation fixture, "
                "not a statistically representative estimate of either source or the public "
                "Internet."
            ),
        },
        "sources": source_records,
        "provenanceAndRights": (
            "Rows were retrieved from the documented public HTTPS endpoints. Endpoint availability "
            "and source naming are provenance, not independent validation or an assertion of "
            "license, "
            "ownership, endorsement, or redistribution rights. Review source terms before external "
            "redistribution; complete source snapshots are intentionally not committed."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8"
    )


def verify_fixture(fixture: Path, manifest_path: Path, snapshot_dir: Path | None = None) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fixture_bytes = fixture.read_bytes()
    expected = manifest["fixture"]
    if (
        len(fixture_bytes) != expected["bytes"]
        or _sha256_bytes(fixture_bytes) != expected["sha256"]
    ):
        raise ValueError("fixture digest or size mismatch")
    lines = fixture_bytes.splitlines()
    if len(lines) != expected["rows"]:
        raise ValueError("fixture row count mismatch")
    selected = [row for source in manifest["sources"] for row in source["selectedRows"]]
    if len(selected) != len(lines):
        raise ValueError("selected-row manifest count mismatch")
    for fixture_row, (raw_row, metadata) in enumerate(zip(lines, selected, strict=True), 1):
        parsed = list(csv.reader([raw_row.decode("utf-8", errors="strict")], strict=True))
        if len(parsed) != 1 or len(parsed[0]) != 5 or raw_row.count(b",") != 4:
            raise ValueError(f"fixture row {fixture_row} is not an exact five-field row")
        if metadata["sha256"] != _sha256_bytes(raw_row):
            raise ValueError(f"fixture row {fixture_row} metadata mismatch")
    if snapshot_dir is not None:
        acquisition = snapshot_dir / "acquisition.json"
        with tempfile.TemporaryDirectory(prefix="public-sample-rebuild-") as directory:
            temporary = Path(directory)
            build_fixture(snapshot_dir, acquisition, temporary)
            if (temporary / FIXTURE_NAME).read_bytes() != fixture_bytes:
                raise ValueError("snapshot reconstruction differs from committed fixture")
            reconstructed = json.loads((temporary / MANIFEST_NAME).read_text(encoding="utf-8"))
            if reconstructed != manifest:
                raise ValueError("snapshot reconstruction differs from committed manifest")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--snapshot-dir", type=Path, required=True)
    build.add_argument("--acquisition", type=Path, required=True)
    build.add_argument("--output-dir", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("--fixture", type=Path, required=True)
    verify.add_argument("--manifest", type=Path, required=True)
    verify.add_argument("--snapshot-dir", type=Path)
    arguments = parser.parse_args()
    try:
        if arguments.command == "build":
            build_fixture(arguments.snapshot_dir, arguments.acquisition, arguments.output_dir)
        else:
            verify_fixture(arguments.fixture, arguments.manifest, arguments.snapshot_dir)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
