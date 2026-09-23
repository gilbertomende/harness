# ADR-007: Tool approvals are server-side and bound to one exact call

Status: Proposed (implemented in PR #1; accept on merge)

## Context

v0.2.0 accepted an `approved` flag in the `/chat` request, so the caller could approve its own mutating tool calls, and the model's retries were not tied to what had been approved. This contradicts ADR-005: the model (and the requesting client) may propose actions but cannot authorize them.

## Decision

- `/chat` does not accept any approval input.
- When a tool call needs approval (see ADR-008), the Harness persists a `tool_approvals` record bound to `(session, tool, canonical JSON arguments)` and stops the agent turn, returning `pending_approvals`.
- Only an administrator decides, via `GET /approvals` and `POST /approvals/{id}`. Decisions are durable and audited (`tool_approval_requested`, `tool_approval_approved|rejected`, `tool_approval_used`).
- An approved record is consumed atomically by exactly one execution of the identical call. Different arguments require a new approval.
- `APPROVAL_REQUIRED_FOR_MUTATING_TOOLS=false` disables the gate entirely and is an explicit operator choice for development only.

## Consequences

Positive: prompt injection, model error or a malicious client cannot execute a gated tool; every gated execution is traceable to an approver.

Trade-off: the model must repeat the call with identical arguments after approval. With the stage bootstrap login there is a single administrator, so requester and approver can be the same person; separation of duties depends on OIDC/RBAC (ROADMAP v0.3).

Follow-up: approval expiry, approver != requester policy, notifications, UI.
