.PHONY: check-deps update-iso-tables clean-runs clean-tuner-run clean-geofeed-run \
       awesome-copilot-clone awesome-copilot-branch awesome-copilot-skill \
       awesome-copilot-validate awesome-copilot-commit awesome-copilot-pr \
       awesome-copilot-submit \
       awesome-copilot-plugin awesome-copilot-plugin-validate \
       awesome-copilot-plugin-commit awesome-copilot-plugin-pr \
       awesome-copilot-plugin-submit

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

# ─── awesome-copilot contribution workflow ───────────────────────────────
# Clones the fork, copies the geofeed-tuner skill, and opens a PR
# against github/awesome-copilot's "staged" branch.
#
# Prerequisites: git, gh (GitHub CLI, authenticated), npm, rsync
#
# Usage:
#   make awesome-copilot-submit          # full end-to-end
#   make awesome-copilot-clone           # clone / refresh fork only
#   make awesome-copilot-skill           # copy skill + validate + build
#   make awesome-copilot-pr              # commit, push, open PR

AWESOME_COPILOT_DIR      := ../awesome-copilot
AWESOME_COPILOT_FORK     := https://github.com/punit-fastah/awesome-copilot.git
AWESOME_COPILOT_UPSTREAM := https://github.com/github/awesome-copilot.git
AC_SKILL_NAME            := geofeed-tuner
AC_SKILL_SRC             := skills/$(AC_SKILL_NAME)
AC_BRANCH                := add-$(AC_SKILL_NAME)-skill
AC_PR_TITLE              := Add $(AC_SKILL_NAME) skill for RFC 8805 IP geolocation feeds 🤖🤖🤖

## awesome-copilot-clone: clone fork (or refresh) and install deps
awesome-copilot-clone:
	@command -v gh    >/dev/null 2>&1 || { echo "ERROR: gh (GitHub CLI) is required." >&2; exit 1; }
	@command -v rsync >/dev/null 2>&1 || { echo "ERROR: rsync is required." >&2; exit 1; }
	@if [ -d "$(AWESOME_COPILOT_DIR)/.git" ]; then \
		echo "$(AWESOME_COPILOT_DIR) exists — refreshing…"; \
		cd "$(AWESOME_COPILOT_DIR)" && git fetch --all --prune && git checkout staged && git pull origin staged; \
	else \
		git clone "$(AWESOME_COPILOT_FORK)" "$(AWESOME_COPILOT_DIR)"; \
		cd "$(AWESOME_COPILOT_DIR)" && git remote add upstream "$(AWESOME_COPILOT_UPSTREAM)" 2>/dev/null || true; \
		cd "$(AWESOME_COPILOT_DIR)" && git fetch upstream && git checkout staged; \
	fi
	cd "$(AWESOME_COPILOT_DIR)" && npm ci

## awesome-copilot-branch: create a feature branch from staged
awesome-copilot-branch:
	cd "$(AWESOME_COPILOT_DIR)" && git fetch upstream
	cd "$(AWESOME_COPILOT_DIR)" && git checkout -B staged upstream/staged
	cd "$(AWESOME_COPILOT_DIR)" && git checkout -B "$(AC_BRANCH)" staged

## awesome-copilot-skill: copy skill into fork, validate, and build
awesome-copilot-skill: awesome-copilot-branch
	@echo "Copying $(AC_SKILL_SRC) → $(AWESOME_COPILOT_DIR)/skills/$(AC_SKILL_NAME) …"
	@mkdir -p "$(AWESOME_COPILOT_DIR)/skills/$(AC_SKILL_NAME)"
	rsync -av --delete --exclude='run/' "$(AC_SKILL_SRC)/" "$(AWESOME_COPILOT_DIR)/skills/$(AC_SKILL_NAME)/"

## awesome-copilot-validate: validate skill, rebuild README, fix line endings
awesome-copilot-validate:
	cd "$(AWESOME_COPILOT_DIR)" && npm run skill:validate
	cd "$(AWESOME_COPILOT_DIR)" && npm run build
	cd "$(AWESOME_COPILOT_DIR)" && bash scripts/fix-line-endings.sh
	@echo "Validation and build complete."

AC_PR_BODY_FILE          := pr-body.md

## awesome-copilot-commit: stage and commit the skill changes
awesome-copilot-commit:
	cd "$(AWESOME_COPILOT_DIR)" && git add -A
	cd "$(AWESOME_COPILOT_DIR)" && { git diff --cached --quiet && echo "Nothing to commit." || \
		git commit -m "Add $(AC_SKILL_NAME) skill for RFC 8805 IP geolocation feeds"; }

## awesome-copilot-pr: push branch and open PR targeting staged on upstream
awesome-copilot-pr: awesome-copilot-commit
	cd "$(AWESOME_COPILOT_DIR)" && git push -u origin "$(AC_BRANCH)"
	@echo "Opening PR in browser — edit the body before submitting…"
	cd "$(AWESOME_COPILOT_DIR)" && gh pr create \
		--repo github/awesome-copilot \
		--base staged \
		--head "punit-fastah:$(AC_BRANCH)" \
		--title "$(AC_PR_TITLE)" \
		--body-file "$(CURDIR)/$(AC_PR_BODY_FILE)" \
		--web

