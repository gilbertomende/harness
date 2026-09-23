# ADR-005: Security decisions belong to the Harness

Status: Accepted

## Context

LLMs are probabilistic and may be influenced by user input, retrieved documents or tool output. They cannot be the authority for privileged operations.

## Decision

The model may propose actions but cannot authorize them. The Harness enforces identity, roles, tool policy, approvals, data-classification routing and sandbox restrictions. Security controls fail closed.

## Consequences

Positive: prompt injection or model error cannot legitimately override platform policy.

Trade-off: policy/approval infrastructure becomes a core platform responsibility and must be maintained independently of prompts.
