# ADR-008: Every tool carries an effect class; classification fails closed

Status: Proposed (implemented in PR #1; accept on merge)

## Context

SECURITY.md §4 defines effect classes (READ, QUERY, WRITE, EXEC, DESTRUCTIVE) and requires tools to fail closed when policy metadata is missing. v0.2.0 only had a boolean `mutating` flag that defaulted to `False`, so an unclassified tool ran without approval. MCP servers self-declare annotations (`readOnlyHint`, `destructiveHint`), which SECURITY.md §8 and ADR-004 say must not be trusted as policy.

## Decision

- The Tool Registry stores an `Effect` for every tool. Registering without one logs a warning and classifies the tool as DESTRUCTIVE. Unknown tool names are treated as DESTRUCTIVE.
- DESTRUCTIVE tools default to the `admin` role only (elevated role).
- The effects that need approval (ADR-007) are configured with `APPROVAL_REQUIRED_EFFECTS`, default `WRITE,DESTRUCTIVE`.
- Native tools: `read_file`, `list_files` = READ; `rag_search` = QUERY; `shell` = EXEC. In v0.2 EXEC runs under the application sandbox (read-only allowlist) and is not approval-gated by default; this is not a hostile-code boundary (SECURITY.md §5).
- MCP tools: only the administrator can grant QUERY, by listing remote tool names in `read_only_tools` when registering the server. Server annotations can only make a tool more restrictive: `readOnlyHint` or `destructiveHint=false` gives WRITE; anything else gives DESTRUCTIVE (the MCP default for `destructiveHint` is true).
- `GET /tools` (admin) exposes the effective class, roles, source and approval requirement of every tool.

## Consequences

Positive: one enforcement model for native and MCP tools; a new tool or MCP server cannot silently gain automatic execution.

Trade-off: administrators must classify read-only MCP tools explicitly; until they do, those tools need approval.

Follow-up: per-tool role overrides, argument-level policy (e.g. path or table restrictions), a policy engine (ROADMAP v0.3).