## awesome-copilot-submit: full workflow — clone fork, add skill, create PR
awesome-copilot-submit: awesome-copilot-clone awesome-copilot-skill awesome-copilot-validate awesome-copilot-pr

# ─── awesome-copilot plugin contribution workflow ────────────────────────
# Creates a plugin in the awesome-copilot fork that bundles the
# already-merged geofeed-tuner skill.
#
# Prerequisites: same as the skill workflow (git, gh, npm, rsync)
#
# Usage:
#   make awesome-copilot-plugin-submit   # full end-to-end
#   make awesome-copilot-plugin          # copy plugin files only

AC_PLUGIN_NAME           := fastah-inc-ip-geolocation-tools
AC_PLUGIN_SRC            := .github/plugin
AC_PLUGIN_BRANCH         := add-$(AC_PLUGIN_NAME)-plugin
AC_PLUGIN_PR_TITLE       := Add $(AC_PLUGIN_NAME) plugin for RFC 8805 IP geolocation feeds 🤖🤖🤖

## awesome-copilot-plugin-branch: create a feature branch from staged for plugin
awesome-copilot-plugin-branch:
	cd "$(AWESOME_COPILOT_DIR)" && git fetch upstream
	cd "$(AWESOME_COPILOT_DIR)" && git checkout -B staged upstream/staged
	cd "$(AWESOME_COPILOT_DIR)" && git checkout -B "$(AC_PLUGIN_BRANCH)" staged

## awesome-copilot-plugin: copy plugin metadata and skill into fork
awesome-copilot-plugin: awesome-copilot-plugin-branch
	@echo "Copying $(AC_PLUGIN_SRC) → $(AWESOME_COPILOT_DIR)/plugins/$(AC_PLUGIN_NAME) …"
	@mkdir -p "$(AWESOME_COPILOT_DIR)/plugins/$(AC_PLUGIN_NAME)/.github/plugin"
	rsync -av "$(AC_PLUGIN_SRC)/plugin.json" "$(AWESOME_COPILOT_DIR)/plugins/$(AC_PLUGIN_NAME)/.github/plugin/plugin.json"
	@echo "Copying $(AC_SKILL_SRC) → $(AWESOME_COPILOT_DIR)/plugins/$(AC_PLUGIN_NAME)/skills/$(AC_SKILL_NAME) …"
	@mkdir -p "$(AWESOME_COPILOT_DIR)/plugins/$(AC_PLUGIN_NAME)/skills/$(AC_SKILL_NAME)"
	rsync -av --delete --exclude='run/' "$(AC_SKILL_SRC)/" "$(AWESOME_COPILOT_DIR)/plugins/$(AC_PLUGIN_NAME)/skills/$(AC_SKILL_NAME)/"
	@echo "Copying plugin README …"
	rsync -av "README-PLUGIN.md" "$(AWESOME_COPILOT_DIR)/plugins/$(AC_PLUGIN_NAME)/README.md"

## awesome-copilot-plugin-validate: validate plugin, rebuild README, fix line endings
awesome-copilot-plugin-validate:
	cd "$(AWESOME_COPILOT_DIR)" && npm run plugin:validate
	cd "$(AWESOME_COPILOT_DIR)" && npm run build
	cd "$(AWESOME_COPILOT_DIR)" && bash scripts/fix-line-endings.sh
	@echo "Plugin validation and build complete."

## awesome-copilot-plugin-commit: stage and commit the plugin changes
awesome-copilot-plugin-commit:
	cd "$(AWESOME_COPILOT_DIR)" && git add -A
	cd "$(AWESOME_COPILOT_DIR)" && { git diff --cached --quiet && echo "Nothing to commit." || \
		git commit -m "Add $(AC_PLUGIN_NAME) plugin for RFC 8805 IP geolocation feeds"; }

## awesome-copilot-plugin-pr: push branch and open PR targeting staged on upstream
awesome-copilot-plugin-pr: awesome-copilot-plugin-commit
	cd "$(AWESOME_COPILOT_DIR)" && git push -u origin "$(AC_PLUGIN_BRANCH)"
	@echo "Opening PR in browser — edit the body before submitting…"
	cd "$(AWESOME_COPILOT_DIR)" && gh pr create \
		--repo github/awesome-copilot \
		--base staged \
		--head "punit-fastah:$(AC_PLUGIN_BRANCH)" \
		--title "$(AC_PLUGIN_PR_TITLE)" \
		--body-file "$(CURDIR)/$(AC_PR_BODY_FILE)" \
		--web

## awesome-copilot-plugin-submit: full workflow — clone fork, add plugin, create PR
awesome-copilot-plugin-submit: awesome-copilot-clone awesome-copilot-plugin awesome-copilot-plugin-validate awesome-copilot-plugin-pr
	@echo "Done — PR opened against github/awesome-copilot staged branch."
