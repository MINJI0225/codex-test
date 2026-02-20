# AX Tool Framework

Container-isolated tool execution framework with a single-domain AX Gateway and worker-based tool runtime.

## Normative Spec

The normative v0.1 framework contract lives in:

- `docs/core-spec-v0.1.md`

Use the spec file as the source of truth for invariants, envelope contracts, domain/catalog model, and onboarding requirements.

## Quick Start

Prerequisites:

- Docker Desktop (or Docker Engine)
- Python 3.11+
- `FIRECRAWL_API_KEY` in your environment

Start services:

```bash
docker compose up --build
```

Health checks:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8080/healthz
```

## Gateway API Summary

### `GET /v1/domain`

Returns current mounted domain identity:

```json
{
  "domain_id": "example_domain",
  "version": "0.1"
}
```

### `GET /v1/tools`

Returns domain-scoped tool catalog:

```json
{
  "domain_id": "example_domain",
  "version": "0.1",
  "tools": [
    {
      "tool_id": "firecrawl.crawl",
      "kind": "service_worker",
      "display_name": "Firecrawl Crawl",
      "description": "Crawl a URL and return extracted content using Firecrawl API",
      "capabilities": ["web_crawl", "web_scrape", "extract"],
      "timeout_sec": 60,
      "egress_allowlist": ["api.firecrawl.dev:443"],
      "transport_type": "http",
      "transport_endpoint": "/run",
      "input_schema_ref": "schemas/firecrawl_crawl_input.json",
      "output_schema_ref": "schemas/firecrawl_crawl_output.json"
    }
  ]
}
```

### `POST /v1/tools/{tool_id}:run`

Runs the selected tool via gateway -> worker envelope contract:

```bash
curl -X POST http://localhost:8000/v1/tools/firecrawl.crawl:run \
  -H "Content-Type: application/json" \
  -d '{"input":{"url":"https://example.com","mode":"scrape","formats":["markdown"]}}'
```

## Local API Checks

```bash
curl http://localhost:8000/v1/domain
curl http://localhost:8000/v1/tools
```

## Repo Layout

```text
.
戍式式 README.md
戍式式 docs/
弛   戌式式 core-spec-v0.1.md
戍式式 docker-compose.yml
戍式式 domain/
戍式式 gateway/
戍式式 tools/
戌式式 tests/
```

## Tests

Install dependencies:

```bash
pip install -e .[dev]
```

Run gateway-focused tests:

```bash
PYTHONPATH=gateway:. pytest -q tests/test_manifest_loading.py tests/test_gateway_run_tool.py tests/test_integration_smoke.py
```

Run Firecrawl client mapping tests:

```bash
PYTHONPATH=. pytest -q tests/test_firecrawl_client_error_mapping.py
```