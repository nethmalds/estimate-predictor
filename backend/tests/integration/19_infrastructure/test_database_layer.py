"""Integration tests for the database layer.

Tests run against a real (SQLite in-memory) database so they are fast
and require no running Postgres instance.  SQLite is close enough to
PostgreSQL for all patterns exercised here (ORM CRUD, session lifecycle,
transaction rollback, constraint enforcement).

The schema is created via raw DDL so that PostgreSQL-specific column types
(e.g. JSONB) are replaced with SQLite-compatible equivalents.  All ORM
operations themselves use the production models unchanged.

Run with:
    pytest tests/integration/test_database_layer.py -v
"""
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from infrastructure.data_layer.database.models.bsr_item import BSRItem  # noqa: E402
from infrastructure.data_layer.database.models.category import Category  # noqa: E402
from services.rag_process.db import (  # noqa: E402
    get_all_bsr_items,
    get_bsr_items_by_ids,
    upsert_bsr_items,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """SQLite in-memory engine.

    Schema is created with raw DDL to avoid JSONB incompatibility; the ORM
    models are used as-is for all data operations.
    """
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    with eng.connect() as conn:
        conn.execute(text("""
            CREATE TABLE bsr_items (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                item_no       TEXT        NOT NULL UNIQUE,
                description   TEXT        NOT NULL,
                unit          VARCHAR(50) NOT NULL,
                rate          REAL        NOT NULL,
                category      TEXT        NOT NULL,
                work_type     TEXT,
                material_type TEXT,
                method        TEXT,
                constraints   TEXT,
                metadata      TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code        VARCHAR(100) NOT NULL UNIQUE,
                name        VARCHAR(200) NOT NULL,
                description TEXT
            )
        """))
        conn.execute(text("CREATE INDEX ix_bsr_items_item_no   ON bsr_items (item_no)"))
        conn.execute(text("CREATE INDEX ix_bsr_items_category  ON bsr_items (category)"))
        conn.execute(text("CREATE INDEX ix_bsr_items_work_type ON bsr_items (work_type)"))
        conn.commit()

    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Per-test session isolated by wrapping everything in a transaction that
    is always rolled back, even when the test itself calls session.commit().
    The session uses 'create_savepoint' mode so each commit becomes a
    SAVEPOINT release rather than a real commit on the connection.
    """
    connection = engine.connect()
    trans = connection.begin()
    # bind= is deprecated for Engine but remains supported for Connection in
    # the standard SQLAlchemy "join external transaction" testing recipe.
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield session
    session.close()
    trans.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _bsr_row(**overrides) -> dict:
    base = {
        "item_no": "TEST-001",
        "description": "Excavation in ordinary soil",
        "unit": "m3",
        "rate": 1250.0,
        "category": "Earthwork",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Schema sanity
# ---------------------------------------------------------------------------

class TestSchemaSanity:
    def test_bsr_items_table_exists(self, engine):
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='bsr_items'")
            ).fetchone()
        assert row is not None, "Table 'bsr_items' not found"

    def test_categories_table_exists(self, engine):
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='categories'")
            ).fetchone()
        assert row is not None, "Table 'categories' not found"

    def test_bsr_item_nullable_metadata_defaults_to_none(self, db):
        item = BSRItem(item_no="SCHEMA-001", description="Test", unit="m2", rate=100.0, category="Test")
        db.add(item)
        db.flush()
        assert item.id is not None
        assert item.metadata_json is None


# ---------------------------------------------------------------------------
# 2. upsert_bsr_items — insert path
# ---------------------------------------------------------------------------

class TestUpsertInsert:
    def test_insert_single_item(self, db):
        persisted = upsert_bsr_items(db, [_bsr_row()])
        db.commit()
        for item in persisted:
            db.refresh(item)

        assert len(persisted) == 1
        assert persisted[0].item_no == "TEST-001"
        assert persisted[0].id is not None

    def test_insert_sets_optional_fields(self, db):
        persisted = upsert_bsr_items(db, [_bsr_row(
            item_no="TEST-002",
            work_type="Excavation",
            material_type="Ordinary soil",
            method="Manual",
            constraints="Depth < 1.5m",
            metadata={"source": "BSR2025"},
        )])
        db.commit()
        for item in persisted:
            db.refresh(item)

        item = persisted[0]
        assert item.work_type == "Excavation"
        assert item.material_type == "Ordinary soil"
        assert item.metadata_json == {"source": "BSR2025"}

    def test_insert_multiple_items(self, db):
        rows = [_bsr_row(item_no=f"BULK-{i:03d}") for i in range(5)]
        persisted = upsert_bsr_items(db, rows)
        db.commit()
        for item in persisted:
            db.refresh(item)

        assert len(persisted) == 5
        assert {item.item_no for item in persisted} == {f"BULK-{i:03d}" for i in range(5)}


# ---------------------------------------------------------------------------
# 3. upsert_bsr_items — update (idempotency)
# ---------------------------------------------------------------------------

class TestUpsertUpdate:
    def test_update_existing_item(self, db):
        upsert_bsr_items(db, [_bsr_row(item_no="UPD-001", rate=1000.0)])
        db.commit()

        persisted = upsert_bsr_items(db, [_bsr_row(item_no="UPD-001", rate=1500.0)])
        db.commit()
        for item in persisted:
            db.refresh(item)

        assert persisted[0].rate == 1500.0

    def test_upsert_does_not_duplicate_row(self, db):
        upsert_bsr_items(db, [_bsr_row(item_no="NODUP-001")])
        db.commit()
        upsert_bsr_items(db, [_bsr_row(item_no="NODUP-001", description="Updated")])
        db.commit()

        count = db.execute(
            select(func.count()).select_from(BSRItem).where(BSRItem.item_no == "NODUP-001")
        ).scalar()
        assert count == 1


# ---------------------------------------------------------------------------
# 4. get_bsr_items_by_ids
# ---------------------------------------------------------------------------

class TestGetByIds:
    def test_returns_items_in_requested_order(self, db):
        rows = [_bsr_row(item_no=f"GI-{i:03d}") for i in range(3)]
        persisted = upsert_bsr_items(db, rows)
        db.commit()
        for item in persisted:
            db.refresh(item)

        ids = [item.id for item in persisted]
        result = get_bsr_items_by_ids(db, list(reversed(ids)))
        assert [r.id for r in result] == list(reversed(ids))

    def test_empty_input_returns_empty_list(self, db):
        assert get_bsr_items_by_ids(db, []) == []

    def test_nonexistent_id_is_skipped(self, db):
        assert get_bsr_items_by_ids(db, [999_999]) == []


# ---------------------------------------------------------------------------
# 5. get_all_bsr_items
# ---------------------------------------------------------------------------

class TestGetAll:
    def test_returns_inserted_items(self, db):
        rows = [_bsr_row(item_no=f"ALL-{i:03d}") for i in range(4)]
        upsert_bsr_items(db, rows)
        db.commit()

        all_items = get_all_bsr_items(db)
        all_item_nos = {item.item_no for item in all_items}
        for i in range(4):
            assert f"ALL-{i:03d}" in all_item_nos


# ---------------------------------------------------------------------------
# 6. Session lifecycle — rollback semantics
# ---------------------------------------------------------------------------

class TestSessionLifecycle:
    def test_flush_without_commit_does_not_persist(self, engine):
        """A flushed-but-rolled-back insert is invisible to a new session."""
        _Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

        with _Session() as sess:
            sess.add(BSRItem(item_no="ROLLBACK-001", description="x", unit="m2", rate=1.0, category="Test"))
            sess.flush()
            sess.rollback()

        with _Session() as sess2:
            found = sess2.scalar(select(BSRItem).where(BSRItem.item_no == "ROLLBACK-001"))
        assert found is None

    def test_exception_path_rolls_back(self, engine):
        """Simulates what get_db_session does: rollback on exception, close in finally."""
        _Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        item_no = "EXC-ROLLBACK-001"

        sess = _Session()
        try:
            sess.add(BSRItem(item_no=item_no, description="x", unit="m2", rate=1.0, category="Test"))
            sess.flush()
            raise RuntimeError("Simulated route-handler exception")
        except RuntimeError:
            sess.rollback()
        finally:
            sess.close()

        with _Session() as sess2:
            found = sess2.scalar(select(BSRItem).where(BSRItem.item_no == item_no))
        assert found is None


# ---------------------------------------------------------------------------
# 7. Category model
# ---------------------------------------------------------------------------

class TestCategoryModel:
    def test_category_insert(self, db):
        cat = Category(code="EW", name="Earthwork")
        db.add(cat)
        db.flush()
        assert cat.id is not None

    def test_unique_code_constraint(self, db):
        db.add(Category(code="UNIQ", name="First"))
        db.flush()
        db.add(Category(code="UNIQ", name="Duplicate"))
        with pytest.raises(IntegrityError):
            db.flush()

