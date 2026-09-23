# ADR-003: RAG is owned by the Harness

Status: Accepted

## Context

Knowledge retrieval must survive model/provider changes and must be governed by the same identity and policy layer as other capabilities.

## Decision

Chunking, embeddings, storage, retrieval, metadata and authorization belong to the Harness. RAG search is exposed to agents through a controlled tool/capability interface.

## Consequences

Positive: provider-independent knowledge, centralized governance and testable retrieval behavior.

Trade-off: the Harness owns ingestion lifecycle, embedding migrations and access-control complexity.
