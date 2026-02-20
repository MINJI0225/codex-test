from __future__ import annotations

import asyncio
import time
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError

from src.manifest import load_domain_config, resolve_domain_paths
from src.models import ToolListItem, ToolConfig
from src.policy import PolicyEnforcer
from src.schemas import validate_tool_input, validation_error_details

app = FastAPI(title="AX Gateway", version="0.1")

app.state.manifest = None
app.state.policies = None
app.state.domain_dir = None
app.state.policy = None
app.state.load_error = None


def _gateway_error(
    *,
    status_code: int,
    tool_id: str,
    tool_run_id: str,
    trace_id: str,
    start_ms: int,
    code: str,
    message: str,
    retryable: bool,
    details: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "ok": False,
            "tool_id": tool_id,
            "tool_run_id": tool_run_id,
            "error": {
                "code": code,
                "message": message,
                "retryable": retryable,
                "details": details or {},
            },
            "meta": {
                "trace_id": trace_id,
                "duration_ms": max(0, int(time.time() * 1000) - start_ms),
            },
        },
    )


def _tool_map() -> dict[str, ToolConfig]:
    return {tool.tool_id: tool for tool in app.state.manifest.tools}


@app.on_event("startup")
def startup_load_domain() -> None:
    try:
        _domain_id, manifest_path, _policies_path = resolve_domain_paths()
        manifest, policies = load_domain_config()
        app.state.manifest = manifest
        app.state.policies = policies
        app.state.domain_dir = manifest_path.parent
        app.state.policy = PolicyEnforcer.from_config(policies, manifest.tools)
        app.state.load_error = None
    except Exception as exc:
        app.state.load_error = f"Failed to load domain manifest/policies: {exc}"


def ensure_loaded() -> None:
    if app.state.load_error:
        raise HTTPException(status_code=500, detail=app.state.load_error)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    ensure_loaded()
    return {"ok": True}


@app.get("/v1/tools", response_model=list[ToolListItem])
def list_tools() -> list[ToolListItem]:
    ensure_loaded()
    return [
        ToolListItem(
            tool_id=tool.tool_id,
            display_name=tool.display_name,
            description=tool.description,
        )
        for tool in app.state.manifest.tools
    ]


async def call_worker(tool: ToolConfig, payload: dict, timeout_sec: int) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=timeout_sec) as client:
        url = f"{tool.transport.base_url.rstrip('/')}{tool.transport.endpoint}"
        response = await client.post(url, json=payload)
        return response.status_code, response.json()


@app.post("/v1/tools/{tool_id}:run")
async def run_tool(tool_id: str, request: Request):
    ensure_loaded()
    start_ms = int(time.time() * 1000)
    trace_id = str(uuid.uuid4())
    tool_run_id = str(uuid.uuid4())

    tools = _tool_map()
    tool = tools.get(tool_id)
    if tool is None:
        return _gateway_error(
            status_code=404,
            tool_id=tool_id,
            tool_run_id=tool_run_id,
            trace_id=trace_id,
            start_ms=start_ms,
            code="NOT_FOUND",
            message=f"Unknown tool_id: {tool_id}",
            retryable=False,
        )

    try:
        body = await request.json()
    except Exception:
        return _gateway_error(
            status_code=400,
            tool_id=tool_id,
            tool_run_id=tool_run_id,
            trace_id=trace_id,
            start_ms=start_ms,
            code="VALIDATION_ERROR",
            message="Request body must be valid JSON",
            retryable=False,
        )

    input_payload = body.get("input") if isinstance(body, dict) else None
    if not isinstance(input_payload, dict):
        return _gateway_error(
            status_code=400,
            tool_id=tool_id,
            tool_run_id=tool_run_id,
            trace_id=trace_id,
            start_ms=start_ms,
            code="VALIDATION_ERROR",
            message="Request body must include an object field: input",
            retryable=False,
        )

    try:
        validate_tool_input(app.state.domain_dir, tool, input_payload)
    except ValidationError as exc:
        return _gateway_error(
            status_code=400,
            tool_id=tool_id,
            tool_run_id=tool_run_id,
            trace_id=trace_id,
            start_ms=start_ms,
            code="VALIDATION_ERROR",
            message="Input schema validation failed",
            retryable=False,
            details=validation_error_details(exc),
        )

    timeout_sec = app.state.policy.timeout_for(tool)
    deadline_ms = int(time.time() * 1000) + (timeout_sec * 1000)
    worker_payload = {
        "meta": {
            "trace_id": trace_id,
            "tool_run_id": tool_run_id,
            "domain_id": app.state.manifest.domain_id,
            "deadline_ms": deadline_ms,
        },
        "input": input_payload,
    }

    limiter = app.state.policy.limiter_for(tool_id)
    async with limiter:
        try:
            status_code, worker_json = await call_worker(tool, worker_payload, timeout_sec)
        except httpx.TimeoutException:
            return _gateway_error(
                status_code=504,
                tool_id=tool_id,
                tool_run_id=tool_run_id,
                trace_id=trace_id,
                start_ms=start_ms,
                code="TIMEOUT",
                message="Worker request timed out",
                retryable=True,
            )
        except Exception as exc:
            return _gateway_error(
                status_code=502,
                tool_id=tool_id,
                tool_run_id=tool_run_id,
                trace_id=trace_id,
                start_ms=start_ms,
                code="UPSTREAM_ERROR",
                message=f"Worker call failed: {exc}",
                retryable=True,
            )

    if status_code != 200 or not isinstance(worker_json, dict):
        return _gateway_error(
            status_code=502,
            tool_id=tool_id,
            tool_run_id=tool_run_id,
            trace_id=trace_id,
            start_ms=start_ms,
            code="UPSTREAM_ERROR",
            message="Worker returned non-200 or invalid JSON",
            retryable=True,
        )

    worker_ok = worker_json.get("ok")
    worker_meta = worker_json.get("meta") if isinstance(worker_json.get("meta"), dict) else {}
    worker_trace = worker_meta.get("trace_id", trace_id)
    worker_run = worker_meta.get("tool_run_id", tool_run_id)

    if worker_ok is True:
        return {
            "ok": True,
            "tool_id": tool_id,
            "tool_run_id": worker_run,
            "output": worker_json.get("output", {}),
            "meta": {
                "trace_id": worker_trace,
                "duration_ms": max(0, int(time.time() * 1000) - start_ms),
            },
        }

    if worker_ok is False:
        worker_error = worker_json.get("error") if isinstance(worker_json.get("error"), dict) else {}
        return _gateway_error(
            status_code=200,
            tool_id=tool_id,
            tool_run_id=worker_run,
            trace_id=worker_trace,
            start_ms=start_ms,
            code=str(worker_error.get("code", "INTERNAL")),
            message=str(worker_error.get("message", "Worker returned error")),
            retryable=bool(worker_error.get("retryable", False)),
            details=worker_error.get("details") if isinstance(worker_error.get("details"), dict) else {},
        )

    return _gateway_error(
        status_code=502,
        tool_id=tool_id,
        tool_run_id=tool_run_id,
        trace_id=trace_id,
        start_ms=start_ms,
        code="UPSTREAM_ERROR",
        message="Worker returned invalid envelope",
        retryable=True,
    )