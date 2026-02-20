from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import ValidationError, validate

from src.models import ToolConfig


def load_schema(domain_dir: Path, schema_ref: str | None) -> dict[str, Any] | None:
    if not schema_ref:
        return None
    schema_path = domain_dir / schema_ref
    if not schema_path.exists():
        return None
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_tool_input(domain_dir: Path, tool: ToolConfig, payload: dict[str, Any]) -> None:
    schema = load_schema(domain_dir, tool.input_schema_ref)
    if schema is None:
        return
    validate(instance=payload, schema=schema)


def validation_error_details(exc: ValidationError) -> dict[str, Any]:
    return {
        "path": [str(p) for p in exc.path],
        "message": exc.message,
        "validator": exc.validator,
    }