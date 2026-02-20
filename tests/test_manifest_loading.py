from pathlib import Path

from gateway.src.manifest import load_domain_config, load_manifest, load_policies


def test_load_manifest_and_policies_from_domain_files() -> None:
    manifest = load_manifest(Path("domain/example_domain/manifest.yaml"))
    policies = load_policies(Path("domain/example_domain/policies.yaml"))

    assert manifest.domain_id == "example_domain"
    assert manifest.version == "0.1"
    assert len(manifest.tools) == 1
    assert manifest.tools[0].tool_id == "firecrawl.crawl"

    assert policies.concurrency.max_inflight == 8
    assert policies.concurrency.per_tool_max_inflight["firecrawl.crawl"] == 2


def test_load_domain_config_defaults(monkeypatch) -> None:
    monkeypatch.delenv("DOMAIN_ID", raising=False)
    monkeypatch.delenv("DOMAIN_MANIFEST_PATH", raising=False)
    monkeypatch.delenv("DOMAIN_POLICIES_PATH", raising=False)

    manifest, policies = load_domain_config()

    assert manifest.domain_id == "example_domain"
    assert policies.timeouts.default_tool_timeout_sec == 60