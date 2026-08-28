"""
Tests for Supabase authentication and JWT verification subsystem.
"""

import jwt
import pytest
from fastapi.testclient import TestClient

from nexus.api.app import create_app
from nexus.core.config import NexusSettings
from nexus.security.supabase_auth import SupabaseUser, decode_supabase_jwt, verify_supabase_token


def test_supabase_jwt_decoding_unverified():
    payload = {
        "sub": "user-123-abc",
        "email": "test@example.com",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": 2524608000,  # far future timestamp
    }
    token = jwt.encode(payload, "secret123", algorithm="HS256")

    decoded = decode_supabase_jwt(token, secret="", verify_signature=False)
    assert decoded is not None
    assert decoded["sub"] == "user-123-abc"
    assert decoded["email"] == "test@example.com"


def test_supabase_jwt_decoding_verified():
    secret = "my-supabase-super-secret"
    payload = {
        "sub": "user-456-def",
        "email": "hero@nexus.ai",
        "role": "authenticated",
        "aud": "authenticated",
        "exp": 2524608000,
    }
    token = jwt.encode(payload, secret, algorithm="HS256")

    user = verify_supabase_token(token, settings=NexusSettings(supabase_jwt_secret=secret))
    assert user is not None
    assert user.user_id == "user-456-def"
    assert user.email == "hero@nexus.ai"


def test_auth_status_endpoint():
    app = create_app(NexusSettings(supabase_url="https://yxvwhewzbifgttmiasas.supabase.co"))
    client = TestClient(app)

    response = client.get("/api/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "supabase"
    assert data["configured"] is True
    assert data["status"] == "ready"


def test_auth_me_endpoint_dev_fallback():
    app = create_app(NexusSettings(supabase_url="https://yxvwhewzbifgttmiasas.supabase.co"))
    client = TestClient(app)

    response = client.get("/api/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is True
    assert "user_id" in data
