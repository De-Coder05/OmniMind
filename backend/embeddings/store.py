import os
import uuid
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

# In-memory BM25 index per session: { session_id: {"bm25": BM25Okapi, "chunks": [...]} }
_bm25_indexes: Dict[str, Dict] = {}


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


def _tokenize(text: str) -> List[str]:
    return text.lower().split()


def _rebuild_bm25(session_id: str, chunks: List[Dict[str, Any]]):
    """(Re)build the BM25 index for a session from its chunks."""
    corpus = [_tokenize(c["text"]) for c in chunks]
    _bm25_indexes[session_id] = {
        "bm25": BM25Okapi(corpus) if corpus else None,
        "chunks": chunks,
    }


def add_chunks(session_id: str, chunks: List[Dict[str, Any]]) -> int:
    """Embed + store in ChromaDB, and index in BM25. Returns count added."""
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

    batch_size = 100
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i: i + batch_size],
            documents=documents[i: i + batch_size],
            metadatas=metadatas[i: i + batch_size],
        )

    # Update BM25 index
    existing = _bm25_indexes.get(session_id, {}).get("chunks", [])
    all_chunks = existing + [
        {"text": doc, "metadata": meta}
        for doc, meta in zip(documents, metadatas)
    ]
    _rebuild_bm25(session_id, all_chunks)

    return len(chunks)


def _semantic_search(session_id: str, query: str, n: int) -> List[Dict[str, Any]]:
    collection = get_or_create_collection(session_id)
    count = collection.count()
    if count == 0:
        return []
    n = min(n, count)
    results = collection.query(query_texts=[query], n_results=n)
    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        chunks.append({
            "text": doc,
            "metadata": meta,
            "score": round(1 - dist, 4),
        })
    return chunks


def _bm25_search(session_id: str, query: str, n: int) -> List[Dict[str, Any]]:
    idx = _bm25_indexes.get(session_id)
    if not idx or idx["bm25"] is None:
        return []
    tokens = _tokenize(query)
    scores = idx["bm25"].get_scores(tokens)
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
    results = []
    for i in top_indices:
        if scores[i] > 0:
            c = idx["chunks"][i]
            results.append({
                "text": c["text"],
                "metadata": c["metadata"],
                "score": round(float(scores[i]), 4),
                "bm25_rank": len(results) + 1,
            })
    return results


def _reciprocal_rank_fusion(
    semantic: List[Dict], bm25: List[Dict], k: int = 60, top_n: int = 8
) -> List[Dict[str, Any]]:
    """Combine semantic and BM25 results using Reciprocal Rank Fusion."""
    rrf_scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict] = {}

    for rank, c in enumerate(semantic, start=1):
        key = c["text"][:120]  # fingerprint
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank)
        chunk_map[key] = c

    for rank, c in enumerate(bm25, start=1):
        key = c["text"][:120]
        rrf_scores[key] = rrf_scores.get(key, 0) + 1 / (k + rank)
        if key not in chunk_map:
            chunk_map[key] = c

    ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    results = []
    for key, rrf_score in ranked:
        c = dict(chunk_map[key])
        c["score"] = round(rrf_score, 5)
        results.append(c)
    return results


def _get_unique_files(session_id: str) -> List[str]:
    """Return list of distinct source filenames in a session's BM25 index."""
    idx = _bm25_indexes.get(session_id)
    if not idx:
        return []
    files = list({c["metadata"].get("source", "") for c in idx["chunks"]})
    return [f for f in files if f]


def _fair_retrieval(
    fused: List[Dict[str, Any]],
    session_id: str,
    query: str,
    total: int,
) -> List[Dict[str, Any]]:
    """
    Ensure every indexed file gets at least MIN_SLOTS_PER_FILE chunks
    in the final result set. Fills gaps by fetching per-file if needed.
    """
    MIN_SLOTS = 2
    files = _get_unique_files(session_id)

    if len(files) <= 1:
        return fused  # single file — no fairness needed

    # Count how many chunks each file already has in fused results
    file_counts: Dict[str, int] = {f: 0 for f in files}
    for c in fused:
        src = c["metadata"].get("source", "")
        if src in file_counts:
            file_counts[src] += 1

    # Find files that are under-represented
    under = [f for f, cnt in file_counts.items() if cnt < MIN_SLOTS]
    if not under:
        return fused

    # For each under-represented file, fetch its best-matching chunks directly
    collection = get_or_create_collection(session_id)
    ef = _get_ef()
    import hashlib
    result = list(fused)
    existing_keys = {hashlib.md5(c["text"].encode()).hexdigest() for c in result}

    for filename in under:
        needed = MIN_SLOTS - file_counts[filename]
        try:
            # Query with a file-scoped where clause
            res = collection.query(
                query_texts=[query],
                n_results=min(needed + 2, 5),
                where={"source": filename},
            )
            for doc, meta, dist in zip(
                res["documents"][0],
                res["metadatas"][0],
                res["distances"][0],
            ):
                key = doc[:120]
                chunk_key = hashlib.md5(doc.encode()).hexdigest()
                if chunk_key not in existing_keys and needed > 0:
                    result.append({
                        "text": doc,
                        "metadata": meta,
                        "score": round(1 - dist, 4),
                    })
                    existing_keys.add(chunk_key)
                    needed -= 1
        except Exception:
            continue

    return result[:total]


def query_collection(session_id: str, query: str, n_results: int = 8) -> List[Dict[str, Any]]:
    """Hybrid retrieval: semantic + BM25 fused via RRF, with per-file fairness."""
    semantic = _semantic_search(session_id, query, n=n_results)
    bm25 = _bm25_search(session_id, query, n=n_results)

    fused = (
        _reciprocal_rank_fusion(semantic, bm25, top_n=n_results)
        if bm25
        else semantic
    )

    return _fair_retrieval(fused, session_id, query, total=min(n_results, 10))


def delete_collection(session_id: str):
    client = _get_client()
    try:
        client.delete_collection(f"session_{session_id}")
    except Exception:
        pass
    _bm25_indexes.pop(session_id, None)
