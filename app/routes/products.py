"""Product CRUD routes — procurement items within a project."""

# SPDX-License-Identifier: MIT
# ruff: noqa: B008 — FastAPI Depends() in defaults is the standard idiom

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.designer import Designer
from app.models.product import Product, ProductStatus
from app.models.project import Project
from app.routes.dependencies import get_current_designer

router = APIRouter(prefix="/api/projects", tags=["products"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class ProductCreate(BaseModel):
    """Request body for creating a product."""

    name: str
    vendor: str
    trade_price: float
    client_price: float
    notes: str | None = None
    description: str | None = None


class ProductUpdate(BaseModel):
    """Request body for updating a product (all fields optional)."""

    name: str | None = None
    vendor: str | None = None
    trade_price: float | None = None
    client_price: float | None = None
    notes: str | None = None
    description: str | None = None


class ProductResponse(BaseModel):
    """Public product data."""

    id: str
    project_id: str
    name: str
    vendor: str
    trade_price: float
    client_price: float
    status: str
    notes: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StatusTransitionRequest(BaseModel):
    """Request body for a status transition."""

    status: str


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


async def _get_product_in_project(
    project_id: str,
    product_id: str,
    designer: Designer,
    db: AsyncSession,
) -> Product:
    """Fetch a product that belongs to a project owned by the designer."""
    await _get_owned_project(project_id, designer, db)
    result = await db.execute(
        select(Product).where(
            Product.id == product_id, Product.project_id == project_id
        )
    )
    product = result.scalar_one_or_none()
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Product not found"
        )
    return product


def _parse_status(status_str: str) -> ProductStatus:
    """Parse a status string to a ProductStatus enum, 422 on invalid."""
    try:
        return ProductStatus(status_str)
    except ValueError:
        raise HTTPException(  # noqa: B904 — intentional re-raise as HTTPException
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"'{status_str}' is not a valid product status",
        )


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/{project_id}/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product(  # noqa: B008
    project_id: str,
    request: ProductCreate,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Create a new product within a project."""
    await _get_owned_project(project_id, designer, db)

    product = Product(
        project_id=project_id,
        name=request.name,
        vendor=request.vendor,
        trade_price=request.trade_price,
        client_price=request.client_price,
        notes=request.notes,
        description=request.description,
    )
    db.add(product)
    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


@router.get("/{project_id}/products", response_model=list[ProductResponse])
async def list_products(  # noqa: B008
    project_id: str,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> list[ProductResponse]:
    """List all products in a project."""
    await _get_owned_project(project_id, designer, db)
    result = await db.execute(
        select(Product)
        .where(Product.project_id == project_id)
        .order_by(Product.created_at)
    )
    products = result.scalars().all()
    return [ProductResponse.model_validate(p) for p in products]


@router.get("/{project_id}/products/{product_id}", response_model=ProductResponse)
async def get_product(  # noqa: B008
    project_id: str,
    product_id: str,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Get a single product by ID within a project."""
    product = await _get_product_in_project(project_id, product_id, designer, db)
    return ProductResponse.model_validate(product)


@router.put("/{project_id}/products/{product_id}", response_model=ProductResponse)
async def update_product(  # noqa: B008
    project_id: str,
    product_id: str,
    request: ProductUpdate,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Update a product (name, vendor, prices, notes, description)."""
    product = await _get_product_in_project(project_id, product_id, designer, db)

    if request.name is not None:
        product.name = request.name
    if request.vendor is not None:
        product.vendor = request.vendor
    if request.trade_price is not None:
        product.trade_price = request.trade_price
    if request.client_price is not None:
        product.client_price = request.client_price
    if request.notes is not None:
        product.notes = request.notes
    if request.description is not None:
        product.description = request.description
    product.updated_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(product)


@router.delete(
    "/{project_id}/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_product(  # noqa: B008
    project_id: str,
    product_id: str,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a product from a project."""
    product = await _get_product_in_project(project_id, product_id, designer, db)
    await db.delete(product)
    await db.flush()


@router.patch(
    "/{project_id}/products/{product_id}/status",
    response_model=ProductResponse,
)
async def transition_product_status(  # noqa: B008
    project_id: str,
    product_id: str,
    request: StatusTransitionRequest,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProductResponse:
    """Transition a product's status forward through the procurement pipeline.

    Valid statuses (in order): proposed → approved → ordered → shipped
    → received → installed. Skipping steps or moving backward is rejected
    with HTTP 422.
    """
    product = await _get_product_in_project(project_id, product_id, designer, db)
    target_status = _parse_status(request.status)

    if target_status != product.status:
        try:
            product.validate_transition(target_status)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

    product.status = target_status
    product.updated_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(product)
    return ProductResponse.model_validate(product)
