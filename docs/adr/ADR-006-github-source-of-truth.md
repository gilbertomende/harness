# ADR-006: GitHub is the source of truth

Status: Accepted

## Context

Local ZIPs, developer workstations and VPS edits create configuration drift and make rollback/audit difficult.

## Decision

The `gilbertomende/harness` GitHub repository is authoritative for application code, architecture documentation, deployment manifests and version history. Environments deploy commits/tags/images derived from the repository. Secrets remain outside Git.

## Consequences

Positive: reproducible builds, reviewable changes, CI/CD and rollback.

Trade-off: emergency server changes must be reconciled back into version control rather than becoming permanent unmanaged state.
