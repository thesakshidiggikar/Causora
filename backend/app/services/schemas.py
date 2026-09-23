from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Severity(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class ConfigChange(BaseModel):
    service: str = Field(min_length=1, max_length=100)
    key: str = Field(min_length=1, max_length=200)
    before: Any = None
    after: Any = None


class AnalysisRequest(BaseModel):
    changes: list[ConfigChange] = Field(min_length=1, max_length=500)
    context: dict[str, Any] = Field(default_factory=dict)


class RemediationOption(BaseModel):
    title: str
    expected_effect: str
    trade_off: str
    requires_approval: bool = True


class Finding(BaseModel):
    code: str
    title: str
    severity: Severity
    evidence: list[str]
    affected_services: list[str] = Field(default_factory=list)
    recommendation: str
    remediation_options: list[RemediationOption] = Field(default_factory=list)


class AnalysisResponse(BaseModel):
    findings: list[Finding]
    changed_services: list[str]
    overall_severity: Severity
    assumptions: list[str]
    mode: str = "deterministic_rules"
