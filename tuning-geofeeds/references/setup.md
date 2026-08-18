# Python setup

The portable analyzer requires Python 3.13 or newer. Resolve the skill root
from the installed skill location, change to that directory, then ask the
bundled launcher where its package lives:

```bash
SKILL_ROOT="/absolute/path/to/tuning-geofeeds"
cd "$SKILL_ROOT"
BOOTSTRAP_PYTHON="/absolute/path/to/python3.13"
PACKAGE_ROOT="$("$BOOTSTRAP_PYTHON" scripts/geofeed_cli.py --print-package-root)"
"$BOOTSTRAP_PYTHON" -m venv "$WORK/.venv"
PYTHON="$WORK/.venv/bin/python"
RUNTIME_SOURCE="$WORK/tuning-geofeeds-runtime"
cp -R "$PACKAGE_ROOT" "$RUNTIME_SOURCE"
"$PYTHON" -m pip install "$RUNTIME_SOURCE"
```

On Windows, use the virtual environment interpreter at
`$WORK\.venv\Scripts\python.exe`. Windows users should install Python through
[Python Install Manager in the Microsoft Store](https://apps.microsoft.com/detail/9nq7512cxl7t?hl=en-US)
so it auto-updates; the Microsoft Store is not mandatory. Use the host's file
copy operation to create the same `tuning-geofeeds-runtime` working copy before
installing it.

Run the launcher with the prepared interpreter:

```bash
"$PYTHON" scripts/geofeed_cli.py --help
```

If the host cannot retain the skill root as its working directory, invoke the
same launcher by its resolved absolute path. It does not resolve the bundled
package relative to the caller's current directory.

The analyzer accepts at most 60,000 data rows. Comments and blank physical
lines do not count. An oversized input fails before any Analysis IR is
generated; never truncate or split it to create partial IR.

Never install directly from `PACKAGE_ROOT`: Python build frontends may write
build or metadata files beside their input. Keep the runtime source copy,
virtual environment, and all analysis outputs in the user-selected working
directory so the installed skill remains read-only.

Downloaded feeds, analysis IR, approval artifacts, reports, and exports remain
in that user-selected local work directory until the user deletes them. Fastah
does not retain those artifacts server-side. Optional RDAP uses only a per-run
in-memory cache by default; persistent caching is not enabled. Fastah MCP
operational/authentication logs are separate and may retain only sanitized
request metadata and aggregate outcomes. They must exclude tokens, row location
contents, feed/IR/publisher/RDAP/approval data, and raw backend errors, and must
be deleted after 30 days. Do not claim deployed compliance until worker fields
and retention infrastructure have been verified.
