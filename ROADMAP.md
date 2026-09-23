# AI Harness - Roadmap

The roadmap is gate-driven. A version is not considered complete because code exists; its acceptance criteria must pass in a repeatable environment.

## v0.2.x - Stage baseline

Goal: prove the single-agent architecture works end to end.

Scope:
- FastAPI API;
- PostgreSQL persistence;
- owner-scoped sessions/messages;
- Agent Runtime and max-step guard;
- OpenAI-compatible provider adapter;
- Ollama, 9Router and OpenRouter;
- automatic fallback;
- `private=true` local-only routing;
- Tool Registry;
- filesystem/read-only shell sandbox baseline;
- RAG + pgvector;
- MCP registry/client;
- bootstrap JWT/RBAC;
- audit events/logs;
- Docker/Compose;
- CI baseline.

Acceptance gate:
1. Fresh clone builds locally.
2. `/health` and authentication pass.
3. Ollama chat passes.
4. Session history persists and remains owner-scoped.
5. Filesystem/shell restrictions are verified.
6. RAG ingest/search/tool call passes.
7. At least one test MCP server can be registered and invoked.
8. OpenRouter and 9Router explicit-provider tests pass when credentials are configured.
9. Automatic fallback behaves as designed.
10. `private=true` never uses a cloud provider.
11. Tests and README reproduce the process.

Exit target: v0.2.1+ validated locally, then deployed to Stage VPS.

## v0.3 - Production Candidate

Goal: make the runtime operationally safe and observable.

Planned capabilities:
- OIDC integration;
- complete RBAC/policy engine;
- approval engine with durable decisions;
- Alembic migrations;
- ephemeral Sandbox Manager for EXEC tools;
- OpenTelemetry traces/metrics/log correlation;
- rate limiting;
- provider/MCP timeouts, retries and circuit breakers;
- Redis/worker queue for long-running tasks where justified;
- structured health/readiness checks;
- backup/restore procedure;
- deployment hardening and immutable container releases.

Acceptance gate:
- security controls in `SECURITY.md` required for production candidate are demonstrated;
- migration and rollback path is tested;
- failure of one model provider does not corrupt a session;
- sandbox escape assumptions are documented and tested at the selected isolation level;
- traces identify request -> model -> tool -> result;
- backup restore is tested.

## v0.4 - Knowledge Platform

Goal: turn RAG into governed enterprise knowledge access.

Planned capabilities:
- PDF, DOCX, XLSX, Markdown and HTML ingestion;
- metadata extraction;
- collections/namespaces;
- document ACL/group filters;
- source citations;
- hybrid retrieval;
- reranking;
- ingestion jobs/status;
- document update/delete lifecycle;
- embedding-model migration strategy;
- prompt-injection defenses for retrieved content.

Acceptance gate:
- unauthorized users cannot retrieve restricted chunks;
- deletion removes content from retrieval;
- citations identify source documents;
- ingestion is repeatable and observable.

## v0.5 - Agent Platform

Goal: support specialized agents without duplicating platform controls.

Candidate agents:
- research;
- coding;
- infrastructure;
- governance/document analysis.

Rules:
- all agents use the same identity/policy layer;
- all model access goes through Model Router;
- all executable capabilities go through Tool Registry;
- all knowledge access goes through governed RAG;
- multi-agent orchestration must not bypass audit or approvals.

Acceptance gate:
- specialized agents can be added primarily through configuration/prompts/tools rather than copied platform code;
- cross-agent delegation is traceable and policy-controlled.

## v1.0 - Production platform

Goal: stable corporate AI execution layer for applications, agents and automations.

Expected characteristics:
- hardened identity and policy;
- local and cloud model routing;
- governed knowledge access;
- secure MCP/tool ecosystem;
- isolated execution;
- observability and audit;
- documented SLOs, backup and incident response;
- reproducible release/deployment process.

## Deferred until justified

The following should not be added merely for architectural fashion:
- Kubernetes;
- multiple databases for the same durable state;
- multi-agent orchestration before single-agent stability;
- a custom vector database while pgvector satisfies requirements;
- GPU-direct code inside the Harness when an inference server can provide a stable API;
- complex event buses before queue/workload needs demonstrate them.
