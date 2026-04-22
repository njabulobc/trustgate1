from pydantic import Field, SecretStr
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


settings = Settings()