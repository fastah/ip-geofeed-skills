deps:
	@command -v curl >/dev/null 2>&1 || { echo "ERROR: curl is required. Install it and retry." >&2; exit 1; }
	@command -v jq   >/dev/null 2>&1 || { echo "ERROR: jq is required. Install it and retry." >&2; exit 1; }
	@command -v openapi-generator-cli   >/dev/null 2>&1 || { echo "ERROR: openapi-generator-cli is required. Install it and retry." >&2; exit 1; }
	@echo "All required tools are present."

update-rest-from-openapi:
	@echo "Downloading OpenAPI spec from https://mcp.fastah.ai/rest/openapi.json ..."
	@tmp_spec=$$(mktemp); trap 'rm -f "$$tmp_spec"' EXIT; \
	curl -fsSL https://mcp.fastah.ai/rest/openapi.json -o "$$tmp_spec"; \
	echo "Generating Go client code with OpenAPI Generator CLI ..." ; \
	openapi-generator-cli generate -i "$$tmp_spec" -g go -o internal/rest/client --additional-properties=packageName=restclient,generateModels=true,generateModelTests=false,generateModelDocumentation=false,generateApiTests=false,generateApiDocumentation=false; \
# 	echo "Generating Python 3 models with OpenAPI Generator CLI ..." ; \
# 	openapi-generator-cli generate -i "$$tmp_spec" -g python -o internal/rest/python_models --additional-properties=packageName=restclient,generateModels=true,generateModelTests=false,generateModelDocumentation=false,generateApiTests=false,generateApiDocumentation=false		

clean-rest:
	@rm -rf internal/rest/client internal/rest/python_models
	@echo "Cleaned generated REST client code and models."