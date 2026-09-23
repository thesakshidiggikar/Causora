# Delivery roadmap

- Foundation: conventions, typed API, local run path, health checks, CI, deterministic starter analyzer. (implemented)
- Ingestion: bounded YAML/JSON parsing, nested-key diff, safe secret redaction. (initial slice implemented)
- Next: environment manifest parsing, immutable snapshots, provenance, and persistence.
- Schema: configuration contracts, provenance, versioned storage and migrations.
- Graph: services, resources, config references, dependency edges and confidence.
- Discovery: manifest and repository import with explicit trust boundaries.
- Interactions: deterministic cross-setting rules and evidence.
- Causality and propagation: bounded graph traversal and explainable paths.
- Impact and simulation: scenario comparison and blast-radius summaries.
- Risk: evidence-linked categories first; calibrated probabilities only after sufficient outcomes.
- Remediation: safe options, trade-offs, human approval; no autonomous production writes.
- Runtime learning: telemetry and deployment outcomes.
- Security and observability: tenant isolation, RBAC, audit, metrics, tracing, scanning.
- Production: deployment architecture, disaster recovery, rollout and rollback.

This repository is at the foundation slice. The roadmap is not a claim that later capabilities already exist.
