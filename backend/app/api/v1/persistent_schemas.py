from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    organization_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ServiceRead(BaseModel):
    id: UUID
    name: str
    description: str | None
    model_config = ConfigDict(from_attributes=True)


class SnapshotCreate(BaseModel):
    service_id: UUID
    format: Literal["yaml", "json"] = "yaml"
    document: str = Field(max_length=250_000)


class SnapshotRead(BaseModel):
    id: UUID
    service_id: UUID
    format: str
    content_hash: str
    document: dict[str, Any]
    created_at: str


class DependencyCreate(BaseModel):
    source_id: UUID
    target_id: UUID


class DependencyRead(BaseModel):
    id: UUID
    source_id: UUID
    target_id: UUID
    model_config = ConfigDict(from_attributes=True)


class DiffRunRequest(BaseModel):
    before_snapshot_id: UUID
    after_snapshot_id: UUID
    context: dict[str, Any] = Field(default_factory=dict, max_length=50)


class DiffRunResponse(BaseModel):
    run_id: UUID
    changes: list[dict[str, Any]]
    analysis: dict[str, Any]
    created_at: str


class WorkspaceImpactRequest(BaseModel):
    changed_services: list[UUID] = Field(min_length=1, max_length=100)
