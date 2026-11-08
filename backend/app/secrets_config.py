"""Secrets: every credential the backend uses, read in one place.

    GRE_DATABASE_URL    PostgreSQL connection string (it holds the database password)
    ANTHROPIC_API_KEY   Claude API key (optional: without it the SDK looks in the
                        environment, then at an `ant auth login` profile)

Values come from the process environment (Vercel, Docker) or, for local runs,
the repository root .env. Each one is a SecretStr, so it shows up as '**********'
in logs, reprs and validation errors; call .get_secret_value() only at the
point of use. Ordinary, non-secret settings live in app/config.py.
"""
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# One .env at the repository root holds the settings for both halves of the
# app. Vite reads the same file, but only VITE_* values reach the browser.
ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def env_file() -> str | None:
    """GRE_ENV_FILE picks the settings file; empty disables it (the test suite
    does this so a developer's real .env can't change test results)."""
    return os.environ.get("GRE_ENV_FILE", str(ROOT_ENV_FILE)) or None


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_ENV_FILE,
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,  # a rejected value never lands in an error message
    )

    database_url: SecretStr = Field(validation_alias="GRE_DATABASE_URL")
    anthropic_api_key: SecretStr | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, url: SecretStr) -> SecretStr:
        value = url.get_secret_value()
        if not value.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            raise ValueError("GRE_DATABASE_URL must be a PostgreSQL connection string (postgresql://...)")
        # Supabase's direct host (db.<ref>.supabase.co) is IPv6-only, and Vercel
        # functions can't reach IPv6: every connection fails with "Cannot assign
        # requested address". Say so up front instead.
        if os.environ.get("VERCEL") and _is_supabase_direct_host(value):
            raise ValueError(
                "GRE_DATABASE_URL points at Supabase's direct connection (db.<ref>.supabase.co), "
                "which is IPv6-only and unreachable from Vercel. Use the Transaction pooler string "
                "from Supabase → Connect (…pooler.supabase.com:6543) instead."
            )
        return url


def _is_supabase_direct_host(url: str) -> bool:
    try:
        host = urlsplit(url).hostname or ""
    except ValueError:
        return False
    return host.startswith("db.") and host.endswith(".supabase.co")


@lru_cache
def get_secrets() -> Secrets:
    return Secrets(_env_file=env_file())
