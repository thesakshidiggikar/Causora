from fastapi import APIRouter

from app.services.analysis import analysis_service
from app.services.schemas import AnalysisRequest, AnalysisResponse

router = APIRouter()


@router.post("/analyses", response_model=AnalysisResponse, summary="Analyze configuration changes")
def analyze(request: AnalysisRequest) -> AnalysisResponse:
    return analysis_service.analyze(request)
