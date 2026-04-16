import os
from dataclasses import dataclass, field
from pathlib import Path

try:
	from dotenv import load_dotenv

	ROOT_DIR = Path(__file__).resolve().parents[2]
	load_dotenv(ROOT_DIR / ".env.local", override=False)
	load_dotenv(ROOT_DIR / ".env", override=False)
except Exception:
	pass


def _required_env(name: str) -> str:
	value = os.getenv(name)
	if value is None or value.strip() == "":
		raise ValueError(f"Missing required environment variable: {name}")
	return value


def _optional_env(name: str) -> str | None:
	value = os.getenv(name)
	if value is None or value.strip() == "":
		return None
	return value


def _required_int(name: str) -> int:
	return int(_required_env(name))


def _required_float(name: str) -> float:
	return float(_required_env(name))


def _optional_int(name: str) -> int | None:
	value = _optional_env(name)
	if value is None:
		return None
	return int(value)


def _optional_bool(name: str, default: bool = False) -> bool:
	value = _optional_env(name)
	if value is None:
		return default
	return value.lower() in {"1", "true", "yes", "on"}


def _optional_csv(name: str) -> list[str] | None:
	value = _optional_env(name)
	if value is None:
		return None
	items = [item.strip() for item in value.split(",")]
	return [item for item in items if item]


def _cors_allow_origins() -> list[str]:
	origins = _optional_csv("CORS_ALLOW_ORIGINS")
	if origins:
		return origins
	return ["http://localhost:3000"]


def _database_url() -> str:
	value = os.getenv("DATABASE_URL")
	if value and value.strip() != "":
		return value

	postgres_user = _required_env("POSTGRES_USER")
	postgres_password = _required_env("POSTGRES_PASSWORD")
	postgres_host = _required_env("POSTGRES_HOST")
	postgres_port = _required_env("POSTGRES_PORT")
	postgres_db = _required_env("POSTGRES_DB")

	return (
		f"postgresql://{postgres_user}:{postgres_password}"
		f"@{postgres_host}:{postgres_port}/{postgres_db}"
	)


@dataclass(frozen=True)
class DatabaseSettings:
	postgres_user: str = field(default_factory=lambda: _required_env("POSTGRES_USER"))
	postgres_password: str = field(default_factory=lambda: _required_env("POSTGRES_PASSWORD"))
	postgres_db: str = field(default_factory=lambda: _required_env("POSTGRES_DB"))
	postgres_host: str = field(default_factory=lambda: _required_env("POSTGRES_HOST"))
	postgres_port: int = field(default_factory=lambda: _required_int("POSTGRES_PORT"))

	database_url: str = field(default_factory=_database_url)

	chroma_collection: str = field(default_factory=lambda: _optional_env("CHROMA_COLLECTION"))
	chroma_host: str = field(default_factory=lambda: _optional_env("CHROMA_HOST"))
	chroma_port: int = field(default_factory=lambda: _optional_int("CHROMA_PORT"))
	chroma_ssl: bool = field(default_factory=lambda: _optional_bool("CHROMA_SSL", default=False))
	chroma_api_key: str | None = field(default_factory=lambda: _optional_env("CHROMA_API_KEY"))

	embedding_model: str = field(default_factory=lambda: _required_env("EMBEDDING_MODEL"))
	retrieval_top_k: int = field(default_factory=lambda: _required_int("RETRIEVAL_TOP_K"))
	min_confidence_threshold: float = field(default_factory=lambda: _required_float("MIN_CONFIDENCE_THRESHOLD"))

	log_level: str = field(default_factory=lambda: _optional_env("LOG_LEVEL") or "INFO")

	ollama_api_key: str | None = field(default_factory=lambda: _optional_env("OLLAMA_API_KEY"))
	ollama_host: str | None = field(default_factory=lambda: _optional_env("OLLAMA_HOST"))
	ollama_model: str | None = field(default_factory=lambda: _optional_env("OLLAMA_MODEL"))

	cors_allow_origins: list[str] = field(default_factory=_cors_allow_origins)


settings = DatabaseSettings()
