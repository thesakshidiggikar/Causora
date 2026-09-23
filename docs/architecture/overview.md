# Architecture overview

## Current slice
A versioned FastAPI API accepts operator-supplied changes or bounded YAML/JSON documents, validates them with Pydantic, safely parses YAML, flattens nested keys, and invokes deterministic rules. Findings include evidence and recommendations. Secret-like values are redacted in both evidence and returned diffs. A separate bounded breadth-first traversal traces shortest downstream paths through an operator-supplied graph and reports that reachability is not a failure prediction. The API performs no network calls and stores no customer data.

## Intended evolution
1. Persist organizations, systems, services, configuration snapshots, and analysis runs in PostgreSQL through SQLAlchemy and Alembic.
2. Build a typed dependency graph from manifests and operator-confirmed links.
3. Add change diffs, interaction rules, and bounded propagation analysis.
4. Add evidence-linked risk assessments; calibrated probabilities only after sufficient outcomes.
5. Add authenticated, tenant-isolated UI and audit trail.
6. Integrate telemetry and deployment outcomes; calibrate predictions against evidence.
7. Deploy with managed database, workload identity, secrets manager, least privilege, backups, monitoring, and rollback.

## Security boundaries
Treat uploaded config values as sensitive. Redact secret-like values from logs and persisted diffs. Cloud integrations should use short-lived workload credentials; AWS account IDs, IAM role ARNs, and region choices belong in deployment configuration. No credentials are required by the current slice.
