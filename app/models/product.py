"""Product database model — belongs to a project, has procurement status."""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ProductStatus(str, enum.Enum):
    """Valid statuses for a product item in the procurement workflow.

    Transitions MUST proceed forward through the pipeline in order.
    """

    PROPOSED = "proposed"
    APPROVED = "approved"
    ORDERED = "ordered"
    SHIPPED = "shipped"
    RECEIVED = "received"
    INSTALLED = "installed"


# Ordered list for transition validation — index is the step number.
_ORDERED_STATUSES = list(ProductStatus)


class Product(Base):
    """A product item within a designer's project — the procurement unit."""

    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    vendor: Mapped[str] = mapped_column(String(255), nullable=False)
    trade_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    client_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[ProductStatus] = mapped_column(
        String(20),
        default=ProductStatus.PROPOSED,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    project: Mapped["Project"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Project", back_populates="products"
    )

    def __init__(self, **kwargs: object) -> None:
        kwargs.setdefault("status", ProductStatus.PROPOSED)
        kwargs.setdefault("created_at", datetime.now(UTC))
        kwargs.setdefault("updated_at", datetime.now(UTC))
        kwargs.setdefault("id", str(uuid.uuid4()))
        super().__init__(**kwargs)

    def __repr__(self) -> str:
        return f"<Product {self.name} [{self.status.value}]>"

    def validate_transition(self, target: ProductStatus) -> None:
        """Check that a status transition is valid (forward-only, no skips).

        Raises ValueError if the transition is not allowed.
        """
        # Coerce current status to the enum (DB may store it as a str).
        if isinstance(self.status, ProductStatus):
            current = self.status
        else:
            current = ProductStatus(str(self.status))

        if current == target:
            return  # Idempotent — setting same status is always OK.

        current_idx = _ORDERED_STATUSES.index(current)
        target_idx = _ORDERED_STATUSES.index(target)

        if target_idx <= current_idx:
            raise ValueError(
                f"Cannot move status from '{current.value}' "
                f"to '{target.value}' — backward or same (idempotent has "
                f"already been handled)."
            )

        if target_idx != current_idx + 1:
            raise ValueError(
                f"Cannot move status from '{current.value}' "
                f"to '{target.value}' — must advance one step at a time "
                f"(next valid: '{_ORDERED_STATUSES[current_idx + 1].value}')."
            )
