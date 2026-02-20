from __future__ import annotations

from pydantic import BaseModel, Field


class TransportConfig(BaseModel):
    type: str
    base_url: str
    endpoint: str


class ToolConfig(BaseModel):
    tool_id: str
    display_name: str
    description: str
    transport: TransportConfig
    timeout_sec: int = 60
    input_schema_ref: str | None = None
    output_schema_ref: str | None = None
    egress_allowlist: list[str] = Field(default_factory=list)


class DomainManifest(BaseModel):
    domain_id: str
    version: str
    tools: list[ToolConfig]


class ConcurrencyConfig(BaseModel):
    max_inflight: int = 8
    per_tool_max_inflight: dict[str, int] = Field(default_factory=dict)


class TimeoutConfig(BaseModel):
    default_tool_timeout_sec: int = 60


class NetworkConfig(BaseModel):
    default_egress_policy: str = "deny"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    include_request_body: bool = False


class DomainPolicies(BaseModel):
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    timeouts: TimeoutConfig = Field(default_factory=TimeoutConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class ToolListItem(BaseModel):
    tool_id: str
    display_name: str
    description: str


class WorkerError(BaseModel):
    code: str
    message: str
    retryable: bool
    details: dict = Field(default_factory=dict)