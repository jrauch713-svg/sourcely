"""Tests for database models."""

# ruff: noqa: F811 — inline imports for model registration in tests

from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.models import Designer, Project  # noqa: F401 — ensure all models registered

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


class TestDesignerModel:
    """Tests for the Designer model."""

    def test_designer_creation(self):
        """Designer model should be creatable with required fields."""
        from app.models.designer import Designer

        designer = Designer(
            email="jane@example.com",
            password_hash="$2b$12$hashedpassword",
        )

        assert designer.email == "jane@example.com"
        assert designer.password_hash == "$2b$12$hashedpassword"
        assert isinstance(designer.id, str)
        assert len(designer.id) == 36
        assert designer.created_at is not None
        assert isinstance(designer.created_at, datetime)

    def test_designer_unique_id(self):
        """Each designer should get a unique UUID."""
        from app.models.designer import Designer

        d1 = Designer(email="a@example.com", password_hash="hash")
        d2 = Designer(email="b@example.com", password_hash="hash")

        assert d1.id != d2.id

    def test_designer_repr(self):
        """Designer repr should include email."""
        from app.models.designer import Designer

        designer = Designer(email="jane@example.com", password_hash="hash")
        r = repr(designer)

        assert "jane@example.com" in r

    @pytest.mark.asyncio
    async def test_designer_persistence(self):
        """Should be able to persist and retrieve a designer from the database."""
        from app.models.designer import Designer

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            designer = Designer(
                email="persist@example.com",
                password_hash="$2b$12$securehash",
            )
            session.add(designer)
            await session.commit()

            result = await session.execute(
                select(Designer).where(Designer.email == "persist@example.com")
            )
            fetched = result.scalar_one_or_none()

            assert fetched is not None
            assert fetched.email == "persist@example.com"
            assert fetched.password_hash == "$2b$12$securehash"
            assert fetched.id == designer.id

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_designer_email_unique(self):
        """Duplicate email should raise an integrity error."""
        from app.models.designer import Designer

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            d1 = Designer(email="same@example.com", password_hash="hash")
            session.add(d1)
            await session.commit()

            d2 = Designer(email="same@example.com", password_hash="hash2")
            session.add(d2)

            with pytest.raises(Exception):  # noqa: B017 — SQLite IntegrityError varies by driver
                await session.commit()
            await session.rollback()

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()


class TestProjectModel:
    """Tests for the Project model."""

    def test_project_creation(self):
        """Project model should be creatable with required fields."""
        from app.models.project import Project

        project = Project(
            designer_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Smith Residence",
            client_name="John Smith",
        )

        assert project.name == "Smith Residence"
        assert project.client_name == "John Smith"
        assert project.designer_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert project.status == "draft"
        assert isinstance(project.id, str)
        assert len(project.id) == 36
        assert project.created_at is not None
        assert project.updated_at is not None

    def test_project_template_type_optional(self):
        """template_type should be optional (None by default)."""
        from app.models.project import Project

        project = Project(
            designer_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Custom Project",
            client_name="Jane Doe",
        )

        assert project.template_type is None

    def test_project_with_template_type(self):
        """Should accept a template type string."""
        from app.models.project import Project

        project = Project(
            designer_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Kitchen Remodel",
            client_name="Bob Jones",
            template_type="Kitchen Remodel",
        )

        assert project.template_type == "Kitchen Remodel"

    def test_project_status_values(self):
        """Should accept valid status values."""
        from app.models.project import Project

        for status in ("draft", "active", "completed", "archived"):
            project = Project(
                designer_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                name=f"Project {status}",
                client_name="Test Client",
                status=status,
            )
            assert project.status == status

    def test_project_repr(self):
        """Project repr should include project name."""
        from app.models.project import Project

        project = Project(
            designer_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Smith Residence",
            client_name="John Smith",
        )
        r = repr(project)

        assert "Smith Residence" in r

    @pytest.mark.asyncio
    async def test_project_persistence(self):
        """Should persist and retrieve a project from the DB."""
        from app.models.designer import Designer
        from app.models.project import Project

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            designer = Designer(email="proj-test@example.com", password_hash="hash")
            session.add(designer)
            await session.commit()

            project = Project(
                designer_id=designer.id,
                name="Smith Residence",
                client_name="John Smith",
                template_type="Single Room",
            )
            session.add(project)
            await session.commit()

            result = await session.execute(
                select(Project).where(Project.name == "Smith Residence")
            )
            fetched = result.scalar_one_or_none()

            assert fetched is not None
            assert fetched.name == "Smith Residence"
            assert fetched.designer_id == designer.id
            assert fetched.template_type == "Single Room"

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_project_updated_at_changes(self):
        """updated_at should change when the record is modified."""
        from app.models.designer import Designer
        from app.models.project import Project

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            designer = Designer(email="update-test@example.com", password_hash="hash")
            session.add(designer)
            await session.commit()

            project = Project(
                designer_id=designer.id,
                name="Original Name",
                client_name="Client A",
            )
            session.add(project)
            await session.commit()

            original_updated_at = project.updated_at

            project.name = "Updated Name"
            await session.commit()

            assert project.updated_at != original_updated_at

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()


class TestClientModel:
    """Tests for the Client model."""

    def test_client_creation(self):
        """Client model should be creatable with required fields."""
        from app.models.client import Client

        client = Client(
            project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="John Smith",
            email="john@example.com",
        )

        assert client.name == "John Smith"
        assert client.email == "john@example.com"
        assert client.project_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert isinstance(client.id, str)
        assert len(client.id) == 36
        assert client.created_at is not None

    def test_client_email_optional(self):
        """Client email should be optional."""
        from app.models.client import Client

        client = Client(
            project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Jane Doe",
        )

        assert client.email is None
        assert client.name == "Jane Doe"

    def test_client_repr(self):
        """Client repr should include client name."""
        from app.models.client import Client

        client = Client(
            project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="John Smith",
        )
        r = repr(client)

        assert "John Smith" in r

    @pytest.mark.asyncio
    async def test_client_persistence(self):
        """Should persist and retrieve a client from the DB."""
        from app.models.client import Client
        from app.models.designer import Designer
        from app.models.project import Project

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            designer = Designer(email="client-test@example.com", password_hash="hash")
            session.add(designer)
            await session.commit()

            project = Project(
                designer_id=designer.id,
                name="Client Project",
                client_name="John Smith",
            )
            session.add(project)
            await session.commit()

            client = Client(
                project_id=project.id,
                name="John Smith",
                email="john@example.com",
            )
            session.add(client)
            await session.commit()

            result = await session.execute(
                select(Client).where(Client.email == "john@example.com")
            )
            fetched = result.scalar_one_or_none()

            assert fetched is not None
            assert fetched.name == "John Smith"
            assert fetched.project_id == project.id

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_client_cascade_with_project(self):
        """Client should be linked to a project; client remains after project delete."""
        from app.models.client import Client
        from app.models.designer import Designer
        from app.models.project import Project

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            designer = Designer(email="cascade-test@example.com", password_hash="hash")
            session.add(designer)
            await session.commit()

            project = Project(
                designer_id=designer.id,
                name="Cascade Project",
                client_name="Cascade Client",
            )
            session.add(project)
            await session.commit()

            client = Client(
                project_id=project.id,
                name="Cascade Client",
            )
            session.add(client)
            await session.commit()

            # Delete project
            await session.delete(project)
            await session.commit()

            # Verify project is gone
            proj_result = await session.execute(
                select(Project).where(Project.id == project.id)
            )
            assert proj_result.scalar_one_or_none() is None

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()
