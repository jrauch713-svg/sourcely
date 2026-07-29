"""Authentication routes — register, login, JWT, user info."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.designer import Designer
from app.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


# ── Schemas ───────────────────────────────────────────────────────────────────


class RegisterRequest(BaseModel):
    """Request body for designer registration."""

    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


class LoginRequest(BaseModel):
    """Request body for designer login."""

    email: EmailStr
    password: str


class DesignerResponse(BaseModel):
    """Public designer data (never includes password hash)."""

    id: str
    email: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str = "bearer"
    user: DesignerResponse


# ── Dependencies ──────────────────────────────────────────────────────────────


async def get_current_designer(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> Designer:
    """Dependency that extracts and validates the current designer from JWT."""
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


# ── Routes ────────────────────────────────────────────────────────────────────


@router.post(
    "/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:  # noqa: B008
    """Register a new designer account."""
    # Check for duplicate email
    result = await db.execute(select(Designer).where(Designer.email == request.email))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A designer with this email already exists",
        )

    # Create designer
    designer = Designer(
        email=request.email,
        password_hash=AuthService.hash_password(request.password),
    )
    db.add(designer)
    await db.flush()

    # Generate token
    token = AuthService.create_access_token(
        data={"sub": designer.id, "email": designer.email}
    )

    return TokenResponse(
        access_token=token,
        user=DesignerResponse.model_validate(designer),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:  # noqa: B008
    """Login with email and password."""
    result = await db.execute(select(Designer).where(Designer.email == request.email))
    designer = result.scalar_one_or_none()

    if designer is None or not AuthService.verify_password(
        request.password, designer.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = AuthService.create_access_token(
        data={"sub": designer.id, "email": designer.email}
    )

    return TokenResponse(
        access_token=token,
        user=DesignerResponse.model_validate(designer),
    )


@router.get("/me", response_model=DesignerResponse)
async def me(designer: Designer = Depends(get_current_designer)) -> DesignerResponse:  # noqa: B008
    """Get the current authenticated designer's profile."""
    return DesignerResponse.model_validate(designer)
