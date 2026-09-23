from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "Causora API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./causora.db"
    jwt_secret: str | None = None
    redaction_secret: str | None = None
    allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    token_expire_minutes: int = Field(default=30, ge=5, le=1440)
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CAUSORA_", extra="ignore")

    @field_validator("jwt_secret", "redaction_secret")
    @classmethod
    def validate_secret_length(cls, value: str | None) -> str | None:
        if value and len(value) < 32:
            raise ValueError("Configured application secrets must contain at least 32 characters.")
        return value

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment.lower() == "production":
            origins = [item.strip() for item in self.allowed_origins.split(",") if item.strip()]
            if not self.jwt_secret or not self.redaction_secret:
                raise ValueError("Production requires distinct JWT and redaction secrets.")
            if not origins or any(not origin.startswith("https://") for origin in origins):
                raise ValueError("Production allowed origins must use HTTPS.")
        return self


settings = Settings()
