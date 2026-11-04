from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="GRE_", extra="ignore")

    # SQLite for local dev. For Supabase, point this at the project's Postgres
    # connection string (postgresql+psycopg://...); the schema is portable.
    database_url: str = "sqlite:///./gre_prep.db"

    # "dev": the user id comes from the X-Dev-User header (default "dev-user").
    # "clerk": verify the Clerk session JWT from the Authorization header.
    auth_mode: Literal["dev", "clerk"] = "dev"
    clerk_jwks_url: str | None = None  # https://<your-clerk-domain>/.well-known/jwks.json
    clerk_issuer: str | None = None    # https://<your-clerk-domain>
    # Origins allowed to use session tokens (the token's `azp` claim), e.g.
    # ["http://localhost:5173", "https://your-app.com"]. Empty = don't check.
    clerk_authorized_parties: list[str] = []

    # Claude. Credentials come from ANTHROPIC_API_KEY (or an `ant auth login` profile).
    ai_enabled: bool = True
    claude_model: str = "claude-opus-5-5"
    claude_fallbacks: bool = True  # server-side refusal fallbacks

    cors_origins: list[str] = ["http://localhost:5173"]
    default_daily_new_words: int = 10
    seed_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
