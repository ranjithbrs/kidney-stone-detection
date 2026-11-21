"""Security verification tests for JWT secret enforcement, environment gating, and token integrity."""

import os
import sys
import pytest
from itsdangerous import URLSafeTimedSerializer

import backend.main as bmain


def test_jwt_secret_required_in_production(monkeypatch):
    """Verify that in production mode, missing NEFROAI_JWT_SECRET raises RuntimeError."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("NEFROAI_JWT_SECRET", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    # In production without a secret, resolve_jwt_secret must fail safely
    with pytest.raises(RuntimeError) as exc_info:
        bmain.resolve_jwt_secret()

    assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc_info.value)
    assert "production mode" in str(exc_info.value)


def test_jwt_secret_development_fallback(monkeypatch, tmp_path):
    """Verify that in development mode, a local session secret is generated/used without failure."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("NEFROAI_JWT_SECRET", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.setattr(bmain, "ROOT_DIR", str(tmp_path))

    secret = bmain.resolve_jwt_secret()
    assert isinstance(secret, str)
    assert len(secret) >= 32

    # Subsequent call in same environment returns same persistent secret
    secret_again = bmain.resolve_jwt_secret()
    assert secret_again == secret


def test_jwt_explicit_secret_takes_precedence(monkeypatch):
    """Verify that an explicitly provided NEFROAI_JWT_SECRET is used regardless of environment."""
    test_secret = "custom-prod-secret-9999-abcdef1234567890"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NEFROAI_JWT_SECRET", test_secret)

    resolved = bmain.resolve_jwt_secret()
    assert resolved == test_secret


def test_jwt_token_signing_and_decoding(monkeypatch):
    """Verify round-trip cryptographic signing and decoding of user claims."""
    test_secret = "test-signing-secret-key-1234567890abcdef"
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEFROAI_JWT_SECRET", test_secret)

    user = {
        "username": "dr_clinician_sec",
        "role": "Nephrologist",
        "full_name": "Dr. Security Tester",
        "email": "sec@nefroai.org",
    }
    token = bmain._create_access_token(user)
    assert isinstance(token, str)
    assert len(token) > 20

    claims = bmain._decode_access_token(token)
    assert claims["sub"] == "dr_clinician_sec"
    assert claims["role"] == "Nephrologist"
    assert claims["full_name"] == "Dr. Security Tester"


def test_jwt_tampered_token_rejected(monkeypatch):
    """Verify that any modification to token characters is caught and rejected."""
    test_secret = "test-tamper-proof-secret-key-abcdef"
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEFROAI_JWT_SECRET", test_secret)

    user = {"username": "admin", "role": "Admin", "full_name": "Administrator"}
    token = bmain._create_access_token(user)

    # Tamper with the signature bytes
    tampered = token[:-4] + "XXXX"
    with pytest.raises(Exception):
        bmain._decode_access_token(tampered)


def test_secret_never_exposed_in_health_or_presets(monkeypatch):
    """Ensure that the JWT secret is never present in health check or preset API outputs."""
    test_secret = "super-secret-key-should-never-leak-in-api"
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NEFROAI_JWT_SECRET", test_secret)

    health = bmain.health_check()
    presets = bmain.get_clinical_presets()

    # Verify secret is not a value in any dictionary level
    health_str = str(health)
    presets_str = str(presets)

    assert test_secret not in health_str
    assert test_secret not in presets_str
