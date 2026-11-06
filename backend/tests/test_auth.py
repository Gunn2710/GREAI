"""Clerk session-token verification, with a locally generated RSA key standing
in for Clerk's signing key (its JWKS endpoint is stubbed)."""
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app import auth
from app.config import get_settings

ISSUER = "https://clerk.example.test"
JWKS_URL = f"{ISSUER}/.well-known/jwks.json"
ORIGIN = "http://localhost:5173"


def make_key(kid: str):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return private, jwk


CLERK_KEY, CLERK_JWK = make_key("clerk-key-1")
OTHER_KEY, _ = make_key("clerk-key-1")  # same key id, different key: forged signature


def token(sub="user_2abc", key=CLERK_KEY, kid="clerk-key-1", **overrides) -> str:
    now = int(time.time())
    claims = {"sub": sub, "iss": ISSUER, "iat": now, "nbf": now, "exp": now + 60, "azp": ORIGIN}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


@pytest.fixture
def clerk_mode(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "auth_mode", "clerk")
    monkeypatch.setattr(settings, "clerk_jwks_url", JWKS_URL)
    monkeypatch.setattr(settings, "clerk_issuer", ISSUER)
    monkeypatch.setattr(settings, "clerk_authorized_parties", [ORIGIN])
    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", lambda self: {"keys": [CLERK_JWK]})
    auth._jwks_client.cache_clear()
    yield
    auth._jwks_client.cache_clear()


def profile(client, bearer: str | None, dev_user: str | None = None):
    headers = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if dev_user:
        headers["X-Dev-User"] = dev_user
    return client.get("/api/me/profile", headers=headers)


def test_valid_token_identifies_the_user(client, clerk_mode):
    assert profile(client, token(sub="user_alice")).status_code == 200
    assert auth._verify_clerk_token(token(sub="user_alice")) == "user_alice"


@pytest.mark.parametrize("bad", [
    token(exp=int(time.time()) - 120),             # expired (beyond leeway)
    token(iss="https://evil.example.test"),        # wrong issuer
    token(azp="https://evil.example.test"),        # minted for another site
    token(key=OTHER_KEY),                          # forged signature
    token(kid="unknown-key"),                      # key Clerk never published
    token(sub=None),                               # no subject
    "not-a-jwt",
])
def test_bad_tokens_are_rejected(client, clerk_mode, bad):
    assert profile(client, bad).status_code == 401


def test_small_clock_skew_is_tolerated(client, clerk_mode):
    assert profile(client, token(exp=int(time.time()) - 2)).status_code == 200


def test_token_without_azp_is_accepted(client, clerk_mode):
    assert profile(client, token(azp=None)).status_code == 200


def test_dev_header_is_ignored_in_clerk_mode(client, clerk_mode):
    assert profile(client, None, dev_user="anyone").status_code == 401


def test_clerk_unreachable_is_503(client, clerk_mode, monkeypatch):
    def boom(self):
        raise jwt.PyJWKClientConnectionError("down")

    monkeypatch.setattr(jwt.PyJWKClient, "fetch_data", boom)
    auth._jwks_client.cache_clear()
    assert profile(client, token()).status_code == 503


def test_users_are_isolated_by_token(client, clerk_mode):
    a = client.put("/api/me/profile", json={"daily_new_words": 3},
                   headers={"Authorization": f"Bearer {token(sub='user_a')}"})
    b = profile(client, token(sub="user_b"))
    assert a.json()["daily_new_words"] == 3
    assert b.json()["daily_new_words"] != 3


# --- Approved accounts (GRE_ALLOWED_EMAILS) --------------------------------------

@pytest.fixture
def approved_only(clerk_mode, monkeypatch):
    monkeypatch.setattr(get_settings(), "allowed_emails", ["Owner@Example.com"])


def me(client, bearer):
    return client.get("/api/me", headers={"Authorization": f"Bearer {bearer}"})


def test_approved_email_gets_in(client, approved_only):
    res = me(client, token(sub="user_owner", primaryEmail="owner@example.com"))  # case-insensitive
    assert res.status_code == 200 and res.json() == {"user_id": "user_owner"}


@pytest.mark.parametrize("claims", [
    {"primaryEmail": "stranger@example.com"},   # signed in, but not approved
    {},                                          # token without the email claim
    {"primaryEmail": ""},
])
def test_unapproved_accounts_are_refused(client, approved_only, claims):
    res = me(client, token(sub="user_other", **claims))
    assert res.status_code == 403
    assert res.json()["detail"] == "account_not_approved"
    # ...on every endpoint, not just /api/me
    bearer = {"Authorization": f"Bearer {token(sub='user_other', **claims)}"}
    assert client.get("/api/stats", headers=bearer).status_code == 403
    assert client.get("/api/study/next", headers=bearer).status_code == 403


def test_invalid_token_is_still_401_not_403(client, approved_only):
    assert me(client, token(key=OTHER_KEY, primaryEmail="owner@example.com")).status_code == 401


def test_no_list_means_any_signed_in_user(client, clerk_mode):
    assert me(client, token(sub="user_any", primaryEmail="anyone@example.com")).status_code == 200


def test_list_is_ignored_in_dev_mode(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "allowed_emails", ["owner@example.com"])
    assert client.get("/api/me", headers={"X-Dev-User": "dev"}).status_code == 200
