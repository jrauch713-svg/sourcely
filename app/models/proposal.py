"""Proposal database model — a client-facing shareable view of a project's products."""

import uuid
from datetime import UTC, datetime
from secrets import token_urlsafe

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Proposal(Base):
    """A shareable, no-login proposal link for a client to view and approve products."""

    __tablename__ = "proposals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    share_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, default=lambda: token_urlsafe(32)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    project: Mapped["Project"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Project", back_populates="proposals"
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("share_token", token_urlsafe(32))
        kwargs.setdefault("created_at", datetime.now(UTC))
        kwargs.setdefault("id", str(uuid.uuid4()))
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Proposal {self.id} for project {self.project_id}>"
