"""Configuration management using pydantic-settings."""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Note: Subreddit configuration has moved to Source Sets.
    Use `pain-radar sources-add <preset>` to configure sources.
    """

    model_config = SettingsConfigDict(
        env_prefix="PAIN_RADAR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Reddit fetching parameters (defaults for source sets)
    listing: str = Field(
        default="new",
        description="Default Reddit listing type: hot, new, top, rising",
    )
    posts_per_subreddit: int = Field(
        default=25,
        ge=1,
        le=100,
        description="Default posts to fetch per subreddit",
    )
    top_comments: int = Field(
        default=15,
        ge=0,
        le=100,
        description="Number of top comments to fetch per post",
    )

    # Concurrency control
    max_concurrency: int = Field(
        default=8,
        ge=1,
        le=50,
        description="Maximum concurrent requests",
    )

    # Storage (SQLite for CLI, Postgres for SaaS)
    db_path: str = Field(
        default="pain_radar.sqlite3",
        description="Path to SQLite database file (CLI mode)",
    )

    # ==========================================================================
    # SAAS CONFIGURATION (used when running as multi-tenant service)
    # ==========================================================================

    # Database (Postgres for SaaS)
    database_url: str | None = Field(
        default=None,
        description="PostgreSQL connection URL (e.g., postgresql://user:pass@host:5432/db)",
    )

    # Authentication
    secret_key: str = Field(
        default="change-me-in-production-use-secrets-generator",
        description="Secret key for signing sessions and tokens",
    )
    magic_link_expiry_minutes: int = Field(
        default=15,
        description="Magic link expiration time in minutes",
    )
    session_expiry_days: int = Field(
        default=30,
        description="Session expiration time in days",
    )

    # Stripe billing
    stripe_secret_key: str | None = Field(
        default=None,
        description="Stripe secret key for billing",
    )
    stripe_webhook_secret: str | None = Field(
        default=None,
        description="Stripe webhook signing secret",
    )
    stripe_price_starter_monthly: str | None = Field(
        default=None,
        description="Stripe price ID for Starter monthly plan",
    )
    stripe_price_pro_monthly: str | None = Field(
        default=None,
        description="Stripe price ID for Pro monthly plan",
    )
    stripe_price_team_monthly: str | None = Field(
        default=None,
        description="Stripe price ID for Team monthly plan",
    )

    # Email delivery
    email_provider: str = Field(
        default="resend",
        description="Email provider: resend, postmark, sendgrid",
    )
    email_api_key: str | None = Field(
        default=None,
        description="Email provider API key",
    )
    email_from_address: str = Field(
        default="noreply@painradar.io",
        description="From address for transactional emails",
    )

    # Redis (for job queue)
    redis_url: str | None = Field(
        default=None,
        description="Redis connection URL for job queue",
    )

    # API settings
    api_rate_limit_per_minute: int = Field(
        default=60,
        description="Default API rate limit per minute",
    )

    # OpenAI configuration
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "PAIN_RADAR_OPENAI_API_KEY"),
        description="OpenAI API key (accepts OPENAI_API_KEY or PAIN_RADAR_OPENAI_API_KEY)",
    )
    openai_model: str = Field(
        default="gpt-4o",
        description="OpenAI model to use for pain signal analysis",
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR",
    )
    log_json: bool = Field(
        default=False,
        description="Output logs as JSON (for production)",
    )

    # User agent for scraping
    user_agent: str = Field(
        default="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        description="User agent string for HTTP requests",
    )

    @property
    def is_saas_mode(self) -> bool:
        """Check if running in SaaS mode (Postgres configured)."""
        return self.database_url is not None


def get_settings() -> Settings:
    """Load and return application settings."""
    return Settings()


settings = get_settings()
