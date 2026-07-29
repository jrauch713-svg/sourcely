"""Project CRUD routes — designer-scoped project management."""

# SPDX-License-Identifier: MIT
# ruff: noqa: B008 — FastAPI Depends() in defaults is the standard idiom

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.designer import Designer
from app.models.project import Project
from app.routes.dependencies import get_current_designer

router = APIRouter(prefix="/api/projects", tags=["projects"])


# ── Schemas ───────────────────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    """Request body for creating a project."""

    name: str
    client_name: str
    template_type: str | None = None


class ProjectUpdate(BaseModel):
    """Request body for updating a project."""

    name: str | None = None
    client_name: str | None = None
    template_type: str | None = None


class ProjectResponse(BaseModel):
    """Public project data."""

    id: str
    name: str
    client_name: str
    status: str
    template_type: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Helper ─────────────────────────────────────────────────────────────────────


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


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(  # noqa: B008
    request: ProjectCreate,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Create a new project for the authenticated designer."""
    project = Project(
        designer_id=designer.id,
        name=request.name,
        client_name=request.client_name,
        template_type=request.template_type,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(  # noqa: B008
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    """List all projects for the authenticated designer."""
    result = await db.execute(
        select(Project)
        .where(Project.designer_id == designer.id)
        .order_by(Project.created_at.desc())
    )
    projects = result.scalars().all()
    return [ProjectResponse.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(  # noqa: B008
    project_id: str,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Get a single project by ID (scoped to the designer)."""
    project = await _get_owned_project(project_id, designer, db)
    return ProjectResponse.model_validate(project)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(  # noqa: B008
    project_id: str,
    request: ProjectUpdate,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    """Update a project (scoped to the designer)."""
    project = await _get_owned_project(project_id, designer, db)

    if request.name is not None:
        project.name = request.name
    if request.client_name is not None:
        project.client_name = request.client_name
    if request.template_type is not None:
        project.template_type = request.template_type
    project.updated_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(project)
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(  # noqa: B008
    project_id: str,
    designer: Designer = Depends(get_current_designer),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a project (scoped to the designer)."""
    project = await _get_owned_project(project_id, designer, db)
    await db.delete(project)
    await db.flush()
