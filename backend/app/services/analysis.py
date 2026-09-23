import math
from typing import Any

from app.services.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    Finding,
    RemediationOption,
    Severity,
)

ORDER = {Severity.low: 0, Severity.medium: 1, Severity.high: 2, Severity.critical: 3}


def _positive_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


class AnalysisService:
    """Deterministic rules with evidence; context facts remain explicit assumptions."""

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        findings: list[Finding] = []
        services = sorted({change.service for change in request.changes})
        for change in request.changes:
            key = change.key.lower()
            is_sensitive = any(
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
            )
            before = "[REDACTED]" if is_sensitive else repr(change.before)
            after = "[REDACTED]" if is_sensitive else repr(change.after)
            evidence = [f"{change.service}.{change.key} changed from {before} to {after}"]
            if is_sensitive:
                findings.append(
                    Finding(
                        code="sensitive-config-change",
                        title="Sensitive configuration changed",
                        severity=Severity.high,
                        evidence=evidence,
                        affected_services=[change.service],
                        recommendation=(
                            "Verify the value is stored in a secret manager, rotated safely, "
                            "and never committed in plaintext."
                        ),
                    )
                )
            if any(
                token in key
                for token in ("replica", "max_replicas", "pool_size", "connections", ".size")
            ):
                findings.append(
                    Finding(
                        code="capacity-change",
                        title="Capacity setting changed",
                        severity=Severity.medium,
                        evidence=evidence,
                        affected_services=[change.service],
                        recommendation=(
                            "Check downstream capacity and peak concurrency before rollout."
                        ),
                    )
                )
            if any(token in key for token in ("timeout", "retry", "backoff")):
                findings.append(
                    Finding(
                        code="resilience-change",
                        title="Timeout or retry behavior changed",
                        severity=Severity.medium,
                        evidence=evidence,
                        affected_services=[change.service],
                        recommendation=(
                            "Check end-to-end deadlines, retry amplification, and idempotency."
                        ),
                    )
                )

        budget_finding = self._database_connection_budget(request, services)
        if budget_finding is not None:
            findings.append(budget_finding)
        if not findings:
            findings.append(
                Finding(
                    code="review-required",
                    title="No matching deterministic rule",
                    severity=Severity.low,
                    evidence=[f"Received {len(request.changes)} configuration change(s)."],
                    affected_services=services,
                    recommendation="Review with service owners; this ruleset has limited coverage.",
                )
            )
        severity = max((item.severity for item in findings), key=lambda item: ORDER[item])
        assumptions = [
            "Analysis uses only the supplied changes and context.",
            "No live infrastructure, telemetry, graph, or cloud account was queried.",
            "Severity is an explainable rule category, not a probability of failure.",
        ]
        if request.context:
            assumptions.append(
                "Operator-supplied context is treated as assumed fact and was not "
                "independently verified."
            )
        return AnalysisResponse(
            findings=findings,
            changed_services=services,
            overall_severity=severity,
            assumptions=assumptions,
        )

    def _database_connection_budget(
        self, request: AnalysisRequest, services: list[str]
    ) -> Finding | None:
        replicas = _positive_number(request.context.get("max_replicas"))
        pool_size = _positive_number(request.context.get("database_pool_size"))
        connection_limit = _positive_number(request.context.get("database_max_connections"))
        for change in request.changes:
            key = change.key.lower()
            if "replica" in key:
                replicas = _positive_number(change.after) or replicas
            if "pool_size" in key or "connections_per_pod" in key:
                pool_size = _positive_number(change.after) or pool_size
        if replicas is None or pool_size is None or connection_limit is None:
            return None

        required = math.ceil(replicas * pool_size)
        margin = request.context.get("database_safety_margin", 0.1)
        try:
            margin_value = float(margin)
        except (TypeError, ValueError):
            margin_value = 0.1
        if not math.isfinite(margin_value) or not 0 <= margin_value < 0.9:
            margin_value = 0.1
        budget = math.floor(connection_limit * (1 - margin_value))
        if required <= budget:
            return None
        severity = Severity.critical if required > connection_limit * 1.5 else Severity.high
        max_pool = max(1, budget // math.ceil(replicas))
        max_replicas = max(1, budget // math.ceil(pool_size))
        return Finding(
            code="database-connection-budget-exceeded",
            title="Potential database connection exhaustion",
            severity=severity,
            evidence=[
                f"Assumed maximum replicas: {math.ceil(replicas)}.",
                f"Assumed pool size per replica: {math.ceil(pool_size)}.",
                f"Estimated maximum connections: {required}.",
                f"Assumed database connection limit: {math.floor(connection_limit)}.",
                f"Usable budget after {margin_value:.0%} safety margin: {budget}.",
            ],
            affected_services=services,
            recommendation=(
                "Keep peak application connections within the database budget, including "
                "migrations and other clients."
            ),
            remediation_options=[
                RemediationOption(
                    title=f"Reduce pool size to at most {max_pool}",
                    expected_effect=(
                        "Lowers the calculated peak connection demand to the usable budget."
                    ),
                    trade_off="May increase queueing and request latency under concurrency.",
                ),
                RemediationOption(
                    title=f"Limit maximum replicas to at most {max_replicas}",
                    expected_effect="Caps peak application connections within the usable budget.",
                    trade_off="Reduces horizontal scale and burst capacity.",
                ),
                RemediationOption(
                    title=f"Increase database connection capacity to at least {required}",
                    expected_effect=(
                        "Raises the configured database ceiling above calculated demand."
                    ),
                    trade_off=(
                        "May require a larger database tier and still needs operational headroom."
                    ),
                ),
            ],
        )


analysis_service = AnalysisService()
