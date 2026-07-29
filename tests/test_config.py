"""Tests for application configuration."""


class TestSettings:
    """Tests for application settings."""

    def test_default_database_url(self, monkeypatch):
        """Should have a default database URL."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        from app.config import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.database_url is not None
        assert "sourcely" in s.database_url

    def test_default_jwt_secret(self, monkeypatch):
        """Should have a JWT secret configured."""
        monkeypatch.delenv("JWT_SECRET", raising=False)
        from app.config import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_secret is not None
        assert len(s.jwt_secret) > 0

    def test_jwt_algorithm_default(self, monkeypatch):
        """Should default to HS256."""
        monkeypatch.delenv("JWT_ALGORITHM", raising=False)
        from app.config import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_algorithm == "HS256"

    def test_jwt_expire_minutes_default(self, monkeypatch):
        """Should default to 1440 minutes (24 hours)."""
        monkeypatch.delenv("JWT_EXPIRE_MINUTES", raising=False)
        from app.config import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_expire_minutes == 1440

    def test_cors_origins(self, monkeypatch):
        """Should have CORS origins configured."""
        monkeypatch.delenv("CORS_ORIGINS", raising=False)
        from app.config import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.cors_origins is not None
