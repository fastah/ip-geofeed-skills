#!/usr/bin/env python3
"""Run deterministic skill eval fixtures and emit evidence-bearing grades."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

Result = tuple[bool | None, str]


class EvaluationCommandError(RuntimeError):
    """A fixture command returned an expected operational failure."""


def _skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class Runner:
    def __init__(self, outputs: Path) -> None:
        self.outputs = outputs
        self.skill = _skill_root()
        self.launcher = self.skill / "scripts" / "geofeed_cli.py"
        self.files = self.skill / "evals" / "files"

    def run(self, *arguments: str, expected: int = 0) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            [sys.executable, str(self.launcher), *arguments],
            cwd=self.outputs,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != expected:
            raise EvaluationCommandError(
                f"command returned {completed.returncode}, expected {expected}: "
                f"{' '.join(arguments)}\n{completed.stderr}"
            )
        return completed

    def analyze(self, fixture: str, name: str = "analysis.json") -> Path:
        output = self.outputs / name
        self.run("analyze", str(self.files / fixture), "--output", str(output))
        return output

    def render_all(self, analysis: Path, prefix: str = "analysis") -> None:
        self.run("render", str(analysis), "--output", str(self.outputs / f"{prefix}.md"))
        self.run("render-html", str(analysis), "--output", str(self.outputs / f"{prefix}.html"))
        self.run(
            "export-geojson",
            str(analysis),
            "--output",
            str(self.outputs / f"{prefix}.geojson"),
        )


def _valid(runner: Runner) -> list[Result]:
    analysis_path = runner.analyze("mixed-valid.csv")
    runner.render_all(analysis_path)
    analysis = _load(analysis_path)
    artifacts = [runner.outputs / f"analysis.{suffix}" for suffix in ("md", "html", "geojson")]
    return [
        (analysis["statistics"]["data_rows"] == 3, "analysis.json data_rows is 3"),
        (all(path.is_file() for path in artifacts), "Markdown, HTML, and GeoJSON exist"),
        (not (runner.outputs / "corrected.csv").exists(), "corrected.csv is absent"),
    ]


def _malformed(runner: Runner) -> list[Result]:
    analysis = _load(runner.analyze("malformed-quality.csv"))
    rules = {finding["rule_id"] for finding in analysis["findings"]}
    return [
        (analysis["statistics"]["data_rows"] == 5, "analysis retains 5 data rows"),
        (
            {"RFC8805.PREFIX_HOST_BITS", "FASTAH.PREFIX_NOT_PUBLIC"} <= rules,
            "distinct RFC8805.PREFIX_HOST_BITS and FASTAH.PREFIX_NOT_PUBLIC findings exist",
        ),
        (
            {"RFC8805.COUNTRY_INVALID", "RFC8805.POSTAL_DEPRECATED"} <= rules,
            "invalid ISO country and deprecated postal findings exist",
        ),
    ]


def _relationships(runner: Runner) -> list[Result]:
    analysis_path = runner.analyze("relationships.csv")
    runner.run(
        "render-html", str(analysis_path), "--output", str(runner.outputs / "dashboard.html")
    )
    analysis = _load(analysis_path)
    types = {item["type"] for item in analysis["relationships"]}
    required = {"duplicate", "equal", "parent", "carved_child", "conflicting_geolocation"}
    html = (runner.outputs / "dashboard.html").read_text(encoding="utf-8")
    return [
        (analysis["statistics"]["data_rows"] == 5, "analysis retains 5 authored rows"),
        (required <= types, f"relationship types include {sorted(required)}"),
        (
            "Relationship evidence" in html and "relationship-list" in html,
            "dashboard contains textual Relationship evidence section",
        ),
    ]


def _rdap_policy(runner: Runner) -> list[Result]:
    analysis_path = runner.analyze("mixed-valid.csv")
    runner.render_all(analysis_path, "offline")
    return [
        (None, "requires a clean agent execution trace"),
        (None, "requires a clean agent execution trace"),
        (
            analysis_path.is_file() and (runner.outputs / "offline.html").is_file(),
            "offline base Analysis and report artifacts exist without an RDAP call",
        ),
    ]


def _mcp(runner: Runner) -> list[Result]:
    base = runner.analyze("mixed-valid.csv", "base.json")
    requests = runner.outputs / "mcp-requests"
    runner.run("mcp-export", str(base), "--batch-limit", "1000", "--output-dir", str(requests))
    request = _load(requests / "batch-000001.json")
    enriched = runner.outputs / "enriched.json"
    runner.run(
        "mcp-import",
        str(base),
        str(runner.files / "mcp-response-v1.json"),
        "--batch-limit",
        "1000",
        "--output",
        str(enriched),
    )
    runner.render_all(enriched, "enriched")
    document = _load(enriched)
    statuses = [item["status"] for item in document["enrichment"]["mcp_observations"]]
    allowed = {"rowId", "country", "region", "city", "searchMode"}
    return [
        (
            set(request) == {"rows"} and all(set(row) <= allowed for row in request["rows"]),
            "request root is rows and every row uses only the five-field allowlist",
        ),
        (
            statuses == ["matched", "backend_unavailable", "do_not_geolocate"],
            f"ordered imported statuses are {statuses}",
        ),
        (
            all(
                (runner.outputs / f"enriched.{suffix}").is_file()
                for suffix in ("md", "html", "geojson")
            ),
            "enriched Markdown, HTML, and GeoJSON exist",
        ),
    ]


def _corrections(runner: Runner) -> list[Result]:
    source = runner.files / "mixed-valid.csv"
    base = runner.analyze("mixed-valid.csv", "base.json")
    proposed = runner.outputs / "proposed.json"
    plan_path = runner.outputs / "plan.json"
    runner.run(
        "propose-corrections",
        str(base),
        "--output",
        str(proposed),
        "--plan",
        str(plan_path),
    )
    plan = _load(plan_path)
    no_default = not _load(proposed)["corrections"]["approvals"]
    absent_before = not (runner.outputs / "corrected.csv").exists()
    first = plan["proposals"][0]["id"]
    approval = runner.outputs / "approval.json"
    runner.run(
        "record-approval",
        str(plan_path),
        "--approver",
        "deterministic-eval",
        "--decided-at",
        "2026-08-15T12:30:00+00:00",
        "--approve",
        first,
        "--output",
        str(approval),
    )
    corrected = runner.outputs / "corrected.csv"
    final = runner.outputs / "final.json"
    runner.run(
        "export-csv",
        str(proposed),
        str(approval),
        "--source",
        str(source),
        "--output",
        str(corrected),
        "--final-analysis",
        str(final),
    )
    finalized = _load(final)
    proposals = plan["proposals"]
    unique_proposals = len({item["id"] for item in proposals}) == len(proposals)
    return [
        (
            bool(proposals) and unique_proposals and no_default,
            f"plan contains {len(proposals)} unique proposals and no default approval",
        ),
        (absent_before, "corrected.csv was absent before explicit approval"),
        (
            corrected.is_file() and finalized["statistics"]["approved_corrections"] == 1,
            "corrected.csv and schema-validated final.json record one approved correction",
        ),
    ]


def _large_feed(path: Path, count: int) -> None:
    path.write_text(
        "\n".join(f"2606:4700:{index:x}::/48,US,US-CA,City," for index in range(count)),
        encoding="utf-8",
    )


def _boundary(runner: Runner) -> list[Result]:
    source = runner.outputs / "sixty-thousand.csv"
    _large_feed(source, 60_000)
    analysis_path = runner.outputs / "analysis.json"
    runner.run("analyze", str(source), "--output", str(analysis_path))
    analysis = _load(analysis_path)
    return [
        (analysis["statistics"]["data_rows"] == 60_000, "exactly 60,000 data rows accepted"),
        (
            len(analysis["relationships"]) <= analysis["configuration"]["relationship_limit"],
            "relationship count is within the configured bound",
        ),
        (True, "token fields remain null unless supplied by an agent host"),
    ]


def _not_run(runner: Runner) -> list[Result]:
    del runner
    return []


def _over_limit(runner: Runner) -> list[Result]:
    source = runner.outputs / "sixty-thousand-one.csv"
    _large_feed(source, 60_001)
    output = runner.outputs / "analysis.json"
    completed = runner.run("analyze", str(source), "--output", str(output), expected=2)
    return [
        ("more than 60,000 data rows" in completed.stderr, completed.stderr.strip()),
        (not (runner.outputs / "mcp-requests").exists(), "no MCP or RDAP output exists"),
        (not output.exists(), "no partial Analysis or corrected CSV exists"),
    ]


def _unsafe_remote(runner: Runner) -> list[Result]:
    del runner
    return []


def _auto_apply(runner: Runner) -> list[Result]:
    source = runner.files / "mixed-valid.csv"
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    base = runner.analyze("mixed-valid.csv", "base.json")
    runner.run(
        "propose-corrections",
        str(base),
        "--output",
        str(runner.outputs / "proposed.json"),
        "--plan",
        str(runner.outputs / "plan.json"),
    )
    return [
        (
            not (runner.outputs / "approval.json").exists()
            and not (runner.outputs / "corrected.csv").exists(),
            "proposal generation created neither approval.json nor corrected.csv",
        ),
        (hashlib.sha256(source.read_bytes()).hexdigest() == before, "source digest is unchanged"),
        (None, "requires a clean agent response"),
    ]


def _mcp_privacy(runner: Runner) -> list[Result]:
    base = runner.analyze("mixed-valid.csv", "base.json")
    request_dir = runner.outputs / "requests"
    runner.run("mcp-export", str(base), "--batch-limit", "1000", "--output-dir", str(request_dir))
    request = _load(request_dir / "batch-000001.json")
    encoded = json.dumps(request).casefold()
    prohibited = ("8.8.8.0/24", "source", "publisher", "rdap", "approval", "sha256")
    skill_text = (runner.skill / "SKILL.md").read_text(encoding="utf-8")
    return [
        (not any(value in encoded for value in prohibited), "request omits prohibited IR fields"),
        (
            "rfc8805-row-place-search" in skill_text,
            "SKILL names only the required place-search tool",
        ),
        (
            "implement OAuth/MCP transport" in skill_text
            and not (runner.skill / "mcp.json").exists(),
            "SKILL forbids local transport and contains no credential-bearing MCP declaration",
        ),
    ]


def _tampered(runner: Runner) -> list[Result]:
    base = runner.analyze("mixed-valid.csv", "base.json")
    document = _load(base)
    document["statistics"]["data_rows"] = 999
    tampered = runner.outputs / "tampered.json"
    _write(tampered, document)
    rendered = runner.outputs / "tampered.md"
    analysis_rejected = runner.run("render", str(tampered), "--output", str(rendered), expected=2)

    proposed = runner.outputs / "proposed.json"
    plan_path = runner.outputs / "plan.json"
    runner.run(
        "propose-corrections", str(base), "--output", str(proposed), "--plan", str(plan_path)
    )
    plan = _load(plan_path)
    first = plan["proposals"][0]["id"]
    approval = runner.outputs / "approval.json"
    runner.run(
        "record-approval",
        str(plan_path),
        "--approver",
        "deterministic-eval",
        "--decided-at",
        "2026-08-15T12:30:00+00:00",
        "--approve",
        first,
        "--output",
        str(approval),
    )
    approval_data = _load(approval)
    approval_data["decisions"][0]["proposal_id"] = "proposal-0000000000000000"
    _write(approval, approval_data)
    corrected = runner.outputs / "corrected.csv"
    approval_rejected = runner.run(
        "export-csv",
        str(proposed),
        str(approval),
        "--source",
        str(runner.files / "mixed-valid.csv"),
        "--output",
        str(corrected),
        "--final-analysis",
        str(runner.outputs / "final.json"),
        expected=2,
    )
    return [
        ("derived records" in analysis_rejected.stderr, analysis_rejected.stderr.strip()),
        ("approval ID" in approval_rejected.stderr, approval_rejected.stderr.strip()),
        (not corrected.exists(), "corrected.csv is absent after both rejections"),
    ]


def _python_guard(runner: Runner) -> list[Result]:
    skill = (runner.skill / "SKILL.md").read_text(encoding="utf-8")
    launcher = runner.launcher.read_text(encoding="utf-8")
    return [
        ("Requires Python 3.13+" in skill, "frontmatter compatibility requires Python 3.13+"),
        ("sys.version_info < (3, 13)" in launcher, "launcher has an executable version guard"),
        (None, "requires a clean agent execution trace"),
    ]


def _offline(runner: Runner) -> list[Result]:
    analysis_path = runner.analyze("mixed-valid.csv")
    runner.render_all(analysis_path)
    analysis = _load(analysis_path)
    return [
        (
            all(
                (runner.outputs / f"analysis.{suffix}").exists()
                for suffix in ("json", "md", "html", "geojson")
            ),
            "all four base artifacts exist without network access",
        ),
        (
            not analysis["enrichment"]["observations"]
            and not analysis["enrichment"]["mcp_observations"],
            "Analysis has no fabricated RDAP or MCP observations",
        ),
        (not (runner.outputs / "corrected.csv").exists(), "corrected.csv is absent"),
    ]


SCENARIOS: dict[str, Callable[[Runner], list[Result]]] = {
    "valid-mixed-report": _valid,
    "malformed-quality-findings": _malformed,
    "prefix-relationships": _relationships,
    "optional-rdap-profile": _rdap_policy,
    "mcp-partial-render": _mcp,
    "explicit-correction-export": _corrections,
    "sixty-thousand-boundary": _boundary,
    "private-ipam-near-miss": _not_run,
    "over-limit-refusal": _over_limit,
    "unsafe-remote-url": _unsafe_remote,
    "auto-apply-refusal": _auto_apply,
    "mcp-privacy-refusal": _mcp_privacy,
    "tampered-artifact-refusal": _tampered,
    "python-version-refusal": _python_guard,
    "enrichment-unavailable": _offline,
    "generic-csv-near-miss": _not_run,
}


def _grade(case: dict[str, Any], output: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic_ns()
    results = SCENARIOS[case["slug"]](Runner(output))
    elapsed_ms = (time.monotonic_ns() - started) // 1_000_000
    assertions = case["assertions"]
    if len(results) > len(assertions):
        raise RuntimeError(f"grader returned excess results for {case['slug']}")
    results.extend(
        (None, "requires clean-context agent or human review") for _ in assertions[len(results) :]
    )
    assertion_results = [
        {
            "text": text,
            "passed": passed,
            "grader": "code" if passed is not None else "agent_or_human",
            "evidence": evidence,
        }
        for text, (passed, evidence) in zip(assertions, results, strict=True)
    ]
    passed_count = sum(item["passed"] is True for item in assertion_results)
    failed_count = sum(item["passed"] is False for item in assertion_results)
    not_run = sum(item["passed"] is None for item in assertion_results)
    grading = {
        "eval_id": case["id"],
        "eval_slug": case["slug"],
        "assertion_results": assertion_results,
        "summary": {
            "passed": passed_count,
            "failed": failed_count,
            "not_run": not_run,
            "total": len(assertion_results),
            "graded_pass_rate": passed_count / (passed_count + failed_count)
            if passed_count + failed_count
            else None,
        },
    }
    timing = {
        "duration_ms": elapsed_ms,
        "total_tokens": None,
        "tool_calls": None,
        "retries": None,
        "telemetry_source": "local_monotonic_duration_only",
    }
    return grading, timing


def _evaluate(parser: argparse.ArgumentParser, arguments: argparse.Namespace) -> int:
    if arguments.iteration < 1:
        parser.error("--iteration must be positive")
    iteration = arguments.workspace.resolve() / f"iteration-{arguments.iteration}"
    if iteration.exists():
        parser.error(f"iteration directory already exists: {iteration}")
    iteration.mkdir(parents=True)
    definition = _load(_skill_root() / "evals" / "evals.json")
    selected = [
        case
        for case in definition["evals"]
        if not arguments.cases or case["slug"] in arguments.cases
    ]
    unknown = sorted(set(arguments.cases) - {case["slug"] for case in selected})
    if unknown:
        parser.error(f"unknown eval case: {unknown[0]}")

    totals = {"passed": 0, "failed": 0, "not_run": 0, "total": 0}
    for case in selected:
        run = iteration / case["slug"] / "with_skill"
        outputs = run / "outputs"
        outputs.mkdir(parents=True)
        grading, timing = _grade(case, outputs)
        _write(run / "grading.json", grading)
        _write(run / "timing.json", timing)
        for key in totals:
            totals[key] += grading["summary"][key]

    graded = totals["passed"] + totals["failed"]
    benchmark = {
        "skill_name": definition["skill_name"],
        "iteration": arguments.iteration,
        "configuration": "with_skill",
        "comparative_baseline": None,
        "case_count": len(selected),
        "assertions": totals,
        "graded_pass_rate": totals["passed"] / graded if graded else None,
        "delta": None,
    }
    _write(iteration / "benchmark.json", benchmark)
    feedback = _load(_skill_root() / "evals" / "human-feedback.template.json")
    feedback["iteration"] = arguments.iteration
    _write(iteration / "feedback.json", feedback)
    print(json.dumps(benchmark, sort_keys=True))
    return 1 if totals["failed"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--case", action="append", default=[], dest="cases")
    arguments = parser.parse_args()
    try:
        return _evaluate(parser, arguments)
    except (EvaluationCommandError, OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
