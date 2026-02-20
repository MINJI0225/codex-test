# AX Tool Framework

## Core Specification (Container-Isolated) v0.1

---

# I. Framework Core Specification

---

## 1. Purpose

AX Tool Framework defines a standardized execution environment for domain-specific tools.

The framework guarantees:

- Isolation of tool execution at container boundary.
- Standardized request/response envelope.
- Domain-scoped tool catalog.
- Deterministic tool execution routing.
- Policy enforcement (timeout, concurrency, egress metadata).

This document defines **normative contracts** for the framework.

---

## 2. Execution Invariants (Normative)

The following invariants MUST always hold:

1. Gateway MUST NOT execute tool business logic directly.
2. All tool execution MUST occur inside worker containers.
3. Every worker MUST expose `/run` and follow the standard envelope.
4. Each gateway instance MUST load exactly one domain package.
5. Tool Search MUST execute outside the sandbox.

---

## 3. Standard Tool Execution Contract

### 3.1 Request Envelope (Gateway <-> Worker)

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

### 3.2 Response Envelope (Worker <-> Gateway)

Success:

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

Error:

```json
{
  "ok": false,
  "meta": {...},
  "error": {
    "code": "UPSTREAM_ERROR | VALIDATION_ERROR | TIMEOUT | INTERNAL",
    "message": "string",
    "retryable": true,
    "details": {}
  }
}
```

---

## 4. Execution Model

### 4.1 v0.1 Execution Model

All tools are implemented as:

```yaml
kind: service_worker
```

Definition:

A service_worker is:

- A long-running container
- Exposes `/run`
- Executes tool logic internally or via upstream systems
- Isolated from gateway process

### 4.2 Execution Scope

The following are implemented inside service_worker:

- Python functions
- External HTTP APIs
- MCP upstream calls
- External OSS/library integrations

### 4.3 Future Extension (v0.2+)

Planned execution types:

- `job_worker` (ephemeral container per request)
- Hybrid execution modes

---

# II. Domain & Catalog Model

---

## 5. Domain Identity

### 5.1 Domain Endpoint

`GET /v1/domain`

```json
{
  "domain_id": "example_domain",
  "version": "0.1"
}
```

Purpose:

- Tool Search cache invalidation
- Domain swap detection
- Operational visibility

---

## 6. Domain-Scoped Tool Catalog

### 6.1 Endpoint

`GET /v1/tools`

Returns:

```json
{
  "domain_id": "example_domain",
  "version": "0.1",
  "tools": [...]
}
```

### 6.2 Required Fields Per Tool

Each tool entry MUST include:

- `tool_id`
- `display_name`
- `description`
- `capabilities`
- `timeout_sec`
- `egress_allowlist`

Optional:

- `transport_type`
- `transport_endpoint`
- `input_schema_ref`
- `output_schema_ref`

---

## 7. Tool Search Integration

### 7.1 Responsibility Split

Tool Search runs outside the sandbox.

Gateway responsibilities:

- Domain identity
- Domain catalog
- Tool execution

### 7.2 Cache Key

Tool Search cache key:

```text
(gateway_base_url, domain_id, version)
```

### 7.3 Cache Workflow

1. Call `/v1/domain`
2. Validate cache
3. If needed, call `/v1/tools`
4. Perform local search
5. Execute selected tool

---

# III. Domain Package Model

---

## 8. Domain Package Structure

Each gateway instance loads exactly one domain package.

A domain package contains:

- `manifest.yaml`
- `policies.yaml`
- Worker container image definitions

---

## 9. Manifest Specification

```yaml
domain_id: "example_domain"
version: "0.1"
tools:
  - tool_id: "firecrawl.crawl"
    kind: "service_worker"
    transport:
      type: "http"
      base_url: "http://tool-firecrawl:8080"
      endpoint: "/run"
    timeout_sec: 60
    egress_allowlist:
      - "api.firecrawl.dev:443"
```

---

## 10. Policy Model

Policies MUST support:

- Global concurrency limit
- Per-tool concurrency limit
- Default timeout
- Egress metadata allowlist
- Logging level

Hard network enforcement is out of scope for v0.1.

---

# IV. Tool Onboarding Model

---

## 11. Tool Kind Classification

Tools MUST declare:

```yaml
kind: service_worker
```

Future:

```yaml
kind: job_worker
```

---

## 12. Tool Onboarding Workflow

When introducing a new domain tool:

1. Classify tool as `service_worker`.
2. Implement worker container exposing `/run`.
3. Ensure standard envelope compliance.
4. Add tool entry in manifest.
5. Add tool metadata to catalog.
6. Validate via `/v1/tools` and `/v1/tools/{tool_id}:run`.

---

# V. Sample Tool Reference

---

## 13. Firecrawl API Worker

### Authentication

```text
Authorization: Bearer <FIRECRAWL_API_KEY>
```

### Endpoints

- `/v1/scrape`
- `/v1/crawl`

### Error Mapping

| Upstream Status | Framework Error |
| --- | --- |
| 401 | UPSTREAM_ERROR (retryable=true) |
| 4xx | UPSTREAM_ERROR (retryable=false) |
| 5xx | UPSTREAM_ERROR (retryable=true) |

---

# VI. Deployment & Operations

---

## 14. docker-compose Baseline

```yaml
services:
  gateway:
    build: ./gateway
    ...
  tool-firecrawl:
    build: ./tools/firecrawl
```

v0.1 model:

- All service_worker containers are always-on.
- Gateway routes by HTTP to workers.

---

# VII. Definition of Done

- Domain manifest loads.
- `/v1/domain` works.
- `/v1/tools` works.
- `/v1/tools/{tool_id}:run` works.
- Policy enforcement active.
- Worker envelope contract verified.

---

# VIII. Assumptions

- Gateway is single-domain.
- Tool Search is external.
- All tool execution occurs inside service_worker containers.
- Worker errors are mapped to standardized error taxonomy.
- Domain swap is achieved by replacing sandbox deployment.

---

# What Changed Structurally

We separated:

1. Core Execution Spec
2. Domain & Catalog Model
3. Tool Onboarding Model
4. Sample Tool Reference
5. Deployment/Operations

This makes:

- Core framework invariant
- Implementation pluggable
- Tool types extensible
- Domain onboarding deterministic
