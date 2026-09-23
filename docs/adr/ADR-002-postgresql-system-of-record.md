# ADR-002: PostgreSQL is the durable system of record

Status: Accepted

## Context

The platform needs durable sessions, messages, audit, MCP configuration and vector-backed RAG without unnecessary operational fragmentation.

## Decision

Use PostgreSQL as the authoritative durable database. Use pgvector for the initial vector-search implementation. Redis may later serve cache/queue/coordination purposes but is not the source of truth.

## Consequences

Positive: one backup/recovery platform, transactional consistency and simpler stage operations.

Trade-off: very large-scale vector/search workloads may eventually require a specialized service. Such a change must be evidence-driven.
