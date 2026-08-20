# Maintainer release guide

The private Fastah monorepo is canonical. Do not edit generated public files by hand.

## Build the public stage

From `gen2/geofeed-quality` in the private monorepo:

```bash
make skill-package-check
make skill-public-stage OUTPUT=/absolute/path/to/new/public-stage
```

The output path must not exist. Neither command pushes, deploys, publishes, or submits a marketplace package.

The package check validates the canonical skill and copied host views, official Agent Skills metadata, a real isolated Amp install, portable analyzer smoke checks, approval refusal, secret and private-path scans, deterministic package trees, and manifest digests. Protected private CI is the release gate.

## Generated public tree

The stage contains:

```text
README.md
CONTRIBUTING.md
MIGRATION.md
LICENSE
mcp-plugin.json
marketplace-metadata.json
public-export-manifest.json
.github/plugin/plugin.json
.vscode/mcp.json
tuning-geofeeds/
```

`public-export-manifest.json` records the private source commit plus the source path, byte count, and SHA-256 digest for every canonical skill file and generated root file. `publicationPerformed` must remain `false` in staging.

Product identity, plugin version, MCP endpoint and contract, publisher, support, privacy, and Terms values come from `tuning-geofeeds/packaging/release.json`. Python and analyzer versions come from `gen2/geofeed-quality/pyproject.toml`. Analysis schema version comes from the committed schema. Public prose comes from `tuning-geofeeds/packaging/public-root/`. The public Apache-2.0 license comes from `tuning-geofeeds/packaging/public/LICENSE`.

## Public update pull request

Prepare one reviewable pull request against `https://github.com/fastah/ip-geofeed-skills`. It should:

1. Replace the public working tree with the generated stage and record its private source commit.
2. Confirm `geofeed-tuner` and its legacy discovery metadata have not returned.
3. Remove files absent from the generated stage rather than carrying stale copies.
4. Exclude feeds other than allowlisted eval fixtures, runtime captures, benchmark transcripts, private validation, credentials, local paths, and generated work directories.
5. Verify every staged file against `public-export-manifest.json` before merge.

The migration is not a compatibility release. Reanalyze original source feeds with `tuning-geofeeds`; do not import legacy reports as current Analysis JSON.

## Readiness

The local-file-first GitHub Skill is public, and its isolated Amp install has been smoke-tested. Marketplace release remains blocked by product-owned secure acquisition, measured 60,000-row time/memory/browser budgets, live production Terms and OAuth consistency, deployed log-retention evidence, clean Claude and OpenAI host verification, reviewer access, and marketplace review. An allowlisted host asking the user to upload the CSV is supported behavior; it is not permission to bypass network policy.

Sequence shared-state work separately: merge the private implementation, generate and review the public pull request, publish to public GitHub with approval, repeat the public Amp install smoke, validate Claude and OpenAI hosts, close production and product blockers, then submit marketplaces last with separate approval.
