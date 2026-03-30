deps:
	@command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required. Install it and retry." >&2; exit 1; }
	@command -v jq   >/dev/null 2>&1 || { echo "ERROR: jq is required. Install it and retry." >&2; exit 1; }
	@command -v openapi-generator-cli   >/dev/null 2>&1 || { echo "ERROR: openapi-generator-cli is required. Install it and retry." >&2; exit 1; }
	@echo "All required tools are present."

update-rest-from-openapi:
	@echo "Downloading OpenAPI spec from https://mcp.fastah.ai/rest/openapi.json ..."
	@tmp_spec=$$(mktemp); trap 'rm -f "$$tmp_spec"' EXIT; \
	curl -fsSL https://mcp.fastah.ai/rest/openapi.json -o "$$tmp_spec"; \
	echo "Generating Go structs (models only) with OpenAPI Generator CLI ..." ; \
	openapi-generator-cli generate -i "$$tmp_spec" -g go -o internal/geofeed-structs \
		--global-property models,supportingFiles= \
		--additional-properties=packageName=geofeed_structs,withGoMod=false,generateMarshalJSON=true,generateUnmarshalJSON=true; \
	echo "Removing non-model generated files ..." ; \
	rm -rf internal/geofeed-structs/api internal/geofeed-structs/docs internal/geofeed-structs/.openapi-generator; \
	rm -f internal/geofeed-structs/.openapi-generator-ignore internal/geofeed-structs/.gitignore internal/geofeed-structs/.travis.yml internal/geofeed-structs/git_push.sh; \
	rm -f internal/geofeed-structs/client.go internal/geofeed-structs/configuration.go internal/geofeed-structs/response.go internal/geofeed-structs/README.md; \
	rm -f internal/geofeed-structs/go.mod internal/geofeed-structs/go.sum; \
	rm -f internal/geofeed-structs/model_approx_geo.go internal/geofeed-structs/model_error_detail.go; \
	rm -f internal/geofeed-structs/model_error_model.go internal/geofeed-structs/model_ip_metadata_body.go; \
	echo "Done. Structs generated in internal/geofeed-structs/"

clean-rest:
	@rm -rf internal/geofeed-structs internal/rest/python_models
	@echo "Cleaned generated REST client code and models."