"""Tests for Product model and product routes."""

# ruff: noqa: F811 — inline imports for model registration in tests

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.database import Base
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_get_token(client: AsyncClient) -> str:
    """Register a designer and return the JWT token."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "product-test@example.com", "password": "securepassword123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _create_project(client: AsyncClient, token: str, name: str = "Test Project") -> dict:
    """Create a project and return its dict."""
    resp = await client.post(
        "/api/projects",
        json={"name": name, "client_name": "Test Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


# ── Product Model Tests ───────────────────────────────────────────────────────


class TestProductModel:
    """Tests for the Product database model."""

    def test_product_creation(self):
        """Product model should be creatable with required fields."""
        from app.models.product import Product, ProductStatus

        product = Product(
            project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Sofa",
            vendor="West Elm",
            trade_price=1200.00,
            client_price=1800.00,
        )

        assert product.name == "Sofa"
        assert product.vendor == "West Elm"
        assert product.trade_price == 1200.00
        assert product.client_price == 1800.00
        assert product.status == ProductStatus.PROPOSED
        assert isinstance(product.id, str)
        assert len(product.id) == 36
        assert product.created_at is not None

    def test_product_defaults(self):
        """Should have correct defaults for optional fields."""
        from app.models.product import Product, ProductStatus

        product = Product(
            project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Lamp",
            vendor="IKEA",
            trade_price=49.99,
            client_price=79.99,
        )

        assert product.notes is None
        assert product.description is None
        assert product.status == ProductStatus.PROPOSED

    def test_product_with_notes(self):
        """Should accept notes and description."""
        from app.models.product import Product

        product = Product(
            project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Table",
            vendor="CB2",
            trade_price=800.00,
            client_price=1200.00,
            notes="Walnut finish, 60-inch",
            description="Dining table for main room",
        )

        assert product.notes == "Walnut finish, 60-inch"
        assert product.description == "Dining table for main room"

    def test_product_status_enum_values(self):
        """ProductStatus enum should have all expected values."""
        from app.models.product import ProductStatus

        values = [s.value for s in ProductStatus]
        assert "proposed" in values
        assert "approved" in values
        assert "ordered" in values
        assert "shipped" in values
        assert "received" in values
        assert "installed" in values

    def test_product_repr(self):
        """Product repr should include product name."""
        from app.models.product import Product

        product = Product(
            project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            name="Sofa",
            vendor="West Elm",
            trade_price=1200.00,
            client_price=1800.00,
        )
        r = repr(product)

        assert "Sofa" in r

    @pytest.mark.asyncio
    async def test_product_persistence(self):
        """Should persist and retrieve a product from the DB."""
        from app.models.designer import Designer
        from app.models.product import Product, ProductStatus
        from app.models.project import Project

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            designer = Designer(email="prod-persist@example.com", password_hash="hash")
            session.add(designer)
            await session.commit()

            project = Project(
                designer_id=designer.id,
                name="Persist Project",
                client_name="Test Client",
            )
            session.add(project)
            await session.commit()

            product = Product(
                project_id=project.id,
                name="Chair",
                vendor="Herman Miller",
                trade_price=900.00,
                client_price=1350.00,
            )
            session.add(product)
            await session.commit()

            result = await session.execute(
                select(Product).where(Product.name == "Chair")
            )
            fetched = result.scalar_one_or_none()

            assert fetched is not None
            assert fetched.name == "Chair"
            assert fetched.vendor == "Herman Miller"
            assert fetched.trade_price == 900.00
            assert fetched.status == ProductStatus.PROPOSED

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_product_project_relationship(self):
        """Product should be accessible via Project.products relationship."""
        from app.models.designer import Designer
        from app.models.product import Product
        from app.models.project import Project

        engine = create_async_engine(TEST_DB_URL, echo=False)
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with factory() as session:
            designer = Designer(email="rel-test@example.com", password_hash="hash")
            session.add(designer)
            await session.commit()

            project = Project(
                designer_id=designer.id,
                name="Rel Project",
                client_name="Rel Client",
            )
            session.add(project)
            await session.commit()

            p1 = Product(
                project_id=project.id,
                name="Item 1",
                vendor="Vendor A",
                trade_price=100.00,
                client_price=150.00,
            )
            p2 = Product(
                project_id=project.id,
                name="Item 2",
                vendor="Vendor B",
                trade_price=200.00,
                client_price=300.00,
            )
            session.add_all([p1, p2])
            await session.commit()

            # Refetch project with products eagerly loaded
            result = await session.execute(
                select(Project)
                .where(Project.id == project.id)
                .options(selectinload(Project.products))
            )
            fetched_project = result.scalar_one_or_none()

            assert fetched_project is not None
            assert len(fetched_project.products) == 2
            names = {p.name for p in fetched_project.products}
            assert names == {"Item 1", "Item 2"}

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

        await engine.dispose()


# ── Status Transition Tests ───────────────────────────────────────────────────


class TestProductStatusTransitions:
    """Tests for product status transition validation."""

    def test_valid_forward_transitions(self):
        """All forward transitions should be valid."""
        from app.models.product import Product, ProductStatus

        product = Product(
            project_id="a" * 36,
            name="Test Item",
            vendor="Test Vendor",
            trade_price=100.00,
            client_price=150.00,
        )

        transitions = [
            (ProductStatus.PROPOSED, ProductStatus.APPROVED),
            (ProductStatus.APPROVED, ProductStatus.ORDERED),
            (ProductStatus.ORDERED, ProductStatus.SHIPPED),
            (ProductStatus.SHIPPED, ProductStatus.RECEIVED),
            (ProductStatus.RECEIVED, ProductStatus.INSTALLED),
        ]

        for current, target in transitions:
            product.status = current
            product.validate_transition(target)  # Should not raise

    def test_same_status_valid(self):
        """Setting the same status should be OK (idempotent)."""
        from app.models.product import Product, ProductStatus

        product = Product(
            project_id="a" * 36,
            name="Test Item",
            vendor="Test Vendor",
            trade_price=100.00,
            client_price=150.00,
            status=ProductStatus.APPROVED,
        )

        product.validate_transition(ProductStatus.APPROVED)  # Should not raise

    def test_invalid_backward_transition(self):
        """Backward transitions should raise ValueError."""
        from app.models.product import Product, ProductStatus

        product = Product(
            project_id="a" * 36,
            name="Test Item",
            vendor="Test Vendor",
            trade_price=100.00,
            client_price=150.00,
            status=ProductStatus.ORDERED,
        )

        with pytest.raises(ValueError, match="Cannot move status"):
            product.validate_transition(ProductStatus.PROPOSED)

    def test_invalid_skip_forward(self):
        """Skipping steps forward should raise ValueError."""
        from app.models.product import Product, ProductStatus

        product = Product(
            project_id="a" * 36,
            name="Test Item",
            vendor="Test Vendor",
            trade_price=100.00,
            client_price=150.00,
            status=ProductStatus.PROPOSED,
        )

        with pytest.raises(ValueError, match="Cannot move status"):
            product.validate_transition(ProductStatus.ORDERED)

    def test_invalid_from_installed(self):
        """Cannot transition away from installed."""
        from app.models.product import Product, ProductStatus

        product = Product(
            project_id="a" * 36,
            name="Test Item",
            vendor="Test Vendor",
            trade_price=100.00,
            client_price=150.00,
            status=ProductStatus.INSTALLED,
        )

        with pytest.raises(ValueError, match="Cannot move status"):
            product.validate_transition(ProductStatus.APPROVED)


# ── Product Route Tests ───────────────────────────────────────────────────────


class TestProductCreateRoute:
    """Tests for POST /api/projects/{project_id}/products."""

    @pytest.mark.asyncio
    async def test_create_product_success(self, client):
        """Should create a product within a project."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={
                "name": "Sofa",
                "vendor": "West Elm",
                "trade_price": 1200.00,
                "client_price": 1800.00,
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Sofa"
        assert data["vendor"] == "West Elm"
        assert data["trade_price"] == 1200.00
        assert data["client_price"] == 1800.00
        assert data["status"] == "proposed"
        assert data["project_id"] == project["id"]

    @pytest.mark.asyncio
    async def test_create_product_missing_required(self, client):
        """Should return 422 when required fields are missing."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Just a name"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_product_unauthenticated(self, client):
        """Should return 401 without auth."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Sofa", "vendor": "V", "trade_price": 1.0, "client_price": 2.0},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_product_invalid_project(self, client):
        """Should return 404 for non-existent project."""
        token = await _register_and_get_token(client)

        resp = await client.post(
            "/api/projects/nonexistent-id/products",
            json={"name": "Sofa", "vendor": "V", "trade_price": 1.0, "client_price": 2.0},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404


class TestProductListRoute:
    """Tests for GET /api/projects/{project_id}/products."""

    @pytest.mark.asyncio
    async def test_list_products_empty(self, client):
        """Should return empty list for project with no products."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.get(
            f"/api/projects/{project['id']}/products",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_products(self, client):
        """Should list all products for a project."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        # Create two products
        await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Item A", "vendor": "V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Item B", "vendor": "W", "trade_price": 30, "client_price": 40},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.get(
            f"/api/projects/{project['id']}/products",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {p["name"] for p in data}
        assert names == {"Item A", "Item B"}

    @pytest.mark.asyncio
    async def test_list_products_unauthenticated(self, client):
        """Should return 401 without auth."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.get(f"/api/projects/{project['id']}/products")

        assert resp.status_code == 401


class TestProductGetRoute:
    """Tests for GET /api/projects/{project_id}/products/{product_id}."""

    @pytest.mark.asyncio
    async def test_get_product(self, client):
        """Should get a single product by ID."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Rug", "vendor": "Ruggable", "trade_price": 200, "client_price": 350},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/projects/{project['id']}/products/{product_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Rug"

    @pytest.mark.asyncio
    async def test_get_product_not_found(self, client):
        """Should return 404 for non-existent product."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.get(
            f"/api/projects/{project['id']}/products/nonexistent",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404


class TestProductUpdateRoute:
    """Tests for PUT /api/projects/{project_id}/products/{product_id}."""

    @pytest.mark.asyncio
    async def test_update_product(self, client):
        """Should update product fields."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Old Name", "vendor": "Old V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/projects/{project['id']}/products/{product_id}",
            json={"name": "New Name", "vendor": "New V", "trade_price": 15, "client_price": 25},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "New Name"
        assert data["vendor"] == "New V"
        assert data["trade_price"] == 15
        assert data["client_price"] == 25

    @pytest.mark.asyncio
    async def test_update_product_partial(self, client):
        """Should allow partial updates (only some fields)."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Original", "vendor": "Old V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/projects/{project['id']}/products/{product_id}",
            json={"name": "Renamed Only"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Renamed Only"
        assert data["vendor"] == "Old V"  # Unchanged


class TestProductDeleteRoute:
    """Tests for DELETE /api/projects/{project_id}/products/{product_id}."""

    @pytest.mark.asyncio
    async def test_delete_product(self, client):
        """Should delete a product."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "To Delete", "vendor": "V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/projects/{project['id']}/products/{product_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 204

        # Verify gone
        get_resp = await client.get(
            f"/api/projects/{project['id']}/products/{product_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 404


class TestProductStatusTransitionRoute:
    """Tests for PATCH /api/projects/{project_id}/products/{product_id}/status."""

    @pytest.mark.asyncio
    async def test_transition_proposed_to_approved(self, client):
        """Should move from proposed to approved."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Item", "vendor": "V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/projects/{project['id']}/products/{product_id}/status",
            json={"status": "approved"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    @pytest.mark.asyncio
    async def test_transition_through_full_pipeline(self, client):
        """Should be able to move through all statuses in order."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Full Cycle", "vendor": "V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        steps = ["approved", "ordered", "shipped", "received", "installed"]
        for status in steps:
            resp = await client.patch(
                f"/api/projects/{project['id']}/products/{product_id}/status",
                json={"status": status},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, f"Failed at {status}: {resp.text}"
            assert resp.json()["status"] == status

    @pytest.mark.asyncio
    async def test_transition_invalid_backward(self, client):
        """Should reject backward status transitions."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Backward Test", "vendor": "V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        # Move to approved first
        await client.patch(
            f"/api/projects/{project['id']}/products/{product_id}/status",
            json={"status": "approved"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Then try to go back to proposed
        resp = await client.patch(
            f"/api/projects/{project['id']}/products/{product_id}/status",
            json={"status": "proposed"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_transition_invalid_skip(self, client):
        """Should reject skipping a step."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Skip Test", "vendor": "V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        # Try to jump from proposed straight to shipped
        resp = await client.patch(
            f"/api/projects/{project['id']}/products/{product_id}/status",
            json={"status": "shipped"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_transition_invalid_status_value(self, client):
        """Should reject unknown status values."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        create_resp = await client.post(
            f"/api/projects/{project['id']}/products",
            json={"name": "Bad Status", "vendor": "V", "trade_price": 10, "client_price": 20},
            headers={"Authorization": f"Bearer {token}"},
        )
        product_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/projects/{project['id']}/products/{product_id}/status",
            json={"status": "nonexistent_status"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422
