"""Project database model."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Project(Base):
    """A designer's project — the core organizing entity."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    designer_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("designers.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    client_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )
    template_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    designer: Mapped["Designer"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Designer", back_populates="projects"
    )
    clients: Mapped[list["Client"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Client", back_populates="project", cascade="all, delete-orphan"
    )
    products: Mapped[list["Product"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Product", back_populates="project", cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("status", "draft")
        kwargs.setdefault("created_at", datetime.now(UTC))
        kwargs.setdefault("updated_at", datetime.now(UTC))
        kwargs.setdefault("id", str(uuid.uuid4()))
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Project {self.name}>"
