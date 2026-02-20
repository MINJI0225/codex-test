# AX Tool Framework (Container-Isolated) Spec v0.1

## 0. Project Summary

AX Tool Framework provides a shared execution framework for domain-specific tools.

External LLM/Agent systems call a single tool endpoint exposed by AX Gateway.
Actual tool execution runs inside isolated tool worker containers.

Goals:

- Package domain-specific tool sets as reusable AX framework bundles.
- Isolate tool execution at container boundary (permissions/resources/network).
- Expose tool operations in a form that LLM/Agent systems can call directly.
- Control external access through explicit allowlists.

v0.1 scope:

- Docker-based local/single-host deployment.
- Gateway + Tool worker over HTTP(JSON).
- Tool registry/policies loaded from domain manifest + policies files.
- Include one common tool worker: Firecrawl API tool.

---

## 1. High-Level Architecture

### 1.1 Components

- LLM + Agent (External)
  - Calls AX Gateway tool endpoint.
  - Optional: can be mounted behind an MCP host.
- AX Gateway (Domain Sandbox Entry)
  - Public HTTP API.
  - Tool registry/manifest loading.
  - Tool routing.
  - Standard request/response envelope handling.
  - Policy enforcement (timeout, concurrency, egress metadata checks).
  - Observability (`trace_id`, `tool_run_id`, logs).
- Tool Worker Containers
  - One service/container per tool group.
  - Receive JSON over HTTP from gateway.
  - Return JSON envelope back to gateway.
- External Data/Services
  - HTTP APIs and optional DB/storage integrations.

### 1.2 Data Flow

1. LLM+Agent calls `POST /v1/tools/{tool_id}:run` on AX Gateway.
2. AX Gateway:
   - Looks up `tool_id` in manifest.
   - Validates input via JSON schema.
   - Applies policy checks (timeout/concurrency/egress metadata).
   - Calls target tool worker via HTTP.
3. Tool worker calls its upstream service (e.g., Firecrawl API).
4. Tool worker returns standard envelope.
5. AX Gateway returns standardized response to caller.

---

## 2. Repository Layout (Target)

```text
ax-tool-framework/
├── README.md
├── docker-compose.yml
├── pyproject.toml
├── domain/
│   └── example_domain/
│       ├── manifest.yaml
│       └── policies.yaml
├── gateway/
│   ├── Dockerfile
│   └── src/
│       ├── main.py
│       ├── api.py
│       ├── manifest.py
│       ├── policy.py
│       ├── schemas.py
│       └── models.py
├── tools/
│   └── firecrawl/
│       ├── Dockerfile
│       └── src/
│           ├── main.py
│           ├── api.py
│           └── firecrawl_client.py
└── tests/
    ├── test_manifest_loading.py
    ├── test_gateway_run_tool.py
    └── test_firecrawl_worker_contract.py
```

---

## 3. Domain Packaging & Manifest

### 3.1 Domain Package Concept

A domain package includes:

- Domain manifest: `domain/<name>/manifest.yaml`
- Domain policies: `domain/<name>/policies.yaml`
- Gateway runtime selection via environment variables
- Tool worker image set

### 3.2 Manifest Format (v0.1)

`domain/<name>/manifest.yaml`

```yaml
domain_id: "example_domain"
version: "0.1"
tools:
  - tool_id: "firecrawl.crawl"
    display_name: "Firecrawl Crawl"
    description: "Crawl a URL and return extracted content using Firecrawl API"
    transport:
      type: "http"
      base_url: "http://tool-firecrawl:8080"
      endpoint: "/run"
    timeout_sec: 60
    input_schema_ref: "schemas/firecrawl_crawl_input.json"
    output_schema_ref: "schemas/firecrawl_crawl_output.json"
    egress_allowlist:
      - "api.firecrawl.dev:443"
```

Note: In v0.1, schemas may be implemented inline in `gateway/src/schemas.py` if needed, but `domain/<name>/schemas/*.json` is preferred.

