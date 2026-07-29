"""Tests for authentication service and routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAuthService:
    """Tests for the auth service (password hashing, JWT)."""

    def test_hash_password(self):
        """Password hashing should produce a bcrypt hash."""
        from app.services.auth import AuthService

        hashed = AuthService.hash_password("mypassword123")

        assert hashed != "mypassword123"
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        """Correct password should verify successfully."""
        from app.services.auth import AuthService

        hashed = AuthService.hash_password("correct_password")
        assert AuthService.verify_password("correct_password", hashed) is True

    def test_verify_password_incorrect(self):
        """Incorrect password should fail verification."""
        from app.services.auth import AuthService

        hashed = AuthService.hash_password("correct_password")
        assert AuthService.verify_password("wrong_password", hashed) is False

    def test_create_access_token(self):
        """Should create a valid JWT token."""
        from app.services.auth import AuthService

        token = AuthService.create_access_token(
            data={"sub": "user123", "email": "test@example.com"}
        )

        assert isinstance(token, str)
        assert len(token) > 20

    def test_decode_access_token_valid(self):
        """Should decode a valid JWT token."""
        from app.services.auth import AuthService

        token = AuthService.create_access_token(
            data={"sub": "user123", "email": "test@example.com"}
        )
        payload = AuthService.decode_access_token(token)

        assert payload is not None
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"

    def test_decode_access_token_invalid(self):
        """Should return None for invalid token."""
        from app.services.auth import AuthService

        result = AuthService.decode_access_token("not.a.valid.token")
        assert result is None

    def test_hash_different_each_time(self):
        """Same password should produce different hashes (salt)."""
        from app.services.auth import AuthService

        hash1 = AuthService.hash_password("password")
        hash2 = AuthService.hash_password("password")

        assert hash1 != hash2


class TestRegisterEndpoint:
    """Tests for POST /api/auth/register."""

    @pytest.mark.asyncio
    async def test_register_success(self, client):
        """Should register a new designer successfully."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "newuser@example.com",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["user"]["email"] == "newuser@example.com"
        assert "password" not in data["user"]
        assert "password_hash" not in data["user"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        """Should reject duplicate email registration."""
        await client.post(
            "/api/auth/register",
            json={
                "email": "dupe@example.com",
                "password": "password123",
            },
        )

        response = await client.post(
            "/api/auth/register",
            json={
                "email": "dupe@example.com",
                "password": "different_password",
            },
        )

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_register_missing_fields(self, client):
        """Should reject registration with missing required fields."""
        response = await client.post(
            "/api/auth/register",
            json={"email": "test@example.com"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_weak_password(self, client):
        """Should reject passwords that are too short."""
        response = await client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "password": "short",
            },
        )

        assert response.status_code == 422


class TestLoginEndpoint:
    """Tests for POST /api/auth/login."""

    @pytest.mark.asyncio
    async def test_login_success(self, client):
        """Should login successfully with correct credentials."""
        await client.post(
            "/api/auth/register",
            json={
                "email": "loginuser@example.com",
                "password": "mypassword123",
            },
        )

        response = await client.post(
            "/api/auth/login",
            json={
                "email": "loginuser@example.com",
                "password": "mypassword123",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client):
        """Should reject login with wrong password."""
        await client.post(
            "/api/auth/register",
            json={
                "email": "wrongpw@example.com",
                "password": "correctpassword",
            },
        )

        response = await client.post(
            "/api/auth/login",
            json={
                "email": "wrongpw@example.com",
                "password": "wrongpassword",
            },
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_nonexistent_user(self, client):
        """Should reject login for non-existent user."""
        response = await client.post(
            "/api/auth/login",
            json={
                "email": "noone@example.com",
                "password": "whatever",
            },
        )

        assert response.status_code == 401


class TestMeEndpoint:
    """Tests for GET /api/auth/me."""

    @pytest.mark.asyncio
    async def test_me_authenticated(self, client):
        """Should return designer info when authenticated."""
        reg_response = await client.post(
            "/api/auth/register",
            json={
                "email": "meuser@example.com",
                "password": "mypassword",
            },
        )
        token = reg_response.json()["access_token"]

        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "meuser@example.com"
        assert "password_hash" not in data

    @pytest.mark.asyncio
    async def test_me_unauthenticated(self, client):
        """Should return 401 when not authenticated."""
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_invalid_token(self, client):
        """Should return 401 for invalid token."""
        response = await client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert response.status_code == 401
