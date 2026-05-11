"""SQLAlchemy Estimate model."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.data_layer.database.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Estimate(Base):
    __tablename__ = "estimates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="in_progress"
    )  # in_progress | completed | failed | cancelled

    # Raw wizard form input — used to power the project specification panel and regenerate.
    wizard_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Normalised pipeline input.
    project_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Live progress snapshot updated on every pipeline stage callback.
    progress: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Human-readable failure reason surfaced to the UI.
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Regeneration lineage — set when this estimate was created by regenerating another.
    regenerated_from_estimate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Timestamp set when the run was cancelled by the user.
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    grand_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    item_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted: Mapped[bool] = mapped_column(nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped["User"] = relationship("User", back_populates="estimates")
    source_estimate: Mapped["Estimate | None"] = relationship(
        "Estimate",
        foreign_keys=[regenerated_from_estimate_id],
        remote_side=[id],
        uselist=False,
    )
