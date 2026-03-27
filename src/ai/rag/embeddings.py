from functools import lru_cache

from src.config.database import settings


class EmbeddingProvider:
    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model
        self._model = self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers is required for embeddings. Install with: pip install sentence-transformers"
            ) from exc
        return SentenceTransformer(self.model_name)

    @staticmethod
    def build_embedding_text(item_no: str, description: str, category: str) -> str:
        return f"{item_no} {description} {category}".strip()

    @lru_cache(maxsize=50000)
    def embed_one(self, text: str) -> list[float]:
        return self._model.encode(text, normalize_embeddings=True).tolist()

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._model.encode(texts, normalize_embeddings=True)
        return vectors.tolist()
