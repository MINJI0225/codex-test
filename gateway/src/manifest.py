from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.models import DomainManifest, DomainPolicies


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML root must be object: {path}")
    return data


def resolve_domain_paths() -> tuple[str, Path, Path]:
    domain_id = os.getenv("DOMAIN_ID", "example_domain")
    manifest_path = Path(
        os.getenv("DOMAIN_MANIFEST_PATH", f"domain/{domain_id}/manifest.yaml")
    )
    policies_path = Path(
        os.getenv("DOMAIN_POLICIES_PATH", f"domain/{domain_id}/policies.yaml")
    )
    return domain_id, manifest_path, policies_path


def load_manifest(path: str | Path) -> DomainManifest:
    return DomainManifest.model_validate(_load_yaml(Path(path)))


def load_policies(path: str | Path) -> DomainPolicies:
    return DomainPolicies.model_validate(_load_yaml(Path(path)))


def load_domain_config() -> tuple[DomainManifest, DomainPolicies]:
    _domain_id, manifest_path, policies_path = resolve_domain_paths()
    manifest = load_manifest(manifest_path)
    policies = load_policies(policies_path)
    return manifest, policies