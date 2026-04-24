from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        default="sqlite:///./trustgate.db",
        description="SQLite database URL for the TrustGate MVP.",
    )

    CORS_ALLOW_ORIGINS: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173"],
        description=(
            "Allowed CORS origins. In production, set this explicitly via environment "
            "variables (e.g., CORS_ALLOW_ORIGINS='[\"https://app.example.com\"]' or a "
            "comma-separated list)."
        ),
    )
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=False,
        description="Whether CORS should allow credentials (cookies/Authorization headers).",
    )

    JWT_SECRET_KEY: SecretStr = Field(
        ...,
        description="Signing key used to generate and validate JWT tokens.",
    )
    SEED_ADMIN_EMAIL: str | None = Field(
        default=None,
        description=(
            "Optional bootstrap admin email. When unset, automatic seed admin creation "
            "is disabled."
        ),
    )
    SEED_ADMIN_PASSWORD: SecretStr | None = Field(
        default=None,
        description=(
            "Optional bootstrap admin password. Must be set together with "
            "SEED_ADMIN_EMAIL."
        ),
    )

    OPENSANCTIONS_API_KEY: SecretStr = Field(
        default=SecretStr("demo-api-key"),
        description="OpenSanctions API key loaded from environment variables.",
    )
    OPENSANCTIONS_BASE_URL: str = Field(
        default="https://api.opensanctions.org",
        description="Base URL for OpenSanctions API requests.",
    )

    SCREENING_MIN_SCORE: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum provider match score to retain as a screening candidate.",
    )
    SCREENING_REVIEW_SCORE: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Score threshold above which a candidate should be flagged for analyst review.",
    )
    SCREENING_HIGH_CONFIDENCE_SCORE: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        description="Score threshold treated as a high-confidence screening match.",
    )

    @field_validator("CORS_ALLOW_ORIGINS", mode="before")
    @classmethod
    def parse_cors_allow_origins(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("["):
                return value
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret_key(cls, value: SecretStr) -> SecretStr:
        raw_value = value.get_secret_value().strip()
        if not raw_value or raw_value == "dev-change-me":
            raise ValueError("JWT_SECRET_KEY must be explicitly set to a non-default value.")
        return SecretStr(raw_value)

    @field_validator("SEED_ADMIN_PASSWORD")
    @classmethod
    def validate_seed_admin_password(cls, value: SecretStr | None, info):
        email = info.data.get("SEED_ADMIN_EMAIL")
        if email and value is None:
            raise ValueError("SEED_ADMIN_PASSWORD must be set when SEED_ADMIN_EMAIL is configured.")
        if value is not None and not email:
            raise ValueError("SEED_ADMIN_EMAIL must be set when SEED_ADMIN_PASSWORD is configured.")
        if value is not None and value.get_secret_value() == "trustgate-admin":
            raise ValueError("SEED_ADMIN_PASSWORD cannot use known default credentials.")
        return value


settings = Settings()
