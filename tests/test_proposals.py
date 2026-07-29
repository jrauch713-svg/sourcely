"""Tests for Proposal model and proposal routes (client-facing share links)."""

# ruff: noqa: F811 — inline imports for model registration in tests

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_get_token(
    client: AsyncClient, email: str = "proposal@example.com"
) -> str:
    """Register a designer and return the JWT token."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "securepassword123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _register_second_designer(client: AsyncClient) -> str:
    """Register a second designer (for ownership tests)."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "other-designer@example.com", "password": "securepassword123"},
    )
    assert resp.status_code == 201
    return resp.json()["access_token"]


async def _create_project(
    client: AsyncClient, token: str, name: str = "Test Project"
) -> dict:
    """Create a project and return its dict."""
    resp = await client.post(
        "/api/projects",
        json={"name": name, "client_name": "Test Client"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_product(
    client: AsyncClient, token: str, project_id: str, name: str = "Sofa"
) -> dict:
    """Create a product within a project and return its dict."""
    resp = await client.post(
        f"/api/projects/{project_id}/products",
        json={
            "name": name,
            "vendor": "West Elm",
            "trade_price": 1200.00,
            "client_price": 1800.00,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


async def _create_proposal(
    client: AsyncClient, token: str, project_id: str
) -> dict:
    """Create a proposal for a project and return its dict."""
    resp = await client.post(
        f"/api/projects/{project_id}/proposals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()


async def _setup_proposal_with_product(client: AsyncClient) -> tuple[dict, str, dict]:
    """Boilerplate: register designer, create project + product + proposal.

    Returns (proposal_dict, token, product_dict).
    """
    token = await _register_and_get_token(client)
    project = await _create_project(client, token)
    product = await _create_product(client, token, project["id"])
    proposal = await _create_proposal(client, token, project["id"])
    return proposal, token, product


# ── Proposal Model Tests ─────────────────────────────────────────────────────


class TestProposalModel:
    """Tests for the Proposal database model."""

    def test_proposal_creation(self):
        """Proposal model should be creatable with required fields."""
        from app.models.proposal import Proposal

        proposal = Proposal(project_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

        assert proposal.project_id == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        assert isinstance(proposal.id, str)
        assert len(proposal.id) == 36
        assert isinstance(proposal.share_token, str)
        assert len(proposal.share_token) > 0
        assert proposal.sent_at is None
        assert proposal.created_at is not None

    def test_proposal_share_token_is_unguessable(self):
        """Share tokens should be long, URL-safe, and unique per instance."""
        from app.models.proposal import Proposal

        p1 = Proposal(project_id="a" * 36)
        p2 = Proposal(project_id="a" * 36)
        assert p1.share_token != p2.share_token
        assert len(p1.share_token) >= 32

    def test_proposal_repr(self):
        """Proposal repr should include the id and project_id."""
        from app.models.proposal import Proposal

        proposal = Proposal(project_id="test-project-id")
        r = repr(proposal)
        assert "Proposal" in r
        assert "test-project-id" in r


# ── Proposal Create Route Tests ──────────────────────────────────────────────


class TestProposalCreateRoute:
    """Tests for POST /api/projects/{project_id}/proposals."""

    @pytest.mark.asyncio
    async def test_create_proposal_success(self, client):
        """Designer can create a proposal for their own project (201, share_token)."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.post(
            f"/api/projects/{project['id']}/proposals",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["project_id"] == project["id"]
        assert "id" in data
        assert "share_token" in data
        assert len(data["share_token"]) > 0
        assert "share_url" in data
        assert data["share_token"] in data["share_url"]

    @pytest.mark.asyncio
    async def test_create_proposal_unauthenticated(self, client):
        """Should return 401 without auth."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)

        resp = await client.post(f"/api/projects/{project['id']}/proposals")

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_proposal_not_owned_project(self, client):
        """Designer cannot create a proposal for a project they don't own (404)."""
        token_a = await _register_and_get_token(client, email="a@example.com")
        project_a = await _create_project(client, token_a)
        token_b = await _register_second_designer(client)

        resp = await client.post(
            f"/api/projects/{project_a['id']}/proposals",
            headers={"Authorization": f"Bearer {token_b}"},
        )

        assert resp.status_code == 404


# ── Public Proposal View Route Tests ─────────────────────────────────────────


class TestProposalPublicViewRoute:
    """Tests for GET /api/proposals/{share_token} (public, no auth)."""

    @pytest.mark.asyncio
    async def test_public_get_proposal_success(self, client):
        """Public GET with no auth header succeeds and returns products."""
        proposal, _, product = await _setup_proposal_with_product(client)

        resp = await client.get(f"/api/proposals/{proposal['share_token']}")

        assert resp.status_code == 200
        data = resp.json()
        assert data["project_name"] == "Test Project"
        assert data["client_name"] == "Test Client"
        assert len(data["products"]) == 1
        assert data["products"][0]["name"] == product["name"]
        assert data["products"][0]["client_price"] == 1800.00
        assert data["products"][0]["status"] == "proposed"

    @pytest.mark.asyncio
    async def test_public_get_proposal_no_auth_header_required(self, client):
        """The public GET works with no Authorization header whatsoever."""
        proposal, _, _ = await _setup_proposal_with_product(client)

        resp = await client.get(f"/api/proposals/{proposal['share_token']}")

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_public_get_proposal_unknown_token_returns_404(self, client):
        """Public GET with an unknown share_token returns 404."""
        resp = await client.get("/api/proposals/this-token-does-not-exist-at-all")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_public_get_proposal_never_exposes_trade_price(self, client):
        """The client-facing proposal view must never leak trade_price anywhere.

        trade_price is the designer's cost. A client should only ever see
        client_price, name, vendor, description, and status. This is the single
        most important guarantee in this slice — asserting the key is absent
        from the serialized product data under any spelling.
        """
        proposal, _, _ = await _setup_proposal_with_product(client)

        resp = await client.get(f"/api/proposals/{proposal['share_token']}")

        assert resp.status_code == 200
        body = resp.json()
        for product in body["products"]:
            # trade_price must never appear as a key in the serialized product.
            assert "trade_price" not in product, (
                "trade_price leaked to client-facing proposal view"
            )
            # No key under any spelling of "trade" should appear.
            trade_spelled_keys = [
                k for k in product if "trade" in k.lower()
            ]
            assert trade_spelled_keys == [], (
                f"trade-related keys leaked: {trade_spelled_keys}"
            )
            # The only fields a client should see.
            allowed_keys = {
                "id", "name", "vendor", "client_price",
                "description", "status",
            }
            assert set(product.keys()) == allowed_keys, (
                f"unexpected keys in public product view: {set(product.keys())}"
            )


# ── Public Proposal Approve Route Tests ──────────────────────────────────────


class TestProposalApproveRoute:
    """Tests for POST /api/proposals/{share_token}/products/{product_id}/approve."""

    @pytest.mark.asyncio
    async def test_public_approve_transitions_proposed_to_approved(self, client):
        """Public approve endpoint transitions a proposed product to approved (no auth)."""
        proposal, _, product = await _setup_proposal_with_product(client)

        resp = await client.post(
            f"/api/proposals/{proposal['share_token']}"
            f"/products/{product['id']}/approve"
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == product["id"]
        assert data["status"] == "approved"

    @pytest.mark.asyncio
    async def test_public_approve_rejects_already_approved(self, client):
        """Public approve rejects (422) approving an already-approved product."""
        proposal, _, product = await _setup_proposal_with_product(client)

        # First approval succeeds.
        first = await client.post(
            f"/api/proposals/{proposal['share_token']}"
            f"/products/{product['id']}/approve"
        )
        assert first.status_code == 200

        # Second approval should 422 — product is no longer 'proposed'.
        second = await client.post(
            f"/api/proposals/{proposal['share_token']}"
            f"/products/{product['id']}/approve"
        )
        assert second.status_code == 422

    @pytest.mark.asyncio
    async def test_public_approve_rejects_ordered_product(self, client):
        """Public approve rejects (422) a product that advanced past approved."""
        proposal, token, product = await _setup_proposal_with_product(client)

        # Advance the product past approved via the authenticated designer route.
        for next_status in ("approved", "ordered"):
            resp = await client.patch(
                f"/api/projects/{proposal['project_id']}/products/{product['id']}"
                f"/status",
                json={"status": next_status},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert resp.status_code == 200, f"Failed at {next_status}: {resp.text}"

        # Client tries to approve an already-ordered product — should 422.
        resp = await client.post(
            f"/api/proposals/{proposal['share_token']}"
            f"/products/{product['id']}/approve"
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_public_approve_unknown_share_token_404s(self, client):
        """Public approve 404s on an unknown share_token."""
        token = await _register_and_get_token(client)
        project = await _create_project(client, token)
        product = await _create_product(client, token, project["id"])

        resp = await client.post(
            f"/api/proposals/this-token-does-not-exist"
            f"/products/{product['id']}/approve"
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_public_approve_product_not_in_proposal_project_404s(self, client):
        """Public approve 404s when the product doesn't belong to the proposal's project."""
        proposal, _, _ = await _setup_proposal_with_product(client)

        # Create a *different* project + product owned by the same designer.
        token = await _register_and_get_token(
            client, email="another@example.com",
        )
        other_project = await _create_project(
            client, token, name="Other Project"
        )
        other_product = await _create_product(
            client, token, other_project["id"], name="Other Sofa"
        )

        # The share_token is valid, but the product_id belongs to a different
        # project than the proposal's — must 404, not approve it.
        resp = await client.post(
            f"/api/proposals/{proposal['share_token']}"
            f"/products/{other_product['id']}/approve"
        )

        assert resp.status_code == 404
