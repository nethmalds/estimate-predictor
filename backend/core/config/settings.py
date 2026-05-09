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

	chroma_collection: str | None = field(default_factory=lambda: _optional_env("CHROMA_COLLECTION"))
	chroma_host: str | None = field(default_factory=lambda: _optional_env("CHROMA_HOST"))
	chroma_port: int | None = field(default_factory=lambda: _optional_int("CHROMA_PORT"))
	chroma_ssl: bool = field(default_factory=lambda: _optional_bool("CHROMA_SSL", default=False))
	chroma_api_key: str | None = field(default_factory=lambda: _optional_env("CHROMA_API_KEY"))

	embedding_model: str = field(default_factory=lambda: _required_env("EMBEDDING_MODEL"))
	retrieval_top_k: int = field(default_factory=lambda: _required_int("RETRIEVAL_TOP_K"))
	min_confidence_threshold: float = field(default_factory=lambda: _required_float("MIN_CONFIDENCE_THRESHOLD"))

	openrouter_api_key: str | None = field(default_factory=lambda: _optional_env("OPENROUTER_API_KEY"))
	openrouter_model: str | None = field(default_factory=lambda: _optional_env("OPENROUTER_MODEL"))

	cors_allow_origins: list[str] = field(default_factory=_cors_allow_origins)

	# Runtime environment — controls feature flags (e.g. diagnostic routes).
	# Set to "production" in deployed environments to disable dev-only surfaces.
	env: str = field(default_factory=lambda: _optional_env("ENV") or "development")

	# Secret key for signing backend-issued JWT access tokens.
	# Generate with: openssl rand -base64 32
	api_secret_key: str = field(
		default_factory=lambda: _optional_env("API_SECRET_KEY") or "dev-secret-change-in-production"
	)

	# Gmail SMTP configuration for password-reset email delivery.
	smtp_host: str = field(default_factory=lambda: _optional_env("SMTP_HOST") or "smtp.gmail.com")
	smtp_port: int = field(default_factory=lambda: int(_optional_env("SMTP_PORT") or "587"))
	smtp_username: str | None = field(default_factory=lambda: _optional_env("SMTP_USERNAME"))
	smtp_password: str | None = field(default_factory=lambda: _optional_env("SMTP_PASSWORD"))
	smtp_from_email: str | None = field(default_factory=lambda: _optional_env("SMTP_FROM_EMAIL"))
	smtp_from_name: str = field(default_factory=lambda: _optional_env("SMTP_FROM_NAME") or "CostEstimate AI")
	smtp_starttls: bool = field(default_factory=lambda: _optional_bool("SMTP_STARTTLS", default=True))
	smtp_ssl: bool = field(default_factory=lambda: _optional_bool("SMTP_SSL", default=False))
	frontend_app_url: str = field(
		default_factory=lambda: _optional_env("FRONTEND_APP_URL") or "http://localhost:3000"
	)

	# Sri Lankan BSR cost factors (configurable via .env.local)
	# preliminaries: covers site management, temporary works, bonds etc. (default 8%)
	# contingencies: allowance for unforeseen variations (default 5%)
	preliminaries_rate: float = field(
		default_factory=lambda: float(_optional_env("PRELIMINARIES_RATE") or "0.08")
	)
	contingencies_rate: float = field(
		default_factory=lambda: float(_optional_env("CONTINGENCIES_RATE") or "0.05")
	)


settings = DatabaseSettings()
