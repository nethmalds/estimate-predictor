from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from core.config.settings import settings


class Base(DeclarativeBase):
	pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
    pool_recycle=3600,
    pool_timeout=30,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db_session():
	db = SessionLocal()
	try:
		yield db
	except Exception:
		db.rollback()
		raise
	finally:
		db.close()
