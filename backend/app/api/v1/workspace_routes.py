import hashlib
import hmac
import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.v1.persistent_schemas import (
    DependencyCreate,
    DependencyRead,
    DiffRunRequest,
    DiffRunResponse,
    ServiceCreate,
    ServiceRead,
    SnapshotCreate,
    SnapshotRead,
    WorkspaceImpactRequest,
)
from app.core.database import get_db
from app.core.security import current_user, redaction_secret
from app.infrastructure.models import (
    AnalysisRun,
    AuditEvent,
    ConfigSnapshot,
    Service,
    ServiceDependency,
    User,
)
from app.services.analysis import analysis_service
from app.services.config_diff import diff_configurations, parse_document, stable_value
from app.services.impact import Dependency, ImpactAnalysisService, ImpactRequest
from app.services.schemas import AnalysisRequest, ConfigChange

router = APIRouter(tags=["workspace"])
SENSITIVE_TOKENS = (
    "password",
    "secret",
    "token",
    "credential",
    "private_key",
    "api_key",
    "access_key",
)
impact_service = ImpactAnalysisService()


def _audit(
    db: Session,
    user: User,
    action: str,
    entity_type: str,
    entity_id: UUID,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            organization_id=user.organization_id,
            actor_id=user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details or {},
        )
    )


