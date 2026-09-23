# AI Harness - Architecture

Status: Baseline architecture
Target baseline: v0.2.x Stage
Repository: `gilbertomende/harness`

## 1. Purpose

AI Harness is a provider-independent execution layer for AI agents. Its job is to control sessions, context, model routing, tool execution, RAG, MCP integration, policy enforcement, audit and isolation without coupling applications to a specific LLM provider.

The central rule is: **the Harness owns agent behavior; the model is an inference dependency**.

## 2. Architectural principles

1. Provider independence: applications and the agent runtime do not depend on Ollama, 9Router or OpenRouter APIs directly.
2. Harness-owned security: model output and tool arguments are untrusted until policy checks succeed.
3. Local-first privacy: requests classified as private must not fall back to cloud providers.
4. PostgreSQL as system of record: sessions, messages, audit, MCP registry and RAG metadata remain centrally persisted.
5. RAG and MCP are capabilities exposed through the Tool Registry, not separate agent runtimes.
6. GitHub is the source of truth for code and architecture. Environments are deployments of versioned repository state.
7. Incremental complexity: multi-agent orchestration, queues and hostile-code sandboxes are introduced only after the single-agent runtime is stable.

## 3. Logical architecture

```text
Clients: Web / CLI / API / Automation
                |
             HTTPS
                |
        API / Reverse Proxy
                |
          FastAPI Harness
                |
   +------------+-------------+
   |            |             |
Identity     Agent Runtime   Audit
/RBAC        /Session       /Logs
                |
        +-------+-------+
        |       |       |
      Models   Tools    Context
        |       |       |
 Model Router  |     PostgreSQL
        |       |
 +------+------+---------+
 |      |      |          |
Ollama 9Router OpenRouter Tool Registry
                         /   |    \
                    Native  RAG   MCP
                              |     |
                           pgvector MCP Servers
```

## 4. Component responsibilities

### 4.1 FastAPI boundary

FastAPI exposes health, authentication, chat, RAG and MCP-management endpoints. HTTP handlers should validate transport-level input and delegate domain work. Provider-specific behavior must not live in route handlers.

### 4.2 Agent Runtime

The Agent Runtime owns the iterative loop:

```text
User request -> session/context -> model -> tool call?
                                      | no -> response
                                      | yes
                                      v
                                Tool Registry
                                      |
                                 Policy check
                                      |
                                Tool execution
                                      |
                                Tool result
                                      +----> model
```

Required controls are maximum steps, tool authorization, execution timeout, cancellation in a future release, and an auditable final outcome.

The current v0.2 implementation has a maximum-step guard and tool approval support. Cancellation and a dedicated policy engine are roadmap items.

### 4.3 Session and context

Sessions belong to an authenticated principal. Messages are persisted in PostgreSQL and reconstructed as model context. A session identifier must never permit access to another owner's history.

### 4.4 Model Router

The Model Router provides a stable interface to inference providers through an OpenAI-compatible adapter where practical.

Current providers:
- Ollama
- 9Router
- OpenRouter

Default automatic order in v0.2:

```text
normal request:  Ollama -> 9Router -> OpenRouter
private request: Ollama only
```

A caller may explicitly request a provider/model when policy allows it. A new provider should normally require a provider adapter/configuration change, not an Agent Runtime rewrite.

Future candidates include vLLM, SGLang, OpenAI, Azure OpenAI, Anthropic and Gemini adapters where useful.

### 4.5 Tool Registry

All executable capabilities are registered centrally. The registry is the enforcement point for tool metadata, role requirements, mutation classification and approval requirements.

Capability families:
- native filesystem/shell tools;
- RAG search;
- MCP-discovered tools;
- future application/domain tools.

### 4.6 RAG

RAG belongs to the Harness. The inference provider does not own the knowledge base.

```text
Document -> chunk -> embedding -> pgvector
                                  ^
Query -> embedding -> similarity search -> RAG tool -> Agent Runtime
```

Current v0.2 uses PostgreSQL + pgvector and a fixed embedding dimension matching the configured baseline embedding model. Future versions must make embedding migrations explicit and add metadata/ACL filtering, citations, lifecycle and reranking.

### 4.7 MCP

MCP is treated as a capability provider. Enabled MCP servers are registered in PostgreSQL and imported into the Tool Registry.

```text
Agent Runtime -> Tool Registry -> MCP Client -> MCP Server
```

MCP server responses and tool schemas are untrusted external input. Production policy must restrict allowed servers, transport, authentication, egress and tool permissions.

### 4.8 Persistence

PostgreSQL is the primary system of record for:
- sessions;
- messages;
- document chunks / vectors;
- MCP server registry;
- audit events.

Redis may be introduced for queue/cache/coordination, but not as the authoritative store for durable business state.

### 4.9 Sandbox

v0.2 has an application-level sandbox: non-root container, restricted workspace path, command allowlist, timeout and no `shell=True`.

This is **not a hostile-code security boundary**. The target production architecture moves Python, shell, build tools and other powerful execution into short-lived isolated containers or VMs managed by a Sandbox Manager.

## 5. Deployment architecture

### Local development

Recommended: Windows 11 or Linux + Docker Desktop/Engine + Docker Compose. Run Harness, PostgreSQL/pgvector and optionally Ollama together for repeatable smoke tests.

### Stage

Recommended: Ubuntu LTS VPS + Docker Engine/Compose + TLS reverse proxy. Keep PostgreSQL, Harness, Ollama and internal MCP services on private Docker networks. Expose only the reverse proxy/API endpoints required for testing.

### Production

Initial production can remain a single Ubuntu host if capacity and risk permit, but must add hardened secrets, backups, TLS, OIDC, observability, rate limits and isolated execution. Scale-out components are introduced when workload requires them.

### Vercel

Use Vercel for an optional web frontend. Do not make it the primary runtime for the stateful Harness, PostgreSQL, Ollama, MCP servers or sandbox workers.

## 6. Environment and promotion model

```text
feature branch -> CI -> local validation -> stage -> release tag -> production
```

GitHub repository state is authoritative. Stage and production should deploy immutable versions/tags or container images rather than untracked server edits.

## 7. Quality attributes

Priority order:
1. Security and data-boundary correctness.
2. Provider independence and recoverability.
3. Auditability and observability.
4. Reproducible deployment.
5. Reliability and graceful fallback.
6. Performance and cost optimization.

## 8. Architecture constraints

- Never commit `.env` or credentials.
- Never allow a model to bypass tool policy.
- Never send private/restricted requests to a cloud fallback.
- Never treat MCP output as trusted merely because the server is registered.
- Never use the production host filesystem as an unrestricted agent workspace.
- Do not introduce multi-agent orchestration before v0.2/v0.3 acceptance gates are met.

## 9. Related documents

- `DECISIONS.md`
- `SECURITY.md`
- `ROADMAP.md`
- `docs/adr/ADR-001-openai-compatible-provider-interface.md`
- `docs/adr/ADR-002-postgresql-system-of-record.md`
- `docs/adr/ADR-003-rag-owned-by-harness.md`
- `docs/adr/ADR-004-mcp-as-tool-provider.md`
- `docs/adr/ADR-005-harness-owned-security.md`
- `docs/adr/ADR-006-github-source-of-truth.md`
