# AI Harness - Architecture Decisions

This document is the decision index. Detailed records live under `docs/adr/`.

## Decision summary

| ADR | Decision | Status | Consequence |
|---|---|---|---|
| ADR-001 | Prefer an OpenAI-compatible provider interface | Accepted | Provider changes do not rewrite the agent loop |
| ADR-002 | PostgreSQL is the durable system of record | Accepted | Sessions, audit, MCP registry and RAG share one durable platform |
| ADR-003 | RAG is owned by the Harness | Accepted | Knowledge remains independent of inference provider |
| ADR-004 | MCP servers are tool providers | Accepted | MCP capabilities pass through the central Tool Registry/policy layer |
| ADR-005 | Security decisions belong to the Harness | Accepted | LLM output cannot authorize privileged actions |
| ADR-006 | GitHub is source of truth | Accepted | Local/VPS state must be reproducible from versioned repository state |
| ADR-007 | Tool approvals are server-side and bound to one exact call | Proposed | Clients and models cannot self-approve; approvals are durable, single-use and audited |
| ADR-008 | Every tool carries an effect class; classification fails closed | Proposed | Unclassified and MCP-declared tools cannot gain automatic execution |

## Decision process

New material architectural choices should be recorded as ADRs when they affect security boundaries, persistence, public APIs, provider abstractions, deployment, data lifecycle or operational ownership.

An ADR should contain context, decision, consequences and follow-up work. Accepted ADRs are not silently rewritten when the decision changes: create a new ADR that supersedes the old one.

## Current non-ADR implementation choices

These are current baseline choices and may become ADRs if they become long-lived constraints:
- FastAPI for the HTTP service.
- Docker Compose for local and initial single-host stage deployment.
- pgvector for vector similarity storage.
- JWT/local administrator credentials only as a stage bootstrap mechanism; OIDC is the production target.
- Ollama as the local/private inference baseline.
- Vercel is reserved for an optional frontend, not the core stateful runtime.
- Deterministic homologation with an OpenAI-compatible stub and a demo MCP server (`compose.e2e.yaml`, `e2e/smoke.py`), run by CI; real-model checks with `e2e/real_model_check.py`.
- Until Alembic (ROADMAP v0.3), schema changes are additive and applied idempotently at startup in `app/db/core.py`.