---

## 4. Policies (Sandbox-level)

`domain/<name>/policies.yaml` (v0.1)

```yaml
concurrency:
  max_inflight: 8
  per_tool_max_inflight:
    firecrawl.crawl: 2

timeouts:
  default_tool_timeout_sec: 60

network:
  default_egress_policy: "deny"
  # tool-specific allowlist comes from manifest.egress_allowlist

logging:
  level: "INFO"
  include_request_body: false
```

Policy semantics:

- Default egress policy is deny (metadata/check-level in v0.1).
- Per-tool concurrency is enforced by gateway.

---

## 5. Tool Contract (Gateway <-> Worker)

### 5.1 Worker HTTP Endpoint

All tool workers MUST expose:

- `POST /run`
- Request: JSON
- Response: JSON
- Content-Type: `application/json`

### 5.2 Standard Envelope

Request envelope (Gateway -> Worker):

```json
{
  "meta": {
    "trace_id": "string",
    "tool_run_id": "string",
    "domain_id": "string",
    "deadline_ms": 1700000000000
  },
  "input": {}
}
```

Response envelope (Worker -> Gateway), success:

```json
{
  "ok": true,
  "meta": {
    "trace_id": "string",
    "tool_run_id": "string",
    "duration_ms": 1234
  },
  "output": {}
}
```

Response envelope (Worker -> Gateway), error:

```json
{
  "ok": false,
  "meta": {
    "trace_id": "string",
    "tool_run_id": "string",
    "duration_ms": 1234
  },
  "error": {
    "code": "UPSTREAM_ERROR | VALIDATION_ERROR | TIMEOUT | INTERNAL",
    "message": "string",
    "retryable": true,
    "details": {}
  }
}
```

Gateway behavior:

- If worker returns `ok=false`, gateway forwards that error in gateway response format.
- If worker returns non-standard payload, gateway returns `INTERNAL`.

---

## 6. Gateway Public API (LLM/Agent Entry)

### 6.1 Run Tool

`POST /v1/tools/{tool_id}:run`

Request:

```json
{
  "input": {}
}
```

Success response:

```json
{
  "ok": true,
  "tool_id": "firecrawl.crawl",
  "tool_run_id": "string",
  "output": {},
  "meta": {
    "trace_id": "string",
    "duration_ms": 1234
  }
}
```

Error response:

```json
{
  "ok": false,
  "tool_id": "firecrawl.crawl",
  "tool_run_id": "string",
  "error": {
    "code": "string",
    "message": "string",
    "retryable": true,
    "details": {}
  },
  "meta": {
    "trace_id": "string",
    "duration_ms": 1234
  }
}
```

### 6.2 List Tools (Optional in v0.1)

`GET /v1/tools`

Returns tool metadata for discovery/UI.

---

## 7. Sample Common Tool: Firecrawl API Worker

### 7.1 Purpose

Provide shared web crawl/scrape extraction capability for domains.

### 7.2 Environment Variables (Worker)

- `FIRECRAWL_API_KEY` (required)
- `FIRECRAWL_BASE_URL` (optional, default: `https://api.firecrawl.dev`)

### 7.3 Tool ID

- `firecrawl.crawl`

### 7.4 Input/Output Schemas (Concept)

Input:

```json
{
  "url": "https://example.com",
  "mode": "crawl | scrape",
  "max_pages": 10, // crawl mode only
  "formats": ["markdown", "html", "text"]
}
```

Output:

```json
{
  "source_url": "https://example.com",
  "items": [
    {
      "url": "string",
      "title": "string",
      "content": "string",
      "format": "markdown"
    }
  ],
  "stats": {
    "pages": 3
  }
}
```

v0.1 implementation guide:

- Worker-side input validation can stay minimal (at least `url`).
- Gateway performs schema validation.
- Upstream failure must be returned as `ok=false` with `UPSTREAM_ERROR`.

---

## 8. Containerization & Deployment (v0.1)

### 8.1 docker-compose Baseline

