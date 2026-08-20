# Copyright 2026 Fastah Inc.
from __future__ import annotations

import subprocess
import sys
import textwrap
import tomllib
from importlib.metadata import version
from pathlib import Path

import pytest
from packaging.version import Version

from geofeed_quality.runtime import MINIMUM_PYTHON, require_supported_python


def test_runtime_floor_is_python_3_14() -> None:
    assert MINIMUM_PYTHON == (3, 14)
    require_supported_python(MINIMUM_PYTHON)
    require_supported_python((MINIMUM_PYTHON[0], MINIMUM_PYTHON[1] + 1))
    unsupported = (MINIMUM_PYTHON[0], MINIMUM_PYTHON[1] - 1)
    with pytest.raises(RuntimeError, match=r"requires Python 3\.14 or newer"):
        require_supported_python(unsupported)
    with pytest.raises(RuntimeError, match=r"requires a final Python 3\.14 or newer release"):
        require_supported_python(MINIMUM_PYTHON, releaselevel="candidate")


def test_package_metadata_matches_runtime_floor() -> None:
    product = Path(__file__).parents[1]
    metadata = tomllib.loads((product / "pyproject.toml").read_text())
    assert metadata["project"]["requires-python"] == ">=3.14"
    assert metadata["tool"]["ruff"]["target-version"] == "py314"
    assert metadata["tool"]["mypy"]["python_version"] == "3.14"
    makefile = (product / "Makefile").read_text(encoding="utf-8")
    assert makefile.count('sys.version_info.releaselevel == "final"') == 2


def test_pycountry_dependency_floor_and_installed_version() -> None:
    metadata = tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    assert "pycountry>=26.2.16" in metadata["project"]["dependencies"]
    assert "pydantic>=2.11,<3" in metadata["project"]["dependencies"]
    assert Version(version("pycountry")) >= Version("26.2.16")


def test_agent_launcher_rejects_prerelease_before_importing_pydantic() -> None:
    launcher = Path(__file__).parents[1] / "tuning-geofeeds" / "scripts" / "geofeed_cli.py"
    script = textwrap.dedent(
        f"""
        import importlib.util
        import sys

        class PrereleaseVersion(tuple):
            releaselevel = "candidate"

        spec = importlib.util.spec_from_file_location("prerelease_launcher", {str(launcher)!r})
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.sys.version_info = PrereleaseVersion((3, 14, 0, "candidate", 2))
        module.sys.version = "3.14.0rc2"
        module.sys.argv = [{str(launcher)!r}, "--help"]
        assert "pydantic" not in sys.modules
        try:
            module.main()
        except SystemExit as error:
            assert "requires a final Python 3.14 or newer release" in str(error)
        else:
            raise AssertionError("prerelease launcher did not exit")
        assert "pydantic" not in sys.modules
        """
    )
    completed = subprocess.run(
        [sys.executable, "-c", script],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_agent_launcher_help_exposes_examples_and_exit_meanings() -> None:
    launcher = Path(__file__).parents[1] / "tuning-geofeeds" / "scripts" / "geofeed_cli.py"
    completed = subprocess.run(
        [sys.executable, str(launcher), "--help"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert "examples:" in completed.stdout
    assert "exit status:" in completed.stdout
    assert "Requested output files are created atomically and are never overwritten." in (
        completed.stdout
    )
