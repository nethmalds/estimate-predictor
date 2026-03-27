import threading

import chromadb
from chromadb.api import ClientAPI
from chromadb.api.models.Collection import Collection
from fastapi import Depends

from src.config.database import settings

_client: ClientAPI | None = None
_collection: Collection | None = None
_client_lock = threading.Lock()
_collection_lock = threading.Lock()


def _create_chroma_client() -> ClientAPI:
    headers = None
    if settings.chroma_api_key:
        headers = {"X-Chroma-Token": settings.chroma_api_key}

    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
        ssl=settings.chroma_ssl,
        headers=headers,
    )


def get_chroma_client() -> ClientAPI:
    global _client

    if _client is not None:
        return _client

    with _client_lock:
        if _client is None:
            _client = _create_chroma_client()

    return _client


def get_chroma_collection(client: ClientAPI | None = None) -> Collection:
    global _collection

    resolved_client = client or get_chroma_client()

    if _collection is not None:
        return _collection

    with _collection_lock:
        if _collection is None:
            _collection = resolved_client.get_or_create_collection(
                name=settings.chroma_collection,
                metadata={"hnsw:space": "cosine"},
            )

    return _collection


def get_chroma_collection_dependency(client: ClientAPI = Depends(get_chroma_client)) -> Collection:
    return get_chroma_collection(client)
