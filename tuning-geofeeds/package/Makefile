PYTHON ?= .venv/bin/python
PYTHON_BOOTSTRAP ?= python3.13

.PHONY: setup check-python format lint type test test-live-rdap schema-generate schema-check skill-validate skill-eval skill-release-check skill-package-check skill-package-build skill-public-stage check analyze render render-html export-geojson mcp-export mcp-import propose-corrections record-approval export-csv

setup:
	$(PYTHON_BOOTSTRAP) -c 'import sys; assert sys.version_info >= (3, 13), "Python 3.13 or newer is required"'
	$(PYTHON_BOOTSTRAP) -m venv --clear .venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -e '.[dev]'

check-python:
	$(PYTHON) -c 'import sys; assert sys.version_info >= (3, 13), "Python 3.13 or newer is required"'

format:
	$(PYTHON) -m ruff format src tests tuning-geofeeds/scripts

lint:
	$(PYTHON) -m ruff check src tests tuning-geofeeds/scripts
	$(PYTHON) -m ruff format --check src tests tuning-geofeeds/scripts

type:
	$(PYTHON) -m mypy src tests
	$(PYTHON) -m mypy tuning-geofeeds/scripts

test:
	$(PYTHON) -m pytest

test-live-rdap:
	FASTAH_RDAP_LIVE=1 $(PYTHON) -m pytest -m live tests/test_rdap.py

schema-generate:
	$(PYTHON) -m geofeed_quality.cli schema generate

schema-check:
	$(PYTHON) -m geofeed_quality.cli schema check

skill-validate:
	$(PYTHON) tuning-geofeeds/scripts/release_check.py --check-only

skill-eval:
	rm -rf tuning-geofeeds/evals/workspace/gate
	$(PYTHON) tuning-geofeeds/scripts/evaluate.py --workspace tuning-geofeeds/evals/workspace/gate --iteration 1

skill-release-check:
	$(PYTHON) tuning-geofeeds/scripts/release_check.py --check-only

skill-package-check:
	$(PYTHON) tuning-geofeeds/scripts/package_hosts.py check

skill-package-build:
	@test -n "$(OUTPUT)" || (echo "usage: make skill-package-build OUTPUT=/new/release-directory" >&2; exit 2)
	$(PYTHON) tuning-geofeeds/scripts/package_hosts.py build --output "$(OUTPUT)"

skill-public-stage:
	@test -n "$(OUTPUT)" || (echo "usage: make skill-public-stage OUTPUT=/new/public-stage" >&2; exit 2)
	$(PYTHON) tuning-geofeeds/scripts/package_hosts.py public-export --output "$(OUTPUT)"

check: check-python lint type schema-check test skill-validate skill-eval skill-release-check skill-package-check

analyze:
	@test -n "$(INPUT)" || (echo "usage: make analyze INPUT=feed.csv [OUTPUT=analysis.json]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli analyze "$(INPUT)" --output "$(or $(OUTPUT),analysis.json)"

render:
	@test -n "$(INPUT)" || (echo "usage: make render INPUT=analysis.json [OUTPUT=analysis.md]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli render "$(INPUT)" --output "$(or $(OUTPUT),analysis.md)"

render-html:
	@test -n "$(INPUT)" || (echo "usage: make render-html INPUT=analysis.json [OUTPUT=dashboard.html]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli render-html "$(INPUT)" --output "$(or $(OUTPUT),dashboard.html)"

export-geojson:
	@test -n "$(INPUT)" || (echo "usage: make export-geojson INPUT=analysis.json [OUTPUT=analysis.geojson]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli export-geojson "$(INPUT)" --output "$(or $(OUTPUT),analysis.geojson)"

mcp-export:
	@test -n "$(INPUT)" -a -n "$(BATCH_LIMIT)" || (echo "usage: make mcp-export INPUT=analysis.json BATCH_LIMIT=<discovered> [OUTPUT_DIR=mcp-requests]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli mcp-export "$(INPUT)" --batch-limit "$(BATCH_LIMIT)" --output-dir "$(or $(OUTPUT_DIR),mcp-requests)"

mcp-import:
	@test -n "$(INPUT)" -a -n "$(RESPONSES)" -a -n "$(MAPPING)" -a -n "$(BATCH_LIMIT)" || (echo "usage: make mcp-import INPUT=analysis.json RESPONSES='response-1.json ...' MAPPING=mcp-requests/mapping.json BATCH_LIMIT=<discovered> [OUTPUT=analysis-with-mcp.json]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli mcp-import "$(INPUT)" $(RESPONSES) --mapping "$(MAPPING)" --batch-limit "$(BATCH_LIMIT)" --output "$(or $(OUTPUT),analysis-with-mcp.json)"

propose-corrections:
	@test -n "$(INPUT)" || (echo "usage: make propose-corrections INPUT=analysis.json [OUTPUT=analysis-proposed.json] [PLAN=correction-plan.json]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli propose-corrections "$(INPUT)" --output "$(or $(OUTPUT),analysis-proposed.json)" --plan "$(or $(PLAN),correction-plan.json)"

record-approval:
	@test -n "$(PLAN)" -a -n "$(APPROVER)" -a -n "$(DECIDED_AT)" || (echo "usage: make record-approval PLAN=correction-plan.json APPROVER=<label> DECIDED_AT=<ISO-8601> DECISIONS='--approve proposal-id [--reject proposal-id]'" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli record-approval "$(PLAN)" --approver "$(APPROVER)" --decided-at "$(DECIDED_AT)" $(DECISIONS) --output "$(or $(OUTPUT),correction-approval.json)"

export-csv:
	@test -n "$(INPUT)" -a -n "$(APPROVAL)" -a -n "$(SOURCE)" || (echo "usage: make export-csv INPUT=analysis-proposed.json APPROVAL=correction-approval.json SOURCE=feed.csv [OUTPUT=corrected.csv] [FINAL_ANALYSIS=analysis-final.json]" >&2; exit 2)
	$(PYTHON) -m geofeed_quality.cli export-csv "$(INPUT)" "$(APPROVAL)" --source "$(SOURCE)" --output "$(or $(OUTPUT),corrected.csv)" --final-analysis "$(or $(FINAL_ANALYSIS),analysis-final.json)"
