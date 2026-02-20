from __future__ import annotations

import os
from typing import Any

import httpx


class FirecrawlClientError(Exception):
    def __init__(self, code: str, message: str, retryable: bool, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}


class FirecrawlClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("FIRECRAWL_BASE_URL", "https://api.firecrawl.dev").rstrip("/")
        self.api_key = os.getenv("FIRECRAWL_API_KEY", "")

    async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise FirecrawlClientError(
                code="UPSTREAM_ERROR",
                message="FIRECRAWL_API_KEY is required",
                retryable=False,
            )

        mode = payload.get("mode", "scrape")
        if mode not in {"scrape", "crawl"}:
            raise FirecrawlClientError(
                code="VALIDATION_ERROR",
                message="mode must be one of: scrape, crawl",
                retryable=False,
            )

        endpoint = f"/v1/{mode}"
        url = f"{self.base_url}{endpoint}"

        request_body: dict[str, Any] = {"url": payload["url"]}
        # Firecrawl scrape endpoint can reject crawl-only params.
        if mode == "crawl" and payload.get("max_pages") is not None:
            request_body["maxPages"] = payload["max_pages"]
        if payload.get("formats") is not None:
            request_body["formats"] = payload["formats"]

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=request_body, headers=headers)
        except httpx.TimeoutException as exc:
            raise FirecrawlClientError(
                code="TIMEOUT",
                message="Firecrawl request timed out",
                retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise FirecrawlClientError(
                code="UPSTREAM_ERROR",
                message=f"Firecrawl HTTP error: {exc}",
                retryable=True,
            ) from exc

        if response.status_code >= 400:
            details: dict[str, Any]
            try:
                details = response.json() if isinstance(response.json(), dict) else {"body": response.text}
            except Exception:
                details = {"body": response.text}
            status_code = response.status_code
            if status_code == 401:
                retryable = True
            elif 400 <= status_code < 500:
                retryable = False
            else:
                retryable = True
            raise FirecrawlClientError(
                code="UPSTREAM_ERROR",
                message=f"Firecrawl returned status {status_code}",
                retryable=retryable,
                details=details,
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise FirecrawlClientError(
                code="UPSTREAM_ERROR",
                message="Firecrawl returned invalid JSON",
                retryable=True,
            ) from exc

        items: list[dict[str, Any]] = []
        source_url = payload["url"]
        pages = 0

        if isinstance(data, dict):
            if "url" in data and isinstance(data["url"], str):
                source_url = data["url"]
            if mode == "scrape":
                # Firecrawl scrape responses commonly return content under data.markdown.
                scrape_payload = data.get("data") if isinstance(data.get("data"), dict) else data
                item = {
                    "url": source_url,
                    "title": str(scrape_payload.get("title", "")),
                    "content": str(scrape_payload.get("markdown") or scrape_payload.get("content") or ""),
                    "format": "markdown",
                }
                items = [item]
                pages = 1 if item["content"] else 0
            else:
                raw_items = data.get("data") if isinstance(data.get("data"), list) else []
                for raw in raw_items:
                    if isinstance(raw, dict):
                        items.append(
                            {
                                "url": str(raw.get("url", source_url)),
                                "title": str(raw.get("title", "")),
                                "content": str(raw.get("markdown") or raw.get("content") or ""),
                                "format": "markdown",
                            }
                        )
                pages = len(items)

        return {
            "source_url": source_url,
            "items": items,
            "stats": {"pages": pages},
        }
