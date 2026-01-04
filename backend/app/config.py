"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "AI Gateway"
    app_env: str = "production"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "postgresql://ai_gateway:password@localhost:5432/ai_gateway"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # Admin User
    admin_email: str = "admin@example.com"
    admin_password: str = "admin123"

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:80"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60

    # Logging
    log_level: str = "INFO"
    log_request_body: bool = False
    log_response_body: bool = False

    # OIDC (Optional) - Legacy single provider
    oidc_enabled: bool = False
    oidc_provider_url: Optional[str] = None
    oidc_client_id: Optional[str] = None
    oidc_client_secret: Optional[str] = None
    oidc_redirect_uri: Optional[str] = None
    
    # Google OAuth2 (Optional)
    google_oauth_enabled: bool = False
    google_client_id: Optional[str] = None
    google_client_secret: Optional[str] = None
    google_redirect_uri: Optional[str] = None
    
    # Keycloak OIDC (Optional)
    keycloak_enabled: bool = False
    keycloak_server_url: Optional[str] = None  # e.g., https://keycloak.example.com
    keycloak_realm: Optional[str] = None  # e.g., my-realm
    keycloak_client_id: Optional[str] = None
    keycloak_client_secret: Optional[str] = None
    keycloak_redirect_uri: Optional[str] = None

    # PII Masking (Presidio)
    pii_masking_enabled: bool = True
    pii_mask_request: bool = True
    pii_mask_response: bool = False
    pii_mask_type: str = "replace"  # replace, redact, hash
    pii_language: str = "en"

    # Security Scan (Optional)
    security_scan_enabled: bool = False

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
