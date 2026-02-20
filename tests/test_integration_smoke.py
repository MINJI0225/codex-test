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
        domain = client.get("/v1/domain")
        tools = client.get("/v1/tools")
        run = client.post(
            "/v1/tools/firecrawl.crawl:run",
            json={"input": {"url": "https://example.com", "mode": "scrape"}},
        )

    assert health.status_code == 200
    assert health.json() == {"ok": True}

    assert domain.status_code == 200
    assert domain.json() == {"domain_id": "example_domain", "version": "0.1"}

    assert tools.status_code == 200
    tools_json = tools.json()
    assert tools_json["domain_id"] == "example_domain"
    assert tools_json["version"] == "0.1"
    assert isinstance(tools_json["tools"], list)
    assert tools_json["tools"][0]["tool_id"] == "firecrawl.crawl"
    assert tools_json["tools"][0]["kind"] == "service_worker"
    assert "capabilities" in tools_json["tools"][0]
    assert "timeout_sec" in tools_json["tools"][0]
    assert "egress_allowlist" in tools_json["tools"][0]

    assert run.status_code == 200
    body = run.json()
    assert body["ok"] is True
    assert body["tool_id"] == "firecrawl.crawl"
    assert body["output"]["source_url"] == "https://example.com"
