import os
import uuid
import hashlib
import chromadb
from chromadb.utils import embedding_functions
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

CHROMA_PATH = os.getenv("CHROMA_DB_PATH", "./data/chroma_db")
EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-large-en-v1.5")

_client = None
_ef = None
_bm25_indexes: Dict[str, Dict] = {}


def _get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def _get_ef():
    global _ef
    if _ef is None:
        _ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    return _ef


def get_or_create_collection(session_id: str):
    return _get_client().get_or_create_collection(
        name=f"session_{session_id}",
        embedding_function=_get_ef(),
        metadata={"hnsw:space": "cosine"},
    )


def _tokenize(text: str) -> List[str]:
    return text.lower().split()


def _rebuild_bm25(session_id: str, chunks: List[Dict[str, Any]]):
    corpus = [_tokenize(c["text"]) for c in chunks]
    _bm25_indexes[session_id] = {
        "bm25": BM25Okapi(corpus) if corpus else None,
        "chunks": chunks,
    }


def add_chunks(session_id: str, chunks: List[Dict[str, Any]]) -> int:
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

    for i in range(0, len(ids), 100):
        collection.add(
            ids=ids[i:i + 100],
            documents=documents[i:i + 100],
            metadatas=metadatas[i:i + 100],
        )

    existing = _bm25_indexes.get(session_id, {}).get("chunks", [])
    _rebuild_bm25(session_id, existing + [{"text": d, "metadata": m} for d, m in zip(documents, metadatas)])
    return len(chunks)


def _semantic_search(session_id: str, query: str, n: int) -> List[Dict[str, Any]]:
    collection = get_or_create_collection(session_id)
    count = collection.count()
    if count == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(n, count))
    return [
        {"text": doc, "metadata": meta, "score": round(1 - dist, 4)}
        for doc, meta, dist in zip(
            results["documents"][0], results["metadatas"][0], results["distances"][0]
        )
    ]


def _bm25_search(session_id: str, query: str, n: int) -> List[Dict[str, Any]]:
    idx = _bm25_indexes.get(session_id)
    if not idx or idx["bm25"] is None:
        return []
    scores = idx["bm25"].get_scores(_tokenize(query))
    top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
    return [
        {"text": idx["chunks"][i]["text"], "metadata": idx["chunks"][i]["metadata"], "score": round(float(scores[i]), 4)}
        for i in top if scores[i] > 0
    ]


def _rrf(semantic: List[Dict], bm25: List[Dict], k: int = 60, top_n: int = 8) -> List[Dict[str, Any]]:
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict] = {}

    for rank, c in enumerate(semantic, start=1):
        key = c["text"][:120]
        scores[key] = scores.get(key, 0) + 1 / (k + rank)
        chunk_map[key] = c

    for rank, c in enumerate(bm25, start=1):
        key = c["text"][:120]
        scores[key] = scores.get(key, 0) + 1 / (k + rank)
        if key not in chunk_map:
            chunk_map[key] = c

    results = []
    for key, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]:
        c = dict(chunk_map[key])
        c["score"] = round(score, 5)
        results.append(c)
    return results


def _fair_retrieval(fused: List[Dict[str, Any]], session_id: str, query: str, total: int) -> List[Dict[str, Any]]:
    MIN_SLOTS = 2
    idx = _bm25_indexes.get(session_id)
    if not idx:
        return fused

    files = list({c["metadata"].get("source", "") for c in idx["chunks"] if c["metadata"].get("source")})
    if len(files) <= 1:
        return fused

    file_counts = {f: sum(1 for c in fused if c["metadata"].get("source") == f) for f in files}
    under = [f for f, cnt in file_counts.items() if cnt < MIN_SLOTS]
    if not under:
        return fused

    collection = get_or_create_collection(session_id)
    result = list(fused)
    seen = {hashlib.md5(c["text"].encode()).hexdigest() for c in result}

    for filename in under:
        needed = MIN_SLOTS - file_counts[filename]
        try:
            res = collection.query(query_texts=[query], n_results=min(needed + 2, 5), where={"source": filename})
            for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
                key = hashlib.md5(doc.encode()).hexdigest()
                if key not in seen and needed > 0:
                    result.append({"text": doc, "metadata": meta, "score": round(1 - dist, 4)})
                    seen.add(key)
                    needed -= 1
        except Exception:
            continue

    return result[:total]


def query_collection(session_id: str, query: str, n_results: int = 8) -> List[Dict[str, Any]]:
    semantic = _semantic_search(session_id, query, n=n_results)
    bm25 = _bm25_search(session_id, query, n=n_results)
    fused = _rrf(semantic, bm25, top_n=n_results) if bm25 else semantic
    return _fair_retrieval(fused, session_id, query, total=min(n_results, 10))


def delete_collection(session_id: str):
    try:
        _get_client().delete_collection(f"session_{session_id}")
    except Exception:
        pass
    _bm25_indexes.pop(session_id, None)
