import os
import uuid
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-large-en-v1.5")

_client = None
_ef = None


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def _get_ef():
    global _ef
    if _ef is None:
        _ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )
    return _ef


def get_or_create_collection(session_id: str):
    client = _get_client()
    ef = _get_ef()
    return client.get_or_create_collection(
        name=f"session_{session_id}",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(session_id: str, chunks: List[Dict[str, Any]]) -> int:
    """Embed and store chunks in the session collection. Returns count added."""
    if not chunks:
        return 0

    collection = get_or_create_collection(session_id)

    ids = [str(uuid.uuid4()) for _ in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "modality": c.get("modality", "text"),
            "source": c.get("source", ""),
            "page": str(c.get("page", 1)),
            "type": c.get("type", ""),
        }
        for c in chunks
    ]

    # ChromaDB handles batching internally but we batch manually for safety
    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i: i + batch_size],
            documents=documents[i: i + batch_size],
            metadatas=metadatas[i: i + batch_size],
        )

    return len(chunks)


def query_collection(session_id: str, query: str, n_results: int = 8) -> List[Dict[str, Any]]:
    """Retrieve top-n semantically similar chunks for a query."""
    collection = get_or_create_collection(session_id)
    count = collection.count()
    if count == 0:
        return []

    n_results = min(n_results, count)
    results = collection.query(query_texts=[query], n_results=n_results)

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "metadata": meta,
            "score": round(1 - dist, 4),  # cosine similarity
        })

    return chunks


def delete_collection(session_id: str):
    client = _get_client()
    try:
        client.delete_collection(f"session_{session_id}")
    except Exception:
        pass
