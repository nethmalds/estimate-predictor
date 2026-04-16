from infrastructure.data_layer.vector_db.chroma_connection import get_chroma_collection


class ChromaBSRVectorStore:
    def __init__(self, persist_path: str | None = None, collection_name: str | None = None):
        self.collection = get_chroma_collection()

    def upsert(self, records: list[dict], embeddings: list[list[float]]) -> None:
        if not records:
            return

        self.collection.upsert(
            ids=[str(record["postgres_id"]) for record in records],
            embeddings=embeddings,
            metadatas=[
                {
                    "postgres_id": record["postgres_id"],
                    "item_no": record["item_no"],
                    "category": record["category"],
                    "work_type": record.get("work_type") or "",
                }
                for record in records
            ],
        )

    def query(self, embedding: list[float], top_k: int = 5, where: dict | None = None) -> list[dict]:
        results = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where=where,
            include=["metadatas", "distances"],
        )

        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        payload: list[dict] = []
        for meta, dist in zip(metadatas, distances):
            similarity = max(0.0, 1.0 - float(dist))
            payload.append(
                {
                    "postgres_id": int(meta["postgres_id"]),
                    "item_no": meta.get("item_no", ""),
                    "category": meta.get("category", ""),
                    "work_type": meta.get("work_type", ""),
                    "vector_score": similarity,
                }
            )
        return payload
