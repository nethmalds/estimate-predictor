from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.data.main_db.models.bsr_item import BSRItem
 


def init_db() -> None:
    """Initialize database schema.

    Uses Alembic migrations (preferred) so schema can evolve safely.
    """

    try:
        from alembic import command
        from alembic.config import Config
    except ImportError as exc:
        raise ImportError(
            "Alembic is required for DB migrations. Install with: pip install alembic"
        ) from exc

    # Resolve repo root (…/codebase) and load alembic.ini from there.
    root_dir = Path(__file__).resolve().parents[3]
    alembic_ini = root_dir / "alembic.ini"
    if not alembic_ini.exists():
        raise FileNotFoundError(f"Missing alembic.ini at: {alembic_ini}")

    alembic_cfg = Config(str(alembic_ini))
    command.upgrade(alembic_cfg, "head")


def upsert_bsr_items(session: Session, items: Iterable[dict]) -> list[BSRItem]:
    persisted: list[BSRItem] = []

    for item in items:
        existing = session.scalar(select(BSRItem).where(BSRItem.item_no == item["item_no"]))
        if existing:
            existing.description = item["description"]
            existing.unit = item["unit"]
            existing.rate = float(item["rate"])
            existing.category = item["category"]
            existing.work_type = item.get("work_type")
            existing.material_type = item.get("material_type")
            existing.method = item.get("method")
            existing.constraints = item.get("constraints")
            existing.metadata_json = item.get("metadata")
            persisted.append(existing)
            continue

        created = BSRItem(
            item_no=item["item_no"],
            description=item["description"],
            unit=item["unit"],
            rate=float(item["rate"]),
            category=item["category"],
            work_type=item.get("work_type"),
            material_type=item.get("material_type"),
            method=item.get("method"),
            constraints=item.get("constraints"),
            metadata_json=item.get("metadata"),
        )
        session.add(created)
        persisted.append(created)

    session.commit()

    for record in persisted:
        session.refresh(record)

    return persisted


def get_bsr_items_by_ids(session: Session, ids: list[int]) -> list[BSRItem]:
    if not ids:
        return []
    rows = session.scalars(select(BSRItem).where(BSRItem.id.in_(ids))).all()
    row_map = {row.id: row for row in rows}
    return [row_map[item_id] for item_id in ids if item_id in row_map]


def get_all_bsr_items(session: Session) -> list[BSRItem]:
    return session.scalars(select(BSRItem)).all()
