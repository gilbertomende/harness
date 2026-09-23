# AI Harness - Security Model

Status: Security baseline for stage; production controls are explicitly identified below.

## 1. Security objective

The Harness must permit useful model/tool execution without granting an LLM implicit authority over infrastructure, data or credentials. Model output, retrieved content, MCP responses and tool arguments are untrusted inputs.

## 2. Trust boundaries

```text
UNTRUSTED / PARTIALLY TRUSTED
- user prompts
- uploaded/retrieved documents
- RAG content
- LLM output
- generated tool arguments
- MCP schemas/responses
- remote provider responses
             |
             v
      Harness validation
      Identity + Policy
             |
             v
       Tool boundary
             |
             v
Sandbox / Data / Infrastructure
```

A registered component is not automatically a trusted component.

## 3. Identity and access

### Stage baseline

v0.2 provides JWT authentication with a bootstrap administrator credential. This is sufficient for controlled stage testing only.

### Production target

Use OIDC with a managed identity provider such as Entra ID or Keycloak. Authorization must be based on explicit roles/claims and should support least privilege for:
- chat/session access;
- RAG ingestion/search;
- MCP registration/administration;
- mutating tools;
- audit access;
- administrative configuration.

Sessions must remain owner-scoped.

## 4. Tool security model

Tools should be classified by effect:

| Class | Examples | Default policy |
|---|---|---|
| READ | list/read file, status | Automatic when role permits |
| QUERY | RAG search, read-only MCP query | Automatic when role permits |
| WRITE | write/update file or record | Policy check; approval as configured |
| EXEC | shell, Python, build tools | Isolated sandbox + policy |
| DESTRUCTIVE | delete, system config, DB mutation, network administration | Explicit approval and elevated role |

The LLM may request a tool but cannot authorize it. The flow is:

```text
LLM request -> Tool Registry -> Policy -> Approval if required -> Sandbox/Tool -> Result
```

Tool arguments must be validated against schemas and additional policy constraints. A tool must fail closed when policy metadata is missing or ambiguous.

## 5. Sandbox controls

### v0.2 stage baseline

Current shell execution is constrained by:
- dedicated application container;
- non-root runtime;
- workspace path restriction;
- executable allowlist;
- timeout;
- direct argv execution rather than `shell=True`;
- dropped Linux capabilities/no-new-privileges in deployment configuration where supported.

These controls reduce risk but do not safely support hostile arbitrary code.

### Production target

Powerful execution moves to ephemeral isolated runtimes with:
- non-root identity;
- read-only base filesystem;
- dedicated ephemeral workspace;
- CPU/memory/PID/time quotas;
- seccomp/AppArmor or stronger isolation where available;
- explicit network egress policy, default deny where feasible;
- no Docker socket mounted into the agent;
- no host secrets inherited by default;
- automatic destruction after task completion.

## 6. Data classification and model routing

Target classifications:
- PUBLIC
- INTERNAL
- CONFIDENTIAL
- RESTRICTED

The current `private=true` flag is the first enforcement mechanism. A private request must use local inference only and must fail rather than fall back to 9Router/OpenRouter.

Future routing policy should map data classification to permitted providers/models and log the policy decision without logging sensitive prompt content unnecessarily.

## 7. RAG security

RAG is a data-access system, not merely a search feature. Production RAG must support:
- document/collection ownership;
- ACL or group-based filters before retrieval;
- tenant/namespace separation when applicable;
- source metadata and citations;
- deletion/lifecycle controls;
- ingestion validation;
- prompt-injection-aware handling of retrieved text.

Retrieved documents are untrusted instructions. Content in a document must never override system/tool policy.

## 8. MCP security

MCP introduces an external capability boundary. Production requirements:
- allowlist approved MCP servers;
- authenticate servers where supported;
- validate URL/transport and block unsafe internal-network reachability where not explicitly required;
- enforce per-tool roles and mutation classification;
- apply timeouts and output-size limits;
- record server/tool identity in audit events;
- do not trust tool descriptions as security policy;
- restrict egress from MCP execution paths.

## 9. Secrets

Never store secrets in:
- Git commits;
- `.env.example` real values;
- prompts or system messages;
- RAG documents;
- ordinary application logs;
- audit detail payloads unless safely redacted.

Stage may use a protected local `.env`. Production should use a secrets manager or platform secret mechanism. Rotate credentials if accidental disclosure is suspected.

## 10. Logging and audit

Security-relevant events should record, where applicable:
- timestamp;
- actor/principal;
- session ID;
- action/tool;
- provider/model;
- policy decision;
- approval decision;
- execution result/status;
- latency;
- correlation/trace ID.

Avoid storing full sensitive prompts, secrets or raw credentials. Prefer hashes, identifiers and redacted metadata for sensitive arguments.

## 11. Network security

Stage/production guidance:
- expose only TLS reverse proxy/API ports;
- keep PostgreSQL private;
- keep Ollama private unless a controlled remote inference use case requires otherwise;
- restrict MCP server reachability;
- apply host firewall rules;
- separate public ingress from internal service networks;
- add provider/MCP egress controls as the policy engine matures.

## 12. Dependency and supply-chain security

Before production:
- pin or constrain critical dependency versions;
- scan Python dependencies and container images;
- use trusted base images;
- publish immutable image tags/digests;
- enable GitHub branch protection and required CI;
- review third-party MCP servers and model gateways;
- generate an SBOM if the service becomes operationally critical.

## 13. Incident response minimums

Maintain procedures to:
1. revoke/rotate provider and JWT/OIDC secrets;
2. disable a compromised MCP server/tool;
3. disable cloud fallback globally;
4. preserve audit logs;
5. redeploy a known-good image/tag;
6. restore PostgreSQL from tested backups.

## 14. Security acceptance gates

Stage may proceed when local authentication, owner-scoped sessions, private routing, sandbox path restrictions and basic audit are verified.

Production must not proceed until OIDC/RBAC, migrations, backups, TLS, rate limiting, isolated execution for powerful tools, secrets management, observability and RAG/MCP access controls are implemented and tested.

## 15. Reporting vulnerabilities

Until a formal disclosure channel exists, do not publish exploitable details in a public issue. Use a private repository/security communication channel and rotate affected credentials immediately.
