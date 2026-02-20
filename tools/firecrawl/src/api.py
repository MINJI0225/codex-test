from __future__ import annotations

import time

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.firecrawl_client import FirecrawlClient, FirecrawlClientError

app = FastAPI(title="AX Firecrawl Worker", version="0.1")


def _error_response(*, trace_id: str, tool_run_id: str, start_ms: int, code: str, message: str, retryable: bool, details: dict | None = None, status_code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "meta": {
                "trace_id": trace_id,
                "tool_run_id": tool_run_id,
                "duration_ms": max(0, int(time.time() * 1000) - start_ms),
            },
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "details": details or {},
            },
        },
    )


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/run")
async def run(request: Request):
    start_ms = int(time.time() * 1000)

    try:
        body = await request.json()
    except Exception:
        return _error_response(
            trace_id="",
            tool_run_id="",
            start_ms=start_ms,
            code="VALIDATION_ERROR",
            message="Request body must be valid JSON",
            retryable=False,
        )

    if not isinstance(body, dict):
        return _error_response(
            trace_id="",
            tool_run_id="",
            start_ms=start_ms,
            code="VALIDATION_ERROR",
            message="Request envelope must be an object",
            retryable=False,
        )

    meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
    trace_id = str(meta.get("trace_id", ""))
    tool_run_id = str(meta.get("tool_run_id", ""))

    input_payload = body.get("input") if isinstance(body.get("input"), dict) else None
    if input_payload is None:
        return _error_response(
            trace_id=trace_id,
            tool_run_id=tool_run_id,
            start_ms=start_ms,
            code="VALIDATION_ERROR",
            message="Request envelope must include input object",
            retryable=False,
        )

    url = input_payload.get("url")
    if not isinstance(url, str) or not url:
        return _error_response(
            trace_id=trace_id,
            tool_run_id=tool_run_id,
            start_ms=start_ms,
            code="VALIDATION_ERROR",
            message="input.url is required",
            retryable=False,
        )

    normalized_input = {
        "url": url,
        "mode": input_payload.get("mode", "scrape"),
        "max_pages": input_payload.get("max_pages"),
        "formats": input_payload.get("formats"),
    }

    try:
        output = await FirecrawlClient().run(normalized_input)
    except FirecrawlClientError as exc:
        return _error_response(
            trace_id=trace_id,
            tool_run_id=tool_run_id,
            start_ms=start_ms,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
            details=exc.details,
        )
    except Exception as exc:
        return _error_response(
            trace_id=trace_id,
            tool_run_id=tool_run_id,
            start_ms=start_ms,
            code="INTERNAL",
            message=f"Internal worker error: {exc}",
            retryable=False,
        )

    return {
        "ok": True,
        "meta": {
            "trace_id": trace_id,
            "tool_run_id": tool_run_id,
            "duration_ms": max(0, int(time.time() * 1000) - start_ms),
        },
        "output": output,
    }