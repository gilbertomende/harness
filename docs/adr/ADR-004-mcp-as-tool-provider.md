# ADR-004: MCP servers are tool providers

Status: Accepted

## Context

MCP can expose powerful remote capabilities. Allowing MCP to bypass the Harness would fragment policy and audit.

## Decision

Import MCP capabilities into the central Tool Registry. MCP does not replace the Agent Runtime or policy layer. Each MCP tool is subject to identity, role, mutation/approval and audit controls.

## Consequences

Positive: one enforcement model for native and remote tools.

Trade-off: MCP discovery metadata cannot be blindly trusted; additional classification and administration are required for production.
