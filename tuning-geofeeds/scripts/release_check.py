#!/usr/bin/env python3
# Copyright 2026 Fastah Inc.
"""Build and verify a deterministic private portable release layout."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".py",
    ".svg",
    ".toml",
    ".txt",
    "",
}
ALLOWED_BINARY_PATHS = {
    "tuning-geofeeds/package/assets/design/assets/fonts/Sora-VariableFont_wght.ttf",
}
SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(rb"gh[pousr]_[A-Za-z0-9]{30,}"),
    "Slack token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
}
MARKDOWN_LINK = re.compile(r"\[[^]]*\]\(([^)]+)\)")
COPYRIGHT_NOTICE = "# Copyright 2026 Fastah Inc."


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _product_root() -> Path:
    return _skill_root().parent


def _repository_root() -> Path:
    return _product_root().parents[1]


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def _copy_tree(source: Path, target: Path) -> None:
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if (
            "__pycache__" in relative.parts
            or any(part.endswith(".egg-info") for part in relative.parts)
            or path.suffix == ".pyc"
            or relative.parts[:1] == ("workspace",)
        ):
            continue
        if path.is_symlink():
            raise ValueError(f"release source must not contain symlinks: {path}")
        if path.is_file():
            _copy_file(path, target / relative)


def _build(target: Path) -> Path:
    skill = _skill_root()
    product = _product_root()
    repository = _repository_root()
    release_skill = target / "tuning-geofeeds"
    release_skill.mkdir(parents=True)
    _copy_file(skill / "SKILL.md", release_skill / "SKILL.md")
    for directory in ("references", "scripts", "evals"):
        _copy_tree(skill / directory, release_skill / directory)
    # Host adapters are development-time generators, not installed skill runtime.
    (release_skill / "scripts" / "package_hosts.py").unlink(missing_ok=True)

    package = release_skill / "package"
    _copy_file(product / "pyproject.toml", package / "pyproject.toml")
    _copy_file(product / "Makefile", package / "Makefile")
    _copy_file(skill / "assets" / "package-README.md", package / "README.md")
    _copy_tree(product / "src", package / "src")
    _copy_tree(product / "schema", package / "schema")
    _copy_tree(product / "tests", package / "tests")
    for relative in (
        Path("design/assets/fonts/Sora-VariableFont_wght.ttf"),
        Path("design/assets/logos/fastah-lockup-ondark.svg"),
    ):
        _copy_file(repository / relative, package / "assets" / relative)
    return target


def _frontmatter(skill: Path) -> dict[str, str]:
    text = (skill / "SKILL.md").read_text(encoding="utf-8")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("SKILL.md requires YAML frontmatter")
    header = text.split("\n---\n", 1)[0].splitlines()[1:]
    values: dict[str, str] = {}
    for line in header:
        if line.startswith("  ") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key] = value.strip().strip('"')
    return values


def _validate_skill(skill: Path) -> None:
    metadata = _frontmatter(skill)
    name = metadata.get("name", "")
    description = metadata.get("description", "")
    compatibility = metadata.get("compatibility", "")
    if name != skill.name or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("skill name must match its valid parent directory")
    if not 1 <= len(description) <= 1024:
        raise ValueError("skill description must contain 1-1024 characters")
    if metadata.get("license") != "Apache-2.0":
        raise ValueError("skill license must be Apache-2.0")
    if not 1 <= len(compatibility) <= 500 or "Python 3.14+" not in compatibility:
        raise ValueError("compatibility must require Python 3.14+")
    body = (skill / "SKILL.md").read_text(encoding="utf-8")
    if len(body.splitlines()) >= 500:
        raise ValueError("SKILL.md must remain below 500 lines")
    if len(body) >= 15_000 or len(re.findall(r"\S+", body)) >= 5_000:
        raise ValueError("SKILL.md must remain conservatively below 5,000 tokens")


def _validate_evals(skill: Path) -> None:
    definition = json.loads((skill / "evals" / "evals.json").read_text(encoding="utf-8"))
    if definition.get("skill_name") != "tuning-geofeeds":
        raise ValueError("eval skill_name must be tuning-geofeeds")
    cases = definition.get("evals")
    if not isinstance(cases, list) or len(cases) < 8:
        raise ValueError("eval inventory requires at least eight cases")
    ids = [case.get("id") for case in cases]
    slugs = [case.get("slug") for case in cases]
    if len(ids) != len(set(ids)) or len(slugs) != len(set(slugs)):
        raise ValueError("eval IDs and slugs must be unique")
    for case in cases:
        for key in ("prompt", "expected_output", "files", "assertions"):
            if key not in case:
                raise ValueError(f"eval {case.get('slug')} is missing {key}")
        if not case["assertions"]:
            raise ValueError(f"eval {case['slug']} needs objective assertions")
        for relative in case["files"]:
            path = skill / relative
            if not path.is_file() or not path.resolve().is_relative_to(skill.resolve()):
                raise ValueError(f"eval fixture is missing or escapes the skill: {relative}")
    triggers = json.loads((skill / "evals" / "trigger-queries.json").read_text(encoding="utf-8"))
    positives = sum(item["should_trigger"] is True for item in triggers)
    negatives = sum(item["should_trigger"] is False for item in triggers)
    if positives < 5 or negatives < 3:
        raise ValueError(
            "trigger inventory requires at least five positive and three negative cases"
        )
    if {item["split"] for item in triggers} != {"train", "validation"}:
        raise ValueError("trigger queries require fixed train and validation splits")


def _validate_markdown_links(root: Path) -> None:
    for markdown in sorted(root.rglob("*.md")):
        for target in MARKDOWN_LINK.findall(markdown.read_text(encoding="utf-8")):
            if "://" in target or target.startswith(("#", "mailto:")):
                continue
            relative = target.split("#", 1)[0]
            if relative and not (markdown.parent / relative).resolve().exists():
                raise ValueError(f"broken local Markdown link in {markdown}: {target}")


def _validate_files(root: Path) -> None:
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"release must not contain symlinks: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        for label, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                raise ValueError(f"possible {label} in {relative}")
        if any(
            relative == allowed or relative.endswith(f"/{allowed}")
            for allowed in ALLOWED_BINARY_PATHS
        ):
            continue
        if path.suffix not in TEXT_SUFFIXES:
            raise ValueError(f"unexpected binary or file type in release: {relative}")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(f"required text file is not UTF-8: {relative}") from error
        if path.suffix == ".py":
            lines = content.decode("utf-8").splitlines()
            notice_index = 1 if lines and lines[0].startswith("#!") else 0
            if len(lines) <= notice_index or lines[notice_index] != COPYRIGHT_NOTICE:
                raise ValueError(
                    f"published Python source missing exact copyright notice: {relative}"
                )
    prohibited = (".env", "__pycache__", ".pyc", "credentials", "node_modules", ".venv")
    for path in root.rglob("*"):
        if any(part in prohibited for part in path.relative_to(root).parts):
            raise ValueError(f"prohibited release path: {path.relative_to(root)}")


def _run_portable_smoke(skill: Path) -> None:
    launcher = skill / "scripts" / "geofeed_cli.py"
    environment = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    package = subprocess.run(
        [sys.executable, str(launcher), "--print-package-root"],
        cwd=skill.parent,
        text=True,
        capture_output=True,
        check=True,
        env=environment,
    ).stdout.strip()
    if Path(package).resolve() != (skill / "package").resolve():
        raise ValueError("released launcher did not resolve the bundled package")
    completed = subprocess.run(
        [sys.executable, str(launcher), "schema", "check"],
        cwd=skill.parent,
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if completed.returncode:
        raise ValueError(f"released schema check failed: {completed.stderr}")
    with tempfile.TemporaryDirectory(prefix="tuning-geofeeds-smoke-") as runtime:
        runtime_root = Path(runtime)
        analysis = runtime_root / "analysis.json"
        dashboard = runtime_root / "dashboard.html"
        geojson = runtime_root / "analysis.geojson"
        commands = (
            (
                "analyze",
                str(skill / "evals" / "files" / "mixed-valid.csv"),
                "--output",
                str(analysis),
            ),
            ("render-html", str(analysis), "--output", str(dashboard)),
            ("export-geojson", str(analysis), "--output", str(geojson)),
        )
        for arguments in commands:
            completed = subprocess.run(
                [sys.executable, str(launcher), *arguments],
                cwd=runtime_root,
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            if completed.returncode:
                raise ValueError(f"released {' '.join(arguments[:1])} failed: {completed.stderr}")
        html = dashboard.read_text(encoding="utf-8")
        if "data:font/ttf;base64," not in html or "data:image/svg+xml;base64," not in html:
            raise ValueError("released HTML did not embed the exact bundled design assets")


def _source_path(relative: Path) -> str:
    parts = relative.parts
    if parts[:1] != ("tuning-geofeeds",):
        raise ValueError(f"unexpected canonical bundle path: {relative}")
    skill_relative = Path(*parts[1:])
    if skill_relative.parts[:1] == ("package",):
        package_relative = Path(*skill_relative.parts[1:])
        if package_relative == Path("README.md"):
            return "tuning-geofeeds/assets/package-README.md"
        if package_relative.parts[:2] == ("assets", "design"):
            return Path(*package_relative.parts[1:]).as_posix()
        return package_relative.as_posix()
    return (Path("tuning-geofeeds") / skill_relative).as_posix()


def _manifest(root: Path) -> dict[str, object]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "bundle-manifest.json":
            continue
        content = path.read_bytes()
        relative = path.relative_to(root)
        files.append(
            {
                "path": relative.as_posix(),
                "source": _source_path(relative),
                "bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return {
        "format_version": "1",
        "bundle": "fastah-netops-tools-agent-skills",
        "skill": "tuning-geofeeds",
        "source_commit": _source_commit(),
        "files": files,
    }


def _source_commit() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=_product_root(),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _file_count(manifest: dict[str, object]) -> int:
    files = manifest.get("files")
    if not isinstance(files, list):
        raise ValueError("release manifest requires a file list")
    return len(files)


def _verify(target: Path) -> dict[str, object]:
    skill = target / "tuning-geofeeds"
    _validate_skill(skill)
    _validate_evals(skill)
    _validate_markdown_links(skill)
    _validate_files(target)
    _run_portable_smoke(skill)
    manifest = _manifest(target)
    (target / "bundle-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-only", action="store_true")
    arguments = parser.parse_args()
    if bool(arguments.output) == arguments.check_only:
        parser.error("choose exactly one of --output or --check-only")
    try:
        if arguments.check_only:
            with tempfile.TemporaryDirectory(prefix="tuning-geofeeds-release-") as temporary:
                target = Path(temporary)
                first = _verify(_build(target))
                with tempfile.TemporaryDirectory(
                    prefix="tuning-geofeeds-release-2-"
                ) as second_temp:
                    second = _verify(_build(Path(second_temp)))
                if first != second:
                    raise ValueError("release layout is not deterministic")
                print(json.dumps({"status": "PASS", "files": _file_count(first)}, sort_keys=True))
            return 0

        output = arguments.output.resolve()
        if output.exists():
            parser.error(f"output already exists: {output}")
        if not output.parent.is_dir():
            parser.error(f"output parent does not exist: {output.parent}")
        with tempfile.TemporaryDirectory(prefix=f".{output.name}.", dir=output.parent) as temporary:
            temporary_root = Path(temporary)
            bundle = _build(temporary_root / "bundle")
            manifest = _verify(bundle)
            os.replace(bundle, output)
        result = {"status": "PASS", "output": str(output), "files": _file_count(manifest)}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
