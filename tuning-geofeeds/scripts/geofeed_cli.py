#!/usr/bin/env python3
# Copyright 2026 Fastah Inc.
"""Run the bundled analyzer without relying on the current working directory."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import venv
from collections.abc import Callable
from pathlib import Path
from typing import cast

REINSTALL_MESSAGE = (
    "error: this tuning-geofeeds installation is incomplete. The skill directory "
    "must contain scripts/geofeed_cli.py and package/pyproject.toml. Some hosts "
    "strip bundled binaries when installing a single skill directory. Reinstall "
    "from the repository bundle root (for example: amp skill add "
    "fastah/ip-geofeed-skills, or the canonical parent directory), not from the "
    "tuning-geofeeds subdirectory, then retry."
)


def package_root() -> Path:
    skill_root = Path(__file__).resolve().parents[1]
    bundled = skill_root / "package"
    # A distributable skill always contains package/. Never fall through to a
    # host checkout when that bundle is present but incomplete or damaged.
    candidates = (bundled,) if bundled.exists() else (skill_root.parent,)
    for candidate in candidates:
        if (candidate / "pyproject.toml").is_file() and (
            candidate / "src" / "geofeed_quality"
        ).is_dir():
            return candidate
    raise SystemExit(REINSTALL_MESSAGE)


def _venv_interpreter(venv_path: Path) -> Path:
    return venv_path / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _bootstrap(work_value: str) -> int:
    """Create or reuse the work-directory venv and install the bundled package.

    Stdlib-only by design: this runs before the analyzer (and Pydantic) import.
    It automates the virtual environment and dependency installation only;
    obtaining a final Python 3.14+ interpreter remains a host or user step.
    """
    work = Path(work_value).resolve()
    work.mkdir(parents=True, exist_ok=True)
    venv_path = work / ".venv"
    interpreter = _venv_interpreter(venv_path)
    if not interpreter.is_file():
        print(f"Creating virtual environment at {venv_path} ...", flush=True)
        venv.EnvBuilder(with_pip=True, clear=False).create(venv_path)
    if not interpreter.is_file():
        raise SystemExit(f"error: virtual environment interpreter not found at {interpreter}")
    root = package_root()
    runtime_source = work / "tuning-geofeeds-runtime"
    if runtime_source.exists():
        shutil.rmtree(runtime_source)
    shutil.copytree(root, runtime_source)
    print("Installing the bundled analyzer (non-interactive) ...", flush=True)
    subprocess.run(
        [str(interpreter), "-m", "pip", "install", "--quiet", str(runtime_source)],
        check=True,
    )
    launcher = Path(__file__).resolve()
    print(f"PYTHON={interpreter}")
    print(f'Next: "{interpreter}" "{launcher}" --help')
    return 0


def main() -> int:
    if sys.version_info < (3, 14):  # noqa: UP036 - portable runtime guard is intentional
        raise SystemExit("error: tuning-geofeeds requires Python 3.14 or newer")
    if sys.version_info.releaselevel != "final":
        raise SystemExit(
            "error: tuning-geofeeds requires a final Python 3.14 or newer release; "
            f"found prerelease {sys.version.split()[0]}. Release candidates are "
            "rejected on purpose. Fix: install a final release — for example "
            "`uv python install 3.14` (upgrade uv first if it only offers rc "
            "builds), then rerun with `--bootstrap`."
        )
    arguments = sys.argv[1:]
    if len(arguments) == 2 and arguments[0] == "--bootstrap":
        return _bootstrap(arguments[1])
    root = package_root()
    if arguments == ["--print-package-root"]:
        print(root)
        return 0
    sys.path.insert(0, str(root / "src"))
    try:
        from geofeed_quality.cli import main as cli_main
    except ModuleNotFoundError as error:
        raise SystemExit(
            "error: analyzer dependencies are unavailable. Run "
            f'"{sys.executable}" "{Path(__file__).resolve()}" --bootstrap '
            "/absolute/path/to/work-directory, then retry with the printed "
            "interpreter; see references/setup.md for the manual path."
        ) from error
    return cast(Callable[[list[str]], int], cli_main)(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
