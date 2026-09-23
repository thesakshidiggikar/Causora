# Causora

Causora is an explainable configuration change impact platform. The current MVP includes a versioned FastAPI API, React dashboard, tenant-scoped PostgreSQL/SQLite persistence, organization registration and login, configuration snapshots with secret-value fingerprinting, saved analysis runs, audit events, YAML/JSON diffs, and bounded dependency-path analysis.

It does not claim calibrated failure probabilities or autonomous production remediation.

## Run locally

### Docker Compose

Requires Docker Desktop with Compose.

```powershell
docker compose up --build
```

This starts PostgreSQL, applies Alembic migrations, then runs the API and dashboard. The default database password is for local development only. For a shared environment, create a local `.env` with unique values. Use URL-safe hex strings for `POSTGRES_PASSWORD`, `CAUSORA_JWT_SECRET`, and `CAUSORA_REDACTION_SECRET`.

Open the dashboard at http://localhost:5173 and API docs at http://localhost:8000/docs. Create an organization from the dashboard; no AWS account or cloud credentials are needed.

### SQLite and separate processes

Terminal 1:

```powershell
cd backend
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -e ".[dev]"
alembic -c alembic.ini upgrade head
uvicorn app.main:app --reload
```

Terminal 2:

```powershell
cd frontend
npm ci
npm run dev
```

SQLite is the default for this local path. Set `CAUSORA_DATABASE_URL` to use PostgreSQL.

## Workspace workflow

1. Register an organization and owner account in the dashboard. Passwords are hashed with Argon2id; the API returns a short-lived bearer token.
2. Add a service and submit before/after YAML or JSON snapshots.
3. Secret-like values are stored as keyed HMAC fingerprints; raw values are not persisted. Compare saved revisions to create an immutable analysis-run record.
4. Review the tenant audit trail. Dependency edges can be persisted with `POST /api/v1/dependencies`; the `/api/v1/impact` endpoint also supports one-off operator-supplied graphs.

The API also retains stateless endpoints `POST /api/v1/analyses` and `POST /api/v1/config-diffs` for local experiments.

## Configuration and secrets

- `CAUSORA_DATABASE_URL`: database URL; local default is SQLite, Compose supplies PostgreSQL.
- `CAUSORA_JWT_SECRET`: signing key for bearer tokens.
- `CAUSORA_REDACTION_SECRET`: separate HMAC key used to fingerprint secret-like configuration values.
- `CAUSORA_ALLOWED_ORIGINS`: comma-separated dashboard origins.
- `POSTGRES_PASSWORD`: Compose database password.

`.env.example` documents these variables without real secrets. Never commit `.env`. Production must use unique managed secrets, TLS, managed PostgreSQL, workload identity for any future AWS connector, and a secret manager. Secret detection is key-name based and cannot identify every credential; limit access to stored configuration snapshots accordingly.

## Development checks

```powershell
cd backend
ruff check .
ruff format --check .
mypy app
pytest
alembic -c alembic.ini upgrade head
```

```powershell
cd frontend
npm ci
npm run build
npm audit
```

See [architecture](docs/architecture/overview.md) and [roadmap](docs/roadmap.md).
