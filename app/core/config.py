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
            default_factory=lambda: [
                "http://localhost:5173", "http://127.0.0.1:5173", "https://trustgate1-1.onrender.com",

            ],
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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=480,
        description="Lifetime for issued JWT access tokens in minutes.",
    )
    JWT_SECRET_KEY: SecretStr = Field(
        default=SecretStr("trustgate-dev-secret-change-me"),
        description="HMAC secret used to sign local JWT access tokens.",
    )
    JWT_ISSUER: str = Field(
        default="trustgate",
        description="JWT issuer claim.",
    )
    DOCUMENT_UPLOAD_DIR: str = Field(
        default="./uploads",
        description="Local upload directory for KYC and supporting documents.",
    )
    BOOTSTRAP_ADMIN_USERNAME: str = Field(
        default="admin",
        description="Seeded local administrator username.",
    )
    BOOTSTRAP_ADMIN_PASSWORD: SecretStr = Field(
        default=SecretStr("admin123!"),
        description="Seeded local administrator password.",
    )
    BOOTSTRAP_ADMIN_EMAIL: str = Field(
        default="admin@trustgate.local",
        description="Seeded local administrator email.",
    )
    BOOTSTRAP_ADMIN_FULL_NAME: str = Field(
        default="TrustGate Administrator",
        description="Seeded local administrator display name.",
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


    OPENSANCTIONS_API_KEY: SecretStr = Field(
        ...,
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
    DEFAULT_MONITORING_INTERVAL_DAYS: int = Field(
        default=30,
        ge=1,
        description="Default periodic monitoring interval in days.",
    )


settings = Settings()
