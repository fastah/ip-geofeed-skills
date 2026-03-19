.PHONY: check-deps update-iso-tables clean-runs clean-tuner-run clean-geofeed-run

ASSETS_DIR := skills/geofeed-tuner/assets

# Source: https://github.com/pycountry/pycountry/tree/main/src/pycountry/databases
PYCOUNTRY_BASE_URL := https://raw.githubusercontent.com/pycountry/pycountry/main/src/pycountry/databases

## check-deps: verify required tools (curl, jq) are installed
check-deps:
	@command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required. Install it and retry." >&2; exit 1; }
	@command -v jq   >/dev/null 2>&1 || { echo "ERROR: jq is required. Install it and retry." >&2; exit 1; }
	@echo "All required tools are present."

## update-iso-tables: refresh ISO 3166-1 and 3166-2 tables from pycountry (run weekly or via CI cron)
update-iso-tables: check-deps
	@echo "Updating $(ASSETS_DIR)/iso3166-1.json ..."
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	curl -fsSL "$(PYCOUNTRY_BASE_URL)/iso3166-1.json" \
	  | jq '."3166-1" |= (map({alpha_2, name, flag}) | sort_by(.alpha_2))' > "$$tmp" \
	  && mv "$$tmp" "$(ASSETS_DIR)/iso3166-1.json"
	@echo "Updating $(ASSETS_DIR)/iso3166-2.json ..."
	@tmp=$$(mktemp); trap 'rm -f "$$tmp"' EXIT; \
	curl -fsSL "$(PYCOUNTRY_BASE_URL)/iso3166-2.json" \
	  | jq '."3166-2" |= (map({code, name}) | sort_by(.code))' > "$$tmp" \
	  && mv "$$tmp" "$(ASSETS_DIR)/iso3166-2.json"
	@echo "ISO tables updated successfully."

# Clear all run directories
clean-runs: clean-tuner-run clean-geofeed-run

# Clear skills/geofeed-tuner/run directory (keeps run/data structure and .gitignore)
clean-tuner-run:
	@find skills/geofeed-tuner/run -type f ! -name '.gitignore' -delete
	@find skills/geofeed-tuner/run -mindepth 2 -type d -delete
	@echo "Cleared files in skills/geofeed-tuner/run (kept first-level dirs)"

# Clear experimental/ip-geofeed/run directory (keeps run/data structure and .gitignore)
clean-geofeed-run:
	@find experimental/ip-geofeed/run -type f ! -name '.gitignore' -delete
	@find experimental/ip-geofeed/run -mindepth 2 -type d -delete
	@echo "Cleared files in experimental/ip-geofeed/run (kept first-level dirs)"
