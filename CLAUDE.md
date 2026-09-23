# Working on AI Harness

Read before changing code: `ARCHITECTURE.md`, `SECURITY.md`, `DECISIONS.md` (+ `docs/adr/`), `ROADMAP.md`, `docs/v0.2-acceptance.md`.

## Non-negotiable constraints (ARCHITECTURE.md §8, SECURITY.md)

- Never commit `.env` or credentials; never put secrets in prompts, RAG documents, logs or audit payloads.
- The model proposes, the Harness authorizes (ADR-005). No code path may let model output, tool output, documents or MCP metadata grant permissions or approvals.
- Every tool registered in `app/tools/registry.py` must declare an `Effect` (ADR-008). Missing classification is treated as DESTRUCTIVE.
- `private=true` and `CLOUD_PROVIDERS_ENABLED=false` must never reach 9Router/OpenRouter, including embeddings.
- MCP tools go through the Tool Registry and policy; never trust server annotations to relax policy (ADR-004).
- Sessions are owner-scoped; a session id must never expose another owner's history.
- Audit security-relevant events via `app/audit.py`; store identifiers and hashes, not raw arguments.
- Do not add multi-agent orchestration, Kubernetes, extra databases or queues before the ROADMAP gates justify them.

## Process

- Material decisions (security boundaries, persistence, public API, providers, deployment) need an ADR under `docs/adr/`; add it to `DECISIONS.md`. Do not rewrite accepted ADRs; supersede them.
- Every bug fix or control gets a test. Run before pushing:
  - `pytest -q`
  - `docker compose build && docker compose -f docker-compose.yml -f compose.e2e.yaml up -d --no-build --wait && python3 e2e/smoke.py --restart`
- Update `docs/v0.2-acceptance.md` when gate evidence changes, and the README when commands change.
- Schema changes are additive until Alembic lands; add idempotent DDL in `app/db/core.py`.
