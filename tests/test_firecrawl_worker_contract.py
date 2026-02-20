from fastapi.testclient import TestClient

from tools.firecrawl.src.api import app
from tools.firecrawl.src.firecrawl_client import FirecrawlClientError


def _base_envelope(input_payload: dict):
    return {
        "meta": {
            "trace_id": "trace-1",
            "tool_run_id": "run-1",
            "domain_id": "example_domain",
            "deadline_ms": 1700000000000,
        },
        "input": input_payload,
    }


def test_worker_healthz():
    with TestClient(app) as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_worker_run_success_envelope(monkeypatch):
    async def fake_run(self, payload):
        assert payload["url"] == "https://example.com"
        assert payload["mode"] == "scrape"
        return {
            "source_url": "https://example.com",
            "items": [{"url": "https://example.com", "title": "t", "content": "c", "format": "markdown"}],
            "stats": {"pages": 1},
        }

    monkeypatch.setattr("tools.firecrawl.src.firecrawl_client.FirecrawlClient.run", fake_run)

    with TestClient(app) as client:
        resp = client.post("/run", json=_base_envelope({"url": "https://example.com"}))

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["meta"]["trace_id"] == "trace-1"
    assert body["meta"]["tool_run_id"] == "run-1"
    assert "output" in body


def test_worker_run_validation_error_missing_url():
    with TestClient(app) as client:
        resp = client.post("/run", json=_base_envelope({"mode": "scrape"}))

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_worker_run_upstream_error_passthrough(monkeypatch):
    async def fake_run(self, payload):
        raise FirecrawlClientError(
            code="UPSTREAM_ERROR",
            message="upstream failed",
            retryable=True,
            details={"status": 500},
        )

    monkeypatch.setattr("tools.firecrawl.src.firecrawl_client.FirecrawlClient.run", fake_run)

    with TestClient(app) as client:
        resp = client.post("/run", json=_base_envelope({"url": "https://example.com"}))

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UPSTREAM_ERROR"
    assert body["error"]["retryable"] is True
    assert body["meta"]["trace_id"] == "trace-1"


def test_worker_run_timeout_error_passthrough(monkeypatch):
    async def fake_run(self, payload):
        raise FirecrawlClientError(
            code="TIMEOUT",
            message="timeout",
            retryable=True,
        )

    monkeypatch.setattr("tools.firecrawl.src.firecrawl_client.FirecrawlClient.run", fake_run)

    with TestClient(app) as client:
        resp = client.post("/run", json=_base_envelope({"url": "https://example.com", "mode": "crawl"}))

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "TIMEOUT"
    assert body["error"]["retryable"] is True