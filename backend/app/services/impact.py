from collections import deque

from pydantic import BaseModel, Field, field_validator, model_validator


class Dependency(BaseModel):
    source: str = Field(min_length=1, max_length=100)
    target: str = Field(min_length=1, max_length=100)


class ImpactRequest(BaseModel):
    services: list[str] = Field(min_length=1, max_length=1000)
    changed_services: list[str] = Field(min_length=1, max_length=100)
    dependencies: list[Dependency] = Field(default_factory=list, max_length=5000)

    @field_validator("services", "changed_services")
    @classmethod
    def unique_services(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("Service names must be unique.")
        return values

    @model_validator(mode="after")
    def validate_references(self) -> "ImpactRequest":
        known = set(self.services)
        unknown_changes = set(self.changed_services) - known
        unknown_edges = {
            name
            for edge in self.dependencies
            for name in (edge.source, edge.target)
            if name not in known
        }
        if unknown_changes or unknown_edges:
            raise ValueError(
                "Every changed service and dependency endpoint must exist in services."
            )
        return self


class ImpactPath(BaseModel):
    service: str
    path: list[str]


class ImpactResponse(BaseModel):
    changed_services: list[str]
    impacted_services: list[str]
    paths: list[ImpactPath]
    assumptions: list[str]
    mode: str = "bounded_breadth_first_traversal"


class ImpactAnalysisService:
    """Return deterministic shortest dependency paths, safely handling cycles."""

    def analyze(self, request: ImpactRequest) -> ImpactResponse:
        adjacency: dict[str, set[str]] = {service: set() for service in request.services}
        for dependency in request.dependencies:
            adjacency[dependency.source].add(dependency.target)

        changed = sorted(request.changed_services)
        queue = deque((service, [service]) for service in changed)
        visited = set(changed)
        paths: list[ImpactPath] = []
        while queue:
            current, path = queue.popleft()
            for downstream in sorted(adjacency[current]):
                if downstream in visited:
                    continue
                visited.add(downstream)
                next_path = [*path, downstream]
                paths.append(ImpactPath(service=downstream, path=next_path))
                queue.append((downstream, next_path))

        return ImpactResponse(
            changed_services=changed,
            impacted_services=[item.service for item in paths],
            paths=paths,
            assumptions=[
                (
                    "Each dependency edge points from an upstream source to a "
                    "downstream dependent service."
                ),
                (
                    "The graph is supplied with this request; no repository or live "
                    "system was discovered."
                ),
                "Paths indicate structural reachability, not a predicted failure or probability.",
                (
                    "For each service, the result includes one deterministic shortest "
                    "path from a changed service."
                ),
            ],
        )


impact_analysis_service = ImpactAnalysisService()