def _normalise(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("Configuration map keys must be strings.")
        return {key: _normalise(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_normalise(child) for child in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise ValueError("Configuration contains an unsupported value.")


def _is_sensitive(key: str) -> bool:
    lowered = key.lower()
    return any(token in lowered for token in SENSITIVE_TOKENS)


def _redact_for_storage(document: dict[str, Any]) -> dict[str, Any]:
    key = redaction_secret().encode()

    def visit(value: Any, parent_key: str = "") -> Any:
        if parent_key and _is_sensitive(parent_key):
            encoded = json.dumps(_normalise(value), sort_keys=True, separators=(",", ":")).encode()
            fingerprint = hmac.new(key, encoded, hashlib.sha256).hexdigest()
            return {"$causora_secret_fingerprint": fingerprint}
        if isinstance(value, dict):
            return {str(k): visit(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [visit(item, parent_key) for item in value]
        return _normalise(value)

    return visit(document)


def _redact_for_read(document: dict[str, Any]) -> dict[str, Any]:
    def visit(value: Any) -> Any:
        if isinstance(value, dict) and set(value) == {"$causora_secret_fingerprint"}:
            return "[REDACTED]"
        if isinstance(value, dict):
            return {key: visit(child) for key, child in value.items()}
        if isinstance(value, list):
            return [visit(child) for child in value]
        return value

    return visit(document)


@router.post("/services", response_model=ServiceRead, status_code=201)
def create_service(
    request: ServiceCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Service:
    service = Service(
        organization_id=user.organization_id,
        name=request.name.strip(),
        description=request.description,
    )
    db.add(service)
    try:
        db.flush()
        _audit(db, user, "service.created", "service", service.id, {"name": service.name})
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A service with this name already exists."
        ) from None
    db.refresh(service)
    return service


@router.get("/services", response_model=list[ServiceRead])
def list_services(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[Service]:
    return list(
        db.scalars(
            select(Service)
            .where(Service.organization_id == user.organization_id)
            .order_by(Service.name)
        )
    )


@router.post("/snapshots", response_model=SnapshotRead, status_code=201)
def create_snapshot(
    request: SnapshotCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    service = db.scalar(
        select(Service).where(
            Service.id == request.service_id, Service.organization_id == user.organization_id
        )
    )
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found.")
    try:
        parsed = parse_document(request.document, request.format)
        stored = _redact_for_storage(parsed)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="Configuration document is invalid.") from exc
    canonical = json.dumps(stored, sort_keys=True, separators=(",", ":"))
    snapshot = ConfigSnapshot(
        organization_id=user.organization_id,
        service_id=service.id,
        format=request.format,
        content_hash=hashlib.sha256(canonical.encode()).hexdigest(),
        document=stored,
        created_by=user.id,
    )
    db.add(snapshot)
    try:
        db.flush()
        _audit(
            db,
            user,
            "snapshot.created",
            "config_snapshot",
            snapshot.id,
            {"service_id": str(service.id), "content_hash": snapshot.content_hash},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(ConfigSnapshot).where(
                ConfigSnapshot.organization_id == user.organization_id,
                ConfigSnapshot.service_id == service.id,
                ConfigSnapshot.content_hash == snapshot.content_hash,
            )
        )
        if existing is None:
            raise HTTPException(status_code=409, detail="Snapshot could not be saved.") from None
        snapshot = existing
    db.refresh(snapshot)
    return {
        "id": snapshot.id,
        "service_id": snapshot.service_id,
        "format": snapshot.format,
        "content_hash": snapshot.content_hash,
        "document": _redact_for_read(snapshot.document),
        "created_at": snapshot.created_at.isoformat(),
    }


@router.get("/snapshots", response_model=list[SnapshotRead])
def list_snapshots(
    service_id: UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, Any]]:
    service = db.scalar(
        select(Service).where(
            Service.id == service_id, Service.organization_id == user.organization_id
        )
    )
    if service is None:
        raise HTTPException(status_code=404, detail="Service not found.")
    snapshots = db.scalars(
        select(ConfigSnapshot)
        .where(
            ConfigSnapshot.organization_id == user.organization_id,
            ConfigSnapshot.service_id == service.id,
        )
        .order_by(ConfigSnapshot.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": item.id,
            "service_id": item.service_id,
            "format": item.format,
            "content_hash": item.content_hash,
            "document": _redact_for_read(item.document),
            "created_at": item.created_at.isoformat(),
        }
        for item in snapshots
    ]


@router.post("/dependencies", response_model=DependencyRead, status_code=201)
def create_dependency(
    request: DependencyCreate, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> ServiceDependency:
    if request.source_id == request.target_id:
        raise HTTPException(status_code=422, detail="A service cannot depend on itself.")
    ids = set(
        db.scalars(
            select(Service.id).where(
                Service.organization_id == user.organization_id,
                Service.id.in_([request.source_id, request.target_id]),
            )
        )
    )
    if ids != {request.source_id, request.target_id}:
        raise HTTPException(status_code=404, detail="Dependency service not found.")
    edge = ServiceDependency(
        organization_id=user.organization_id,
        source_id=request.source_id,
        target_id=request.target_id,
    )
    db.add(edge)
    try:
        db.flush()
        _audit(
            db,
            user,
            "dependency.created",
            "service_dependency",
            edge.id,
            {"source_id": str(edge.source_id), "target_id": str(edge.target_id)},
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Dependency already exists.") from None
    db.refresh(edge)
    return edge


@router.post("/analysis-runs/diff", response_model=DiffRunResponse, status_code=201)
def create_diff_run(
    request: DiffRunRequest, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    snapshots = list(
        db.scalars(
            select(ConfigSnapshot).where(
                ConfigSnapshot.organization_id == user.organization_id,
                ConfigSnapshot.id.in_([request.before_snapshot_id, request.after_snapshot_id]),
            )
        )
    )
    by_id = {item.id: item for item in snapshots}
    before = by_id.get(request.before_snapshot_id)
    after = by_id.get(request.after_snapshot_id)
    if before is None or after is None or before.service_id != after.service_id:
        raise HTTPException(
            status_code=404, detail="Matching snapshots for the same service were not found."
        )
    service = db.get(Service, before.service_id)
    if service is None or service.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Service not found.")
    changes = diff_configurations(before.document, after.document)
    analysis = (
        analysis_service.analyze(
            AnalysisRequest(
                changes=[
                    ConfigChange(
                        service=service.name,
                        key=change["key"],
                        before=stable_value(change["before"]),
                        after=stable_value(change["after"]),
                    )
                    for change in changes
                ],
                context=request.context,
            )
        )
        if changes
        else None
    )
    result = (
        analysis.model_dump(mode="json")
        if analysis
        else {
            "findings": [],
            "changed_services": [],
            "overall_severity": "low",
            "assumptions": ["The selected snapshots contain no changes."],
            "mode": "deterministic_rules",
        }
    )
    run = AnalysisRun(
        organization_id=user.organization_id,
        created_by=user.id,
        input_summary={"before_snapshot_id": str(before.id), "after_snapshot_id": str(after.id)},
        result=result,
        severity=result["overall_severity"],
    )
    db.add(run)
    db.flush()
    _audit(
        db,
        user,
        "analysis.completed",
        "analysis_run",
        run.id,
        {"before_snapshot_id": str(before.id), "after_snapshot_id": str(after.id)},
    )
    db.commit()
    db.refresh(run)
    public_changes = []
    for change in changes:
        item = dict(change)
        if _is_sensitive(change["key"]):
            item["before"] = "[REDACTED]"
            item["after"] = "[REDACTED]"
        else:
            item["before"] = (
                _redact_for_read(item["before"])
                if isinstance(item["before"], dict)
                else item["before"]
            )
            item["after"] = (
                _redact_for_read(item["after"])
                if isinstance(item["after"], dict)
                else item["after"]
            )
        public_changes.append(item)
    return {
        "run_id": run.id,
        "changes": public_changes,
        "analysis": result,
        "created_at": run.created_at.isoformat(),
    }


@router.get("/audit-events")
def list_audit_events(
    limit: int = Query(default=100, ge=1, le=200),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == user.organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": str(event.id),
            "actor_id": str(event.actor_id),
            "action": event.action,
            "entity_type": event.entity_type,
            "entity_id": str(event.entity_id),
            "details": event.details,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]


@router.get("/dependencies", response_model=list[DependencyRead])
def list_dependencies(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[ServiceDependency]:
    return list(
        db.scalars(
            select(ServiceDependency)
            .where(ServiceDependency.organization_id == user.organization_id)
            .order_by(ServiceDependency.source_id, ServiceDependency.target_id)
        )
    )


@router.post("/impact/workspace")
def analyze_workspace_impact(
    request: WorkspaceImpactRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    services = list(
        db.scalars(select(Service).where(Service.organization_id == user.organization_id))
    )
    names = {service.id: service.name for service in services}
    if any(service_id not in names for service_id in request.changed_services):
        raise HTTPException(status_code=404, detail="Changed service not found.")
    edges = list(
        db.scalars(
            select(ServiceDependency).where(
                ServiceDependency.organization_id == user.organization_id
            )
        )
    )
    graph_request = ImpactRequest(
        services=sorted(names.values()),
        changed_services=sorted(names[service_id] for service_id in request.changed_services),
        dependencies=[
            Dependency(source=names[edge.source_id], target=names[edge.target_id])
            for edge in edges
            if edge.source_id in names and edge.target_id in names
        ],
    )
    return impact_service.analyze(graph_request).model_dump(mode="json")


@router.post("/analysis-runs/simulate")
def simulate_saved_change(
    request: DiffRunRequest,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result = create_diff_run(request, user, db)
    snapshot = db.scalar(
        select(ConfigSnapshot).where(
            ConfigSnapshot.id == request.after_snapshot_id,
            ConfigSnapshot.organization_id == user.organization_id,
        )
    )
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Configuration snapshot not found.")
    impact = analyze_workspace_impact(
        WorkspaceImpactRequest(changed_services=[snapshot.service_id]), user, db
    )
    run = db.get(AnalysisRun, result["run_id"])
    if run is None or run.organization_id != user.organization_id:
        raise HTTPException(status_code=404, detail="Analysis run not found.")
    run.result = {**run.result, "impact": impact}
    _audit(
        db,
        user,
        "analysis.simulated",
        "analysis_run",
        run.id,
        {"service_id": str(snapshot.service_id)},
    )
    db.commit()
    return {**result, "impact": impact}
