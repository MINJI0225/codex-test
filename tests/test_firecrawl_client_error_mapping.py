import pytest

from tools.firecrawl.src.firecrawl_client import FirecrawlClient, FirecrawlClientError


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.text = "error"

    def json(self):
        return {"status": self.status_code}


class _FakeClient:
    def __init__(self, response: _FakeResponse):
        self._response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        return self._response


@pytest.mark.asyncio
async def test_firecrawl_401_is_retryable(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "dummy")
    monkeypatch.setattr(
        "tools.firecrawl.src.firecrawl_client.httpx.AsyncClient",
        lambda timeout: _FakeClient(_FakeResponse(401)),
    )

    with pytest.raises(FirecrawlClientError) as exc:
        await FirecrawlClient().run({"url": "https://example.com", "mode": "scrape"})

    assert exc.value.code == "UPSTREAM_ERROR"
    assert exc.value.retryable is True


@pytest.mark.asyncio
async def test_firecrawl_404_is_not_retryable(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "dummy")
    monkeypatch.setattr(
        "tools.firecrawl.src.firecrawl_client.httpx.AsyncClient",
        lambda timeout: _FakeClient(_FakeResponse(404)),
    )

    with pytest.raises(FirecrawlClientError) as exc:
        await FirecrawlClient().run({"url": "https://example.com", "mode": "scrape"})

    assert exc.value.code == "UPSTREAM_ERROR"
    assert exc.value.retryable is False


@pytest.mark.asyncio
async def test_firecrawl_500_is_retryable(monkeypatch):
    monkeypatch.setenv("FIRECRAWL_API_KEY", "dummy")
    monkeypatch.setattr(
        "tools.firecrawl.src.firecrawl_client.httpx.AsyncClient",
        lambda timeout: _FakeClient(_FakeResponse(500)),
    )

    with pytest.raises(FirecrawlClientError) as exc:
        await FirecrawlClient().run({"url": "https://example.com", "mode": "scrape"})

    assert exc.value.code == "UPSTREAM_ERROR"
    assert exc.value.retryable is True
