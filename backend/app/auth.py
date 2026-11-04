"""Request authentication.

Dev mode trusts an `X-Dev-User` header so the app works before Clerk is wired
up. Clerk mode verifies the session JWT the Clerk frontend SDK sends as
`Authorization: Bearer <token>` and uses its `sub` claim (the Clerk user id,
e.g. "user_2abc...") as the user id.
"""
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException, status

from app.config import get_settings

CLOCK_SKEW_SECONDS = 5  # Clerk session tokens live 60 s; tolerate small clock drift


@lru_cache
def _jwks_client(url: str) -> jwt.PyJWKClient:
    # Caches Clerk's signing keys; refetches when a token names an unknown key id.
    return jwt.PyJWKClient(url, cache_keys=True)


def _verify_clerk_token(token: str) -> str:
    settings = get_settings()
    if not settings.clerk_jwks_url or not settings.clerk_issuer:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Clerk is not configured")
    try:
        key = _jwks_client(settings.clerk_jwks_url).get_signing_key_from_jwt(token)
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Could not reach Clerk to verify the session") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token") from exc
    try:
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=settings.clerk_issuer,
            leeway=CLOCK_SKEW_SECONDS,
            options={"require": ["exp", "iat", "sub", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid session token") from exc

    # Clerk recommends checking the authorized party so a token minted for
    # another site can't be replayed here.
    azp = claims.get("azp")
    if settings.clerk_authorized_parties and azp and azp not in settings.clerk_authorized_parties:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session token is for a different site")
    return claims["sub"]


def current_user_id(
    authorization: str | None = Header(default=None),
    x_dev_user: str | None = Header(default=None),
) -> str:
    settings = get_settings()
    if settings.auth_mode == "dev":
        return (x_dev_user or "dev-user")[:64]

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    return _verify_clerk_token(authorization.split(" ", 1)[1])
