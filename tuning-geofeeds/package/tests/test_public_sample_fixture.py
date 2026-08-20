# Copyright 2026 Fastah Inc.
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType


def _verifier() -> ModuleType:
    product = Path(__file__).parents[1]
    path = product / "tuning-geofeeds" / "scripts" / "verify_public_sample.py"
    spec = importlib.util.spec_from_file_location("verify_public_sample", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def test_public_sample_fixture_integrity_and_provenance() -> None:
    product = Path(__file__).parents[1]
    files = product / "tuning-geofeeds" / "evals" / "files"
    fixture = files / "public-cloudflare-starlink-sample.csv"
    manifest_path = files / "public-cloudflare-starlink-sample.manifest.json"
    verifier = _verifier()

    verifier.verify_fixture(fixture, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["fixture"]["rows"] == 200
    assert manifest["selection"]["finalAllocation"] == {
        "cloudflare": {"US": 50, "non-US": 50},
        "starlink": {"US": 50, "non-US": 50},
    }
    assert [source["sourceId"] for source in manifest["sources"]] == [
        "cloudflare",
        "starlink",
    ]
    manifest_text = json.dumps(manifest)
    authored_prefixes = {
        line.split(",", 1)[0] for line in fixture.read_text(encoding="utf-8").splitlines()
    }
    assert not any(prefix in manifest_text for prefix in authored_prefixes)
    assert re.search(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}/\d+", manifest_text) is None
    assert re.search(r"(?i)(?:[0-9a-f]{0,4}:){2,}[0-9a-f:]+/\d+", manifest_text) is None
