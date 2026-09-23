from app.services.schemas import AnalysisRequest, AnalysisResponse, Finding, Severity

ORDER = {Severity.low: 0, Severity.medium: 1, Severity.high: 2, Severity.critical: 3}


class AnalysisService:
    """Explainable starter rules; inputs are untrusted operator-provided facts."""

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        findings: list[Finding] = []
        services = sorted({change.service for change in request.changes})
        for change in request.changes:
            key = change.key.lower()
            is_sensitive = any(
                token in key
                for token in ("password", "secret", "token", "credential", "private_key", "api_key")
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
                token in key for token in ("replica", "max_replicas", "pool_size", "connections")
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
        if not findings:
            findings.append(
                Finding(
                    code="review-required",
                    title="No matching deterministic rule",
                    severity=Severity.low,
                    evidence=[f"Received {len(request.changes)} configuration change(s)."],
                    affected_services=services,
                    recommendation=(
                        "Review the change with service owners; this initial "
                        "ruleset has limited coverage."
                    ),
                )
            )
        severity = max((item.severity for item in findings), key=lambda severity: ORDER[severity])
        return AnalysisResponse(
            findings=findings,
            changed_services=services,
            overall_severity=severity,
            assumptions=[
                "Analysis uses only the supplied changes and context.",
                "No live infrastructure, telemetry, graph, or cloud account was queried.",
                "Severity is a rule classification, not a probability of failure.",
            ],
        )


analysis_service = AnalysisService()
