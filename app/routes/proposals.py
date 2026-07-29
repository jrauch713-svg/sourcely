"""Proposal routes — client-facing shareable proposal views and approvals."""

# SPDX-License-Identifier: MIT
# ruff: noqa: B008 — FastAPI Depends() in defaults is the standard idiom

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.designer import Designer
from app.models.product import Product, ProductStatus
from app.models.project import Project
from app.models.proposal import Proposal
from app.routes.dependencies import get_current_designer

router = APIRouter(tags=["proposals"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class ProposalCreateResponse(BaseModel):
    """Response for creating a proposal — includes the unguessable share token."""

    id: str
    project_id: str
    share_token: str
    share_url: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ProposalProductPublic(BaseModel):
    """A product as seen by a client — never includes the designer's trade_price."""

    id: str
    name: str
    vendor: str
    client_price: float
    description: str | None
    status: str

    model_config = {"from_attributes": True}


class ProposalViewResponse(BaseModel):
    """Public proposal view — what a client sees at the share link."""

    project_name: str
    client_name: str
    products: list[ProposalProductPublic]


class ProposalProductApprovalResponse(BaseModel):
    """Response after a client approves a single product."""

    id: str
    name: str
    status: str

    model_config = {"from_attributes": True}


# ── Helpers ────────────────────────────────────────────────────────────────────


async def _get_owned_project(
    project_id: str,
    designer: Designer,
    db: AsyncSession,
) -> Project:
    """Fetch a project owned by the given designer, 404 if not found."""
    result = await db.execute(
        select(Project).where(
            Project.id == project_id, Project.designer_id == designer.id
        )
    )
    project = result.scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return project


async def _get_proposal_by_token(share_token: str, db: AsyncSession) -> Proposal:
    """Fetch a proposal by share_token, 404 if not found."""
    result = await db.execute(
        select(Proposal).where(Proposal.share_token == share_token)
    )
    proposal = result.scalar_one_or_none()
    if proposal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proposal not found"
        )
    return proposal


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/api/projects/{project_id}/proposals",
    response_model=ProposalCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_proposal(  # noqa: B008
    project_id: str,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProposalCreateResponse:
    """Create a shareable proposal for one of the designer's projects."""
    await _get_owned_project(project_id, designer, db)

    proposal = Proposal(project_id=project_id)
    db.add(proposal)
    await db.flush()
    await db.refresh(proposal)
    return ProposalCreateResponse(
        id=proposal.id,
        project_id=proposal.project_id,
        share_token=proposal.share_token,
        share_url=f"/p/{proposal.share_token}",
        created_at=proposal.created_at,
    )


@router.get(
    "/api/proposals/{share_token}",
    response_model=ProposalViewResponse,
)
async def get_public_proposal(  # noqa: B008
    share_token: str,
    db: AsyncSession = Depends(get_db),
) -> ProposalViewResponse:
    """Public, no-auth view of a proposal — clients see product data minus trade_price."""
    proposal = await _get_proposal_by_token(share_token, db)

    # Stash sent_at the first time a proposal is viewed.
    if proposal.sent_at is None:
        proposal.sent_at = datetime.now(UTC)

    result = await db.execute(
        select(Project)
        .where(Project.id == proposal.project_id)
        .options(selectinload(Project.products))
    )
    project = result.scalar_one()
    products = sorted(project.products, key=lambda p: p.created_at)

    return ProposalViewResponse(
        project_name=project.name,
        client_name=project.client_name,
        products=[
            ProposalProductPublic.model_validate(p) for p in products
        ],
    )


@router.post(
    "/api/proposals/{share_token}/products/{product_id}/approve",
    response_model=ProposalProductApprovalResponse,
)
async def approve_proposal_product(  # noqa: B008
    share_token: str,
    product_id: str,
    db: AsyncSession = Depends(get_db),
) -> ProposalProductApprovalResponse:
    """Public, no-auth per-line-item approval — the share_token is the only gate.

    Transitions one product from `proposed` to `approved`. A client can only
    approve products that are still in `proposed` status; anything already
    approved or further along the pipeline is rejected with 422.
    """
    proposal = await _get_proposal_by_token(share_token, db)

    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.project_id == proposal.project_id
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )

    if product.status != ProductStatus.PROPOSED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Cannot approve a product that is not in 'proposed' status "
                f"(current: '{product.status.value}')."
            ),
        )

    try:
        product.validate_transition(ProductStatus.APPROVED)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    product.status = ProductStatus.APPROVED
    product.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(product)
    return ProposalProductApprovalResponse(
        id=product.id, name=product.name, status=product.status.value
    )
