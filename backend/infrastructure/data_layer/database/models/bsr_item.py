from sqlalchemy import Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.data_layer.database.session import Base


class BSRItem(Base):
    __tablename__ = "bsr_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_no: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)

    work_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    material_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    method: Mapped[str | None] = mapped_column(Text, nullable=True)
    constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("ix_bsr_items_item_no", "item_no"),
        Index("ix_bsr_items_category", "category"),
        Index("ix_bsr_items_work_type", "work_type"),
    )
