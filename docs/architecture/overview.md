# Architecture overview

## Implemented slice

A React dashboard calls versioned FastAPI routes. Pydantic validates requests. Stateless YAML/JSON parsing creates stable nested-key diffs; deterministic rules return evidence and recommendations. A bounded BFS returns shortest service dependency paths, explicitly as reachability rather than failure prediction.

SQLAlchemy 2 models organizations, users, services, config snapshots, dependencies, analysis runs, and audit events. Alembic owns schema changes. Every workspace query scopes by the authenticated user's organization. Passwords use Argon2id; API access uses short-lived signed bearer tokens. Configuration snapshots never persist raw values for key names recognized as sensitive: those values are represented internally by a separate-key HMAC fingerprint and shown as `[REDACTED]`. Analysis outputs and audit events are persisted without raw configuration values.

SQLite is the local default. Docker Compose runs PostgreSQL and applies migrations before starting the API. Readiness checks the configured database connection.

## Current security limits

Registration is open in this internal MVP; there is no invitation, email verification, password reset, rate limiting, or multi-role authorization yet. Tenant isolation is implemented in workspace queries, but a production security review and database-level row security are still needed. Secret detection is key-name based and can miss sensitive values under unrecognized names. Configure distinct, persistent `CAUSORA_JWT_SECRET` and `CAUSORA_REDACTION_SECRET` values outside development; rotating the redaction key makes historic fingerprints compare as changed.

## Next architecture steps

1. Add organization invitations, RBAC, login rate limits, password reset, and security headers.
2. Expand manifest parsing with provenance and operator confirmation.
3. Persist richer graph nodes, edge confidence, and configuration references.
4. Add cross-setting interaction and failure propagation rules with golden cases.
5. Add scenario simulation, evidence-linked risk assessment, and safe remediation proposals.
6. Integrate OpenTelemetry, Prometheus metrics, structured logs, deployment outcomes, backups, and recovery procedures.
7. Add hardened AWS/Kubernetes deployment with least-privilege workload identity, secrets management, rollout and rollback.

No AWS credentials are needed or included in the current project.
