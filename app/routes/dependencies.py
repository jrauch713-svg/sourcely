"""Shared route dependencies — designer authentication."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.designer import Designer
from app.services.auth import AuthService

security = HTTPBearer(auto_error=False)


async def get_current_designer(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Designer:
    """Dependency that extracts and validates the current designer from JWT.

    Raises 401 if not authenticated or token is invalid.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    payload = AuthService.decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )

    designer_id = payload["sub"]
    result = await db.execute(select(Designer).where(Designer.id == designer_id))
    designer = result.scalar_one_or_none()

    if designer is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Designer not found"
        )

    return designer
