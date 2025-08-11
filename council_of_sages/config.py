from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(
        default="Council of Sages", description="Application name"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")
    env: str = Field(default="development", description="Environment")

    # CORS settings
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        description="Allowed CORS origins",
    )
    cors_allow_credentials: bool = Field(
        default=True, description="Allow credentials in CORS requests"
    )
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["*"], description="Allowed CORS methods"
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["*"], description="Allowed CORS headers"
    )

    # API Keys (optional)
    openai_api_key: str | None = Field(
        default=None, description="OpenAI API key"
    )
    anthropic_api_key: str | None = Field(
        default=None, description="Anthropic API key"
    )
    mongodb_url: str | None = Field(
        default=None, description="MongoDB connection URL"
    )

    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.env.lower() in ("development", "dev")

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.env.lower() in ("production", "prod")


# Global configuration instance
config = Config()
