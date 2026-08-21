# Copyright 2026 Fastah Inc.
from __future__ import annotations

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

APACHE_2_LICENSE_SHA256 = "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30"


def _packager() -> ModuleType:
    product = Path(__file__).parents[1]
    scripts = product / "tuning-geofeeds" / "scripts"
    path = scripts / "package_hosts.py"
    spec = importlib.util.spec_from_file_location("package_hosts", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(scripts))
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(scripts))
        del sys.modules[spec.name]
        sys.modules.pop("release_check", None)
    return module


def _config() -> dict[str, Any]:
    path = Path(__file__).parents[1] / "tuning-geofeeds" / "packaging" / "release.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_public_root_is_generated_from_canonical_metadata(tmp_path: Path) -> None:
    packager = _packager()
    config = _config()

    inventory = packager._stage_public_root(tmp_path, config)
    paths = {item["path"] for item in inventory}

    assert paths == {
        ".github/plugin/plugin.json",
        ".vscode/mcp.json",
        "CONTRIBUTING.md",
        "LICENSE",
        "MIGRATION.md",
        "README.md",
        "marketplace-metadata.json",
        "mcp-plugin.json",
    }
    assert all(item["bytes"] > 0 and len(item["sha256"]) == 64 for item in inventory)
    license_entry = next(item for item in inventory if item["path"] == "LICENSE")
    assert license_entry == {
        "path": "LICENSE",
        "bytes": 11358,
        "sha256": APACHE_2_LICENSE_SHA256,
        "source": "tuning-geofeeds/packaging/public/LICENSE",
    }
    assert (
        (tmp_path / "LICENSE")
        .read_text(encoding="utf-8")
        .startswith(
            "\n                                 Apache License\n"
            "                           Version 2.0, January 2004\n"
        )
    )
    packager.release_check._validate_files(tmp_path)

    readme = (tmp_path / "README.md").read_text(encoding="utf-8")
    for text in (
        "Fastah NetOps Tools helps you check a public IP geofeed",
        "Python | 3.14 or newer",
        "Skill and plugin: `0.2.0`",
        "Analyzer and Analysis schema: `0.5.0` / `0.5.0`",
        "MCP response contract: `1.0`",
        "`do_not_geolocate`",
        "around 225 MB",
        "remarks: Geofeed https://...",
        "https://mcp.fastah.ai/terms-of-use.txt",
        "upload the CSV",
        "source.sha256",
        "valid empty FeatureCollection",
    ):
        assert text in readme
    assert "{{" not in readme
    assert "make skill-public-stage" not in readme
    contributing = (tmp_path / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "local-file-first GitHub Skill is public" in contributing
    assert "Marketplace release remains blocked" in contributing
    migration = (tmp_path / "MIGRATION.md").read_text(encoding="utf-8")
    assert "`tuning-geofeeds` supersedes the legacy `geofeed-tuner`" in migration
    assert "public migration removed the legacy skill" in migration
    assert "future public migration" not in migration

    plugin = json.loads((tmp_path / ".github" / "plugin" / "plugin.json").read_text())
    assert plugin["name"] == config["pluginName"]
    assert plugin["version"] == config["version"]
    assert plugin["repository"] == config["repository"]
    assert plugin["skills"] == ["./tuning-geofeeds/"]

    discovery = "\n".join(
        (tmp_path / relative).read_text(encoding="utf-8")
        for relative in (
            ".github/plugin/plugin.json",
            ".vscode/mcp.json",
            "mcp-plugin.json",
        )
    )
    assert "geofeed-tuner" not in discovery
    assert "https://mcp.global.fastah.ai/mcp" not in discovery
    assert "https://mcp.fastah.ai/mcp" in discovery


def test_public_root_rejects_outdated_global_mcp_discovery(tmp_path: Path) -> None:
    packager = _packager()
    config = deepcopy(_config())
    config["mcp"]["url"] = "https://mcp.global.fastah.ai/mcp"

    with pytest.raises(ValueError, match="legacy active skill or endpoint"):
        packager._stage_public_root(tmp_path, config)


def test_canonical_public_license_exists_with_exact_apache_2_content() -> None:
    packager = _packager()
    license_path = (
        Path(__file__).parents[1] / "tuning-geofeeds" / "packaging" / "public" / "LICENSE"
    )

    assert license_path.is_file()
    assert packager._digest(license_path) == APACHE_2_LICENSE_SHA256
    assert packager.PUBLIC_LICENSE_SHA256 == APACHE_2_LICENSE_SHA256


def test_release_copy_excludes_generated_egg_info(tmp_path: Path) -> None:
    packager = _packager()
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "package").mkdir(parents=True)
    (source / "package" / "module.py").write_text("value = 1\n", encoding="utf-8")
    generated = source / "package" / "example.egg-info"
    generated.mkdir()
    (generated / "PKG-INFO").write_text("Requires-Python: >=3.14\n", encoding="utf-8")

    packager.release_check._copy_tree(source, target)

    assert (target / "package" / "module.py").is_file()
    assert not (target / "package" / "example.egg-info").exists()


def test_release_validation_requires_exact_source_notice(tmp_path: Path) -> None:
    packager = _packager()
    plain = tmp_path / "plain.py"
    executable = tmp_path / "executable.py"
    notice = "# Copyright 2026 Fastah Inc."
    plain.write_text(f"{notice}\nvalue = 1\n", encoding="utf-8")
    executable.write_text(f"#!/usr/bin/env python3\n{notice}\nvalue = 1\n", encoding="utf-8")

    packager.release_check._validate_files(tmp_path)

    plain.write_text("value = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing exact copyright notice"):
        packager.release_check._validate_files(tmp_path)
