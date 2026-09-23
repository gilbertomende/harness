# ADR-001: Prefer an OpenAI-compatible provider interface

Status: Accepted

## Context

The Harness must support Ollama, 9Router, OpenRouter and future inference servers without coupling the Agent Runtime to each provider SDK.

## Decision

Use a provider abstraction with an OpenAI-compatible chat/embedding interface wherever the target provider supports it. Provider-specific adapters may be added when compatibility is incomplete or a required feature is unavailable.

## Consequences

Positive: simpler routing, lower provider lock-in, consistent tests and easier local/cloud substitution.

Trade-off: the common interface may not expose every provider-native capability. Provider-specific extensions must remain behind the adapter boundary.