`docker-compose.yml` MUST include:

- `gateway` service
- `tool-firecrawl` service
- `DOMAIN_ID` + manifest/policies env vars

Example:

```yaml
services:
  gateway:
    build: ./gateway
    environment:
      - DOMAIN_ID=example_domain
      - DOMAIN_MANIFEST_PATH=/app/domain/example_domain/manifest.yaml
      - DOMAIN_POLICIES_PATH=/app/domain/example_domain/policies.yaml
    ports:
      - "8000:8000"
    volumes:
      - ./domain:/app/domain:ro

  tool-firecrawl:
    build: ./tools/firecrawl
    environment:
      - FIRECRAWL_API_KEY=${FIRECRAWL_API_KEY}
    ports:
      - "8080:8080"
```

### 8.2 Network Isolation (v0.1 Scope)

v0.1 does not require full runtime egress enforcement.

Required for v0.1:

- Load `egress_allowlist` from manifest.
- Keep policy metadata/check hooks in gateway.
- Defer hard egress controls (iptables/k8s policy) to later versions.

---

## 9. Non-Goals (v0.1)

- Kubernetes deployment/operations.
- Secret manager integration.
- Full hard egress enforcement.
- Concrete GraphDB/VectorDB adapters.

---

## 10. Definition of Done (v0.1)

Required:

- Gateway loads domain manifest/policies.
- `/v1/tools/{tool_id}:run` works.
- Per-tool concurrency limit works.
- Timeout handling works.
- `tool-firecrawl` implements `/run` contract.
- Tests pass:
  - Manifest loading test.
  - Gateway-to-worker run contract test (mock/local).
  - Worker standard envelope test.

Recommended:

- `trace_id`/`tool_run_id` included in logs.
- Reasonable default `retryable` behavior per error class.

---

## 11. Implementation Tasks (Codex-friendly)

- Task 1: Repo skeleton + docker-compose
- Task 2: Gateway (FastAPI/Uvicorn) + manifest loader
- Task 3: Policy module (concurrency + timeout)
- Task 4: Worker contract + Firecrawl worker
- Task 5: Tests + local run docs

---

## 12. Local Run (v0.1)

Prerequisites:

- Docker Desktop (or Docker Engine)
- Python 3.11+
- `FIRECRAWL_API_KEY` set in environment

Start services:

```bash
docker compose up --build
```

Health checks:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8080/healthz
```

List tools:

```bash
curl http://localhost:8000/v1/tools
```

Run `firecrawl.crawl`:

```bash
curl -X POST http://localhost:8000/v1/tools/firecrawl.crawl:run \
  -H "Content-Type: application/json" \
  -d '{"input":{"url":"https://example.com","mode":"scrape","formats":["markdown"]}}'
```

Run tests locally:

```bash
pip install -e .[dev]
pytest -q
```

---

## Notes / Future Extensions (v0.2+)

- DB adapters for vector/graph stores.
- MCP server mode in gateway.
- Strong runtime network controls (k8s/eBPF/iptables).

---

## Assumptions (v0.1)

- The normative interface contracts are the envelope/API sections in this README.
- Firecrawl upstream endpoint details can vary, so worker implementation should keep the HTTP client isolated behind `firecrawl_client.py` and map failures to `UPSTREAM_ERROR`.
- Egress allowlist in v0.1 is loaded and checked at policy metadata level; hard network enforcement is out of scope for this version.
- When manifest/policies fail to load at startup, the gateway still boots and returns HTTP 500 with a clear error message on `/healthz` and `/v1/tools`.
- Unknown `tool_id` uses gateway error code `NOT_FOUND` with HTTP 404.
- Worker `ok=false` responses are passed through in gateway envelope with HTTP 200.
- Worker maps `mode` to Firecrawl endpoints `/v1/scrape` and `/v1/crawl` using `FIRECRAWL_BASE_URL`; request body uses `url`, optional `formats`, and `maxPages` only for `crawl` mode.
