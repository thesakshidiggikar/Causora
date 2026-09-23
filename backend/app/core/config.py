from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "Causora API"
    environment: str = "development"
    api_prefix: str = "/api/v1"
    log_level: str = "INFO"
    # Add a secret-manager-backed database URL when persistence is introduced.
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CAUSORA_", extra="ignore")


settings = Settings()
