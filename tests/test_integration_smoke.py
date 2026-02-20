from fastapi.testclient import TestClient

from gateway.src.main import app


def test_gateway_smoke_with_mocked_worker(monkeypatch):
    async def fake_call_worker(tool, payload, timeout_sec):
        return 200, {
            "ok": True,
            "meta": {
                "trace_id": payload["meta"]["trace_id"],
                "tool_run_id": payload["meta"]["tool_run_id"],
                "duration_ms": 2,
            },
            "output": {
                "source_url": payload["input"]["url"],
                "items": [],
                "stats": {"pages": 0},
            },
        }

    monkeypatch.setattr("gateway.src.main.call_worker", fake_call_worker)

    with TestClient(app) as client:
        health = client.get("/healthz")
        tools = client.get("/v1/tools")
        run = client.post(
            "/v1/tools/firecrawl.crawl:run",
            json={"input": {"url": "https://example.com", "mode": "scrape"}},
        )

    assert health.status_code == 200
    assert health.json() == {"ok": True}

    assert tools.status_code == 200
    assert isinstance(tools.json(), list)
    assert tools.json()[0]["tool_id"] == "firecrawl.crawl"

    assert run.status_code == 200
    body = run.json()
    assert body["ok"] is True
    assert body["tool_id"] == "firecrawl.crawl"
    assert body["output"]["source_url"] == "https://example.com"