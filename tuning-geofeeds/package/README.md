# Fastah geofeed quality analyzer

Portable Python 3.13+ implementation bundled with the `tuning-geofeeds` Agent
Skill. It parses public RFC 8805 geofeeds locally into a typed, versioned
Analysis IR and provides deterministic validation, relationship analysis,
optional direct-RIR RDAP evidence, host-mediated Fastah MCP exchange, IR-only
renderers, and explicit approval-gated corrected CSV export.

Install from a user-selected working directory. Keep the release tree
read-only so committed schemas and dashboard assets remain unchanged:

```bash
PACKAGE_ROOT="/absolute/path/to/tuning-geofeeds/package"
python3.13 -m venv /absolute/work-directory/.venv
cp -R "$PACKAGE_ROOT" /absolute/work-directory/tuning-geofeeds-runtime
/absolute/work-directory/.venv/bin/python -m pip install \
  /absolute/work-directory/tuning-geofeeds-runtime
/absolute/work-directory/.venv/bin/python -m geofeed_quality.cli --help
```

Install from the working copy, never from the read-only distribution tree;
Python build frontends may write local build metadata beside their input.

The skill workflow and safety boundaries are in [`../SKILL.md`](../SKILL.md).
