import httpx
from fastapi.testclient import TestClient

from gateway.src.main import app


class _LimiterProbe:
    def __init__(self):
        self.entered = 0

    async def __aenter__(self):
        self.entered += 1

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_run_tool_success(monkeypatch):
    async def fake_call_worker(tool, payload, timeout_sec):
        assert payload["meta"]["trace_id"]
        assert payload["meta"]["tool_run_id"]
        assert payload["input"]["url"] == "https://example.com"
        return 200, {
            "ok": True,
            "meta": {
                "trace_id": payload["meta"]["trace_id"],
                "tool_run_id": payload["meta"]["tool_run_id"],
                "duration_ms": 12,
            },
            "output": {"source_url": "https://example.com", "items": [], "stats": {"pages": 0}},
        }

    monkeypatch.setattr("gateway.src.main.call_worker", fake_call_worker)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/tools/firecrawl.crawl:run",
            json={"input": {"url": "https://example.com", "mode": "scrape"}},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["tool_id"] == "firecrawl.crawl"
    assert "tool_run_id" in body
    assert "trace_id" in body["meta"]


def test_run_tool_unknown_tool_returns_404():
    with TestClient(app) as client:
        resp = client.post("/v1/tools/not.exists:run", json={"input": {}})

    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "NOT_FOUND"


def test_run_tool_timeout_maps_to_timeout_error(monkeypatch):
    async def fake_call_worker(tool, payload, timeout_sec):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("gateway.src.main.call_worker", fake_call_worker)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/tools/firecrawl.crawl:run",
            json={"input": {"url": "https://example.com"}},
        )

    assert resp.status_code == 504
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "TIMEOUT"
    assert body["error"]["retryable"] is True


def test_run_tool_non_200_upstream_maps_to_upstream_error(monkeypatch):
    async def fake_call_worker(tool, payload, timeout_sec):
        return 503, {"detail": "down"}

    monkeypatch.setattr("gateway.src.main.call_worker", fake_call_worker)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/tools/firecrawl.crawl:run",
            json={"input": {"url": "https://example.com"}},
        )

    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "UPSTREAM_ERROR"


def test_run_tool_worker_ok_false_passthrough(monkeypatch):
    async def fake_call_worker(tool, payload, timeout_sec):
        return 200, {
            "ok": False,
            "meta": {
                "trace_id": payload["meta"]["trace_id"],
                "tool_run_id": payload["meta"]["tool_run_id"],
                "duration_ms": 5,
            },
            "error": {
                "code": "UPSTREAM_ERROR",
                "message": "firecrawl failed",
                "retryable": True,
                "details": {"status": 500},
            },
        }

    monkeypatch.setattr("gateway.src.main.call_worker", fake_call_worker)

    with TestClient(app) as client:
        resp = client.post(
            "/v1/tools/firecrawl.crawl:run",
            json={"input": {"url": "https://example.com"}},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UPSTREAM_ERROR"
    assert body["error"]["retryable"] is True


def test_run_tool_uses_tool_limiter(monkeypatch):
    probe = _LimiterProbe()

    async def fake_call_worker(tool, payload, timeout_sec):
        return 200, {
            "ok": True,
            "meta": {
                "trace_id": payload["meta"]["trace_id"],
                "tool_run_id": payload["meta"]["tool_run_id"],
                "duration_ms": 1,
            },
            "output": {"source_url": payload["input"]["url"], "items": [], "stats": {"pages": 0}},
        }

    monkeypatch.setattr("gateway.src.main.call_worker", fake_call_worker)

    with TestClient(app) as client:
        client.app.state.policy.tool_limiters["firecrawl.crawl"] = probe
        resp = client.post(
            "/v1/tools/firecrawl.crawl:run",
            json={"input": {"url": "https://example.com"}},
        )

    assert resp.status_code == 200
    assert probe.entered == 1