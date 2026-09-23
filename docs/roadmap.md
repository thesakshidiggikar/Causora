# Delivery roadmap

- Engineering foundation, API versioning, local run path, CI and deterministic rule analyzer: implemented.
- YAML/JSON parsing, bounded nested-key diffs and secret redaction: implemented.
- PostgreSQL/SQLite persistence, Alembic migration, tenant registration/login, owner-scoped workspace, immutable redacted snapshots, saved diff runs, dependency storage and audit events: initial MVP implemented.
- Dependency impact: bounded shortest-path traversal and one-off/persisted edge input implemented; discovery, graph provenance and edge confidence remain.
- Security: Argon2id password hashing, signed expiring bearer tokens, tenant scoping and keyed fingerprints implemented. Invitations, email verification, password reset, rate limits, full RBAC, row-level security and production review remain.
- Interaction engine and cross-setting constraints: remaining.
- Causal propagation and scenario simulation: structural reachability exists; causal evidence model and simulation remain.
- Risk: explainable rule severity exists; calibrated probability and historical outcome learning remain.
- Remediation: human-reviewed proposals remain; no automatic production writes.
- Runtime learning: telemetry and deployment feedback remain.
- Observability: health checks exist; structured logging, metrics, tracing, dashboards and alerts remain.
- Production: PostgreSQL Compose path exists; AWS/Kubernetes hardening, backups, disaster recovery, scanning, rollout and rollback remain.

The current implementation is a usable local MVP, not a claim that every roadmap capability is complete.
