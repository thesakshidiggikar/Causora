# Causora

Causora is an explainable platform foundation for reviewing configuration changes and identifying plausible operational risks before rollout. The repository currently contains a stateless API and deterministic starter rules; it is an MVP foundation, not yet a production failure prediction system.

## Quick start

Requirements: Python 3.12+ (3.11+ supported) and Docker Compose (optional).

```powershell
cd backend
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs. Or run `docker compose up --build` from the repository root.

```http
POST /api/v1/analyses
Content-Type: application/json

{"changes":[{"service":"billing","key":"DB_POOL_SIZE","before":20,"after":60}]}
```

The response includes rule findings, evidence, affected services, recommendations, assumptions, and severity. It does not claim probabilistic failure prediction.

## Security and credentials

No AWS credentials or live cloud integrations are required. Keep `.env` local and out of Git. Production AWS access should use workload identity/IAM roles and a managed secret store; never paste keys into source. `.env.example` contains names and guidance only.

## Architecture

- `backend/app/api`: versioned HTTP boundary
- `backend/app/services`: deterministic analysis and typed contracts
- `backend/app/core`: centralized runtime settings
- `frontend`: operator dashboard MVP for submitting and reviewing a local analysis
- `docker-compose.yml`: local API and dashboard services
- `docs`: architecture and delivery notes

The initial analyzer is stateless and deterministic. Persistence, tenant auth, graph ingestion, telemetry, and calibrated prediction need separate design and threat modeling before production use.

## Development

```powershell
cd backend
pip install -e ".[dev]"
ruff check .
ruff format --check .
mypy app
pytest
```

See [architecture overview](docs/architecture/overview.md) and [roadmap](docs/roadmap.md).
