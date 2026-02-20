from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.models import DomainPolicies, ToolConfig


@dataclass
class PolicyEnforcer:
    tool_limiters: dict[str, asyncio.Semaphore]
    default_tool_timeout_sec: int

    @classmethod
    def from_config(cls, policies: DomainPolicies, tools: list[ToolConfig]) -> "PolicyEnforcer":
        tool_limiters: dict[str, asyncio.Semaphore] = {}
        for tool in tools:
            tool_limit = policies.concurrency.per_tool_max_inflight.get(tool.tool_id, 1)
            tool_limiters[tool.tool_id] = asyncio.Semaphore(max(1, tool_limit))
        return cls(
            tool_limiters=tool_limiters,
            default_tool_timeout_sec=max(1, policies.timeouts.default_tool_timeout_sec),
        )

    def limiter_for(self, tool_id: str) -> asyncio.Semaphore:
        return self.tool_limiters.setdefault(tool_id, asyncio.Semaphore(1))

    def timeout_for(self, tool: ToolConfig) -> int:
        return max(1, tool.timeout_sec or self.default_tool_timeout_sec)