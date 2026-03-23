.PHONY: deps install clean run run-bulk

deps:
	@command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 is required. Install it and retry." >&2; exit 1; }
	@echo "All required tools are present."

install:
	pip install -r requirements.txt

clean:
	rm -rf run/output/*
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

run:
	@if [ -z "$(FILE)" ]; then echo "Usage: make run FILE=<csv-file-or-url>"; exit 1; fi
	python3 main.py $(FILE)

run-bulk:
	@if [ -z "$(FILE)" ]; then echo "Usage: make run-bulk FILE=<json-manifest>"; exit 1; fi
	python3 main.py --bulk $(FILE)
