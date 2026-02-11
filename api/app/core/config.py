from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List, Any


class Settings(BaseSettings):
    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — accepts either a comma-separated string or a JSON array in .env
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Strip JSON brackets if someone wrote ["x","y"]
            stripped = v.strip()
            if stripped.startswith("["):
                import json
                return json.loads(stripped)
            # Otherwise treat as comma-separated: x,y,z
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return v

    # Rate limiting
    DEFAULT_RATE_LIMIT: int = 60
    AUTHENTICATED_RATE_LIMIT: int = 120

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@commentplatform.com"
    FROM_NAME: str = "Comment Platform"
    APP_URL: str = "http://localhost:8000"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "ignore",        # Silently ignore unknown env vars
    }


settings = Settings()