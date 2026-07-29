"""Tests for project CRUD routes."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


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
        json={"email": "proj-route-test@example.com", "password": "securepassword123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


class TestProjectCreateRoute:
    """Tests for POST /api/projects."""

    @pytest.mark.asyncio
    async def test_create_project_success(self, client):
        """Should create a project for an authenticated designer."""
        token = await _register_and_get_token(client)

        resp = await client.post(
            "/api/projects",
            json={"name": "Smith Residence", "client_name": "John Smith"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Smith Residence"
        assert data["client_name"] == "John Smith"
        assert data["status"] == "draft"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_project_unauthenticated(self, client):
        """Should return 401 without auth."""
        resp = await client.post(
            "/api/projects",
            json={"name": "No Auth Project", "client_name": "Nobody"},
        )

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_project_missing_fields(self, client):
        """Should reject missing required fields."""
        token = await _register_and_get_token(client)

        resp = await client.post(
            "/api/projects",
            json={"name": "Missing client_name"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_project_with_template(self, client):
        """Should accept optional template_type."""
        token = await _register_and_get_token(client)

        resp = await client.post(
            "/api/projects",
            json={
                "name": "Kitchen Remodel",
                "client_name": "Jane Doe",
                "template_type": "Kitchen Remodel",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201
        assert resp.json()["template_type"] == "Kitchen Remodel"


class TestProjectListRoute:
    """Tests for GET /api/projects."""

    @pytest.mark.asyncio
    async def test_list_projects_empty(self, client):
        """Should return empty list for a new designer."""
        token = await _register_and_get_token(client)

        resp = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_projects(self, client):
        """Should return all projects for the designer."""
        token = await _register_and_get_token(client)

        # Create two projects
        await client.post(
            "/api/projects",
            json={"name": "Project A", "client_name": "Client A"},
            headers={"Authorization": f"Bearer {token}"},
        )
        await client.post(
            "/api/projects",
            json={"name": "Project B", "client_name": "Client B"},
            headers={"Authorization": f"Bearer {token}"},
        )

        resp = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = {p["name"] for p in data}
        assert names == {"Project A", "Project B"}

    @pytest.mark.asyncio
    async def test_list_projects_unauthenticated(self, client):
        """Should return 401 without auth."""
        resp = await client.get("/api/projects")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_projects_scoped_to_designer(self, client):
        """Projects should be scoped to the authenticated designer."""
        # Create designer A + project
        token_a = await _register_and_get_token(client)
        await client.post(
            "/api/projects",
            json={"name": "Designer A Project", "client_name": "Client A"},
            headers={"Authorization": f"Bearer {token_a}"},
        )

        # Register designer B separately
        resp_b = await client.post(
            "/api/auth/register",
            json={"email": "designer-b@example.com", "password": "securepassword123"},
        )
        token_b = resp_b.json()["access_token"]

        # Designer B should see their own empty list, not A's project
        resp = await client.get(
            "/api/projects",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        assert resp.status_code == 200
        assert resp.json() == []


class TestProjectGetRoute:
    """Tests for GET /api/projects/{project_id}."""

    @pytest.mark.asyncio
    async def test_get_project(self, client):
        """Should get a project by ID."""
        token = await _register_and_get_token(client)

        create_resp = await client.post(
            "/api/projects",
            json={"name": "Get Me", "client_name": "Test"},
            headers={"Authorization": f"Bearer {token}"},
        )
        project_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Me"

    @pytest.mark.asyncio
    async def test_get_project_not_found(self, client):
        """Should return 404 for non-existent project."""
        token = await _register_and_get_token(client)

        resp = await client.get(
            "/api/projects/nonexistent-id",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_project_other_designer(self, client):
        """Should not be able to get another designer's project."""
        # Create designer A + project
        resp_a = await client.post(
            "/api/auth/register",
            json={"email": "owner@example.com", "password": "securepassword123"},
        )
        token_a = resp_a.json()["access_token"]

        create_resp = await client.post(
            "/api/projects",
            json={"name": "Owner Project", "client_name": "Owner Client"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        project_id = create_resp.json()["id"]

        # Register designer B
        resp_b = await client.post(
            "/api/auth/register",
            json={"email": "intruder@example.com", "password": "securepassword123"},
        )
        token_b = resp_b.json()["access_token"]

        # Designer B tries to access A's project
        resp = await client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        assert resp.status_code == 404


class TestProjectUpdateRoute:
    """Tests for PUT /api/projects/{project_id}."""

    @pytest.mark.asyncio
    async def test_update_project(self, client):
        """Should update a project."""
        token = await _register_and_get_token(client)

        create_resp = await client.post(
            "/api/projects",
            json={"name": "Original", "client_name": "Original Client"},
            headers={"Authorization": f"Bearer {token}"},
        )
        project_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/projects/{project_id}",
            json={"name": "Updated", "client_name": "Updated Client"},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated"
        assert data["client_name"] == "Updated Client"


class TestProjectDeleteRoute:
    """Tests for DELETE /api/projects/{project_id}."""

    @pytest.mark.asyncio
    async def test_delete_project(self, client):
        """Should delete a project."""
        token = await _register_and_get_token(client)

        create_resp = await client.post(
            "/api/projects",
            json={"name": "To Delete", "client_name": "Delete Me"},
            headers={"Authorization": f"Bearer {token}"},
        )
        project_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 204

        # Verify gone
        get_resp = await client.get(
            f"/api/projects/{project_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 404
