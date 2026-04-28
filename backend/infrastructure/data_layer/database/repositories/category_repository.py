from typing import List, Optional
from sqlalchemy.orm import Session
from infrastructure.data_layer.database.models.category import Category
from infrastructure.data_layer.database.session import SessionLocal


class CategoryRepository:
    _cached_categories: List[Category] | None = None

    @classmethod
    def _fetch_all(cls, db: Session) -> List[Category]:
        return db.query(Category).order_by(Category.name).all()

    @classmethod
    def get_all(cls) -> List[Category]:
        """Fetch all active categories, utilizing an in-memory cache."""
        if cls._cached_categories is None:
            db = SessionLocal()
            try:
                cls._cached_categories = cls._fetch_all(db)
            finally:
                db.close()
        return cls._cached_categories

    @classmethod
    def get_by_code(cls, code: str) -> Optional[Category]:
        """Get a category by its internal code."""
        categories = cls.get_all()
        for cat in categories:
            if cat.code == code:
                return cat
        return None

    @classmethod
    def clear_cache(cls):
        """Clear the in-memory category cache."""
        cls._cached_categories = None

category_repository = CategoryRepository()
