"""Tests for database engine and session management."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


class TestDatabase:
    """Tests for the database module."""

    def test_base_class_exists(self):
        """The Base declarative base should be importable."""
        assert Base is not None

    def test_engine_creation_with_sqlite(self):
        """Should be able to create an async engine with SQLite."""
        engine = create_async_engine(TEST_DB_URL, echo=False)

        assert engine is not None
        assert engine.name == "sqlite"

    def test_session_factory_creation(self):
        """Should be able to create a session factory."""
        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        assert factory is not None

    @pytest.mark.asyncio
    async def test_session_yields_async_session(self):
        """Session factory should yield AsyncSession instances."""
        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as session:
            assert isinstance(session, AsyncSession)
            assert session.is_active

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_can_create_and_query_tables(self):
        """Should be able to create tables and execute queries."""
        from sqlalchemy import String, select
        from sqlalchemy.orm import Mapped, mapped_column

        # Define a model for testing
        class TestModel(Base):
            __tablename__ = "test_models"
            id: Mapped[int] = mapped_column(primary_key=True)
            name: Mapped[str] = mapped_column(String(50))

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # Create tables
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Insert and query
        async with factory() as session:
            obj = TestModel(name="test")
            session.add(obj)
            await session.commit()

            result = await session.execute(select(TestModel).where(TestModel.name == "test"))
            fetched = result.scalar_one_or_none()
            assert fetched is not None
            assert fetched.name == "test"

        # Clean up
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()
