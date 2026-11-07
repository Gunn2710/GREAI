import os
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GRE_", extra="ignore")

    # PostgreSQL connection string: Supabase in practice ("postgresql://...").
    database_url: str

    # "dev": the user id comes from the X-Dev-User header (default "dev-user").
    # Anyone can claim any user, so it is for local use only and must be
    # chosen explicitly (GRE_AUTH_MODE=dev).
    # "clerk": verify the Clerk session JWT from the Authorization header.
    auth_mode: Literal["dev", "clerk"] = "clerk"
    clerk_jwks_url: str | None = None  # https://<your-clerk-domain>/.well-known/jwks.json
    clerk_issuer: str | None = None    # https://<your-clerk-domain>
    # Origins allowed to use session tokens (the token's `azp` claim), e.g.
    # ["http://localhost:5173", "https://your-app.com"]. Empty = don't check.
    clerk_authorized_parties: list[str] = []
    # Approved accounts (Clerk mode). Empty = any signed-in Clerk user.
    # e.g. GRE_ALLOWED_EMAILS=["you@example.com"]
    allowed_emails: list[str] = []

    # Claude. Credentials come from ANTHROPIC_API_KEY (or an `ant auth login` profile).
    ai_enabled: bool = True
    claude_model: str = "claude-opus-5-5"
    claude_fallbacks: bool = True  # server-side refusal fallbacks

    cors_origins: list[str] = ["http://localhost:5173"]
    default_daily_new_words: int = 10
    seed_on_startup: bool = True

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, url: str) -> str:
        if not url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            raise ValueError("GRE_DATABASE_URL must be a PostgreSQL connection string (postgresql://...)")
        return url

    @model_validator(mode="after")
    def _locked_down_on_vercel(self) -> "Settings":
        """A deployment is on the open internet: refuse to start unless only
        signed-in, approved Clerk users can get in."""
        if not os.environ.get("VERCEL"):
            return self
        problems = []
        if self.auth_mode != "clerk":
            problems.append("GRE_AUTH_MODE must be clerk")
        if not self.clerk_jwks_url or not self.clerk_issuer:
            problems.append("GRE_CLERK_JWKS_URL and GRE_CLERK_ISSUER must be set")
        if not [e for e in self.allowed_emails if e.strip()]:
            problems.append("GRE_ALLOWED_EMAILS must list the approved accounts")
        if problems:
            raise ValueError("Unsafe settings for a Vercel deployment: " + "; ".join(problems))
        # Clerk tokens name the site they were issued for; accept this
        # deployment's own Vercel URLs on top of any configured domains.
        own = [f"https://{os.environ[k]}" for k in
               ("VERCEL_PROJECT_PRODUCTION_URL", "VERCEL_BRANCH_URL", "VERCEL_URL") if os.environ.get(k)]
        self.clerk_authorized_parties = list(dict.fromkeys([*self.clerk_authorized_parties, *own]))
        return self


@lru_cache
def get_settings() -> Settings:
    # GRE_ENV_FILE picks the settings file; empty disables it (the test suite
    # does this so a developer's real .env can't change test results).
    env_file = os.environ.get("GRE_ENV_FILE", ".env") or None
    return Settings(_env_file=env_file)
