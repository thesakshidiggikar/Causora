from fastapi import APIRouter, HTTPException

from app.services.analysis import analysis_service
from app.services.config_diff import (
    ConfigDiffRequest,
    ConfigDiffResponse,
    diff_configurations,
    parse_document,
    stable_value,
)
from app.services.schemas import AnalysisRequest, AnalysisResponse, ConfigChange, Severity

router = APIRouter()


@router.post("/analyses", response_model=AnalysisResponse, summary="Analyze configuration changes")
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    return analysis_service.analyze(request)


@router.post(
    "/config-diffs",
    response_model=ConfigDiffResponse,
    summary="Diff YAML or JSON and assess changes",
)
def configuration_diff(request: ConfigDiffRequest) -> ConfigDiffResponse:
    try:
        before = parse_document(request.before, request.format)
        after = parse_document(request.after, request.format)
        changes = diff_configurations(before, after)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not changes:
        return ConfigDiffResponse(
            changes=[],
            analysis=AnalysisResponse(
                findings=[],
                changed_services=[],
                overall_severity=Severity.low,
                assumptions=["The before and after documents contain no changes."],
            ),
        )
    analysis_request = AnalysisRequest(
        changes=[
            ConfigChange(
                service=request.service,
                key=change["key"],
                before=stable_value(change["before"]),
                after=stable_value(change["after"]),
            )
            for change in changes
        ]
    )
    public_changes = []
    for change in changes:
        item = dict(change)
        key = change["key"].lower()
        if any(
            token in key
            for token in (
                "password",
                "secret",
                "token",
                "credential",
                "private_key",
                "api_key",
                "access_key",
            )
        ):
            item["before"] = "[REDACTED]"
            item["after"] = "[REDACTED]"
        public_changes.append(item)
    return ConfigDiffResponse(
        changes=public_changes, analysis=analysis_service.analyze(analysis_request)
    )
