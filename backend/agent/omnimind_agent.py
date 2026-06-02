import os
import httpx
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from backend.embeddings.store import query_collection

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3")
MAX_HISTORY_TURNS = 4  # keep last 4 user/assistant pairs in context


def _call_ollama(messages: List[Dict]) -> str:
    payload = {"model": LLM_MODEL, "messages": messages, "stream": False}
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _infer_doc_role(filename: str) -> str:
    """Heuristic: label a file as JD, Resume, or Document based on its name."""
    name = filename.lower()
    if any(k in name for k in ["jd", "job", "description", "position", "role", "hiring", "opening"]):
        return "JOB DESCRIPTION"
    if any(k in name for k in ["resume", "cv", "curriculum", "profile", "candidate"]):
        return "CANDIDATE RESUME"
    return "DOCUMENT"


def _build_context(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        src = c["metadata"].get("source", "unknown")
        page = c["metadata"].get("page", "?")
        modality = c["metadata"].get("modality", "text")
        role = _infer_doc_role(src)
        label = f"[{i+1}] {role}: {src}, p.{page} ({modality})"
        parts.append(f"{label}\n{c['text']}")
    return "\n\n---\n\n".join(parts)


_CONTEXT_PRONOUNS = {
    "those", "that", "it", "they", "them", "these", "this",
    "what about", "and the", "how about", "same", "above", "mentioned"
}


def rewrite_query(user_query: str, history: List[Dict[str, str]]) -> str:
    """
    Rewrite a potentially contextual/follow-up query into a fully
    self-contained search query using conversation history.
    Only calls the LLM when the query actually contains context-dependent words.
    """
    if not history:
        return user_query  # no history, nothing to resolve

    # Fast path: query is self-contained — skip LLM call entirely
    words = user_query.lower()
    needs_rewrite = any(p in words for p in _CONTEXT_PRONOUNS)
    if not needs_rewrite:
        return user_query

    # Build a compact summary of prior turns
    history_text = "\n".join([
        f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content'][:200]}"
        for m in history[-(MAX_HISTORY_TURNS * 2):]
    ])

    messages = [
        {
            "role": "system",
            "content": (
                "You rewrite follow-up questions into standalone search queries. "
                "Output ONLY the rewritten query — no explanation, no quotes, no punctuation at the end. "
                "If the question is already self-contained, return it unchanged."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Conversation so far:\n{history_text}\n\n"
                f"Follow-up question: {user_query}\n\n"
                "Rewrite this as a standalone search query that could be understood without the conversation context."
            ),
        },
    ]

    rewritten = _call_ollama(messages).strip().strip('"').strip("'")
    # Sanity check: if it ballooned or looks wrong, fall back
    if len(rewritten) > 200 or not rewritten:
        return user_query
    return rewritten


def _refine_query(user_query: str, first_chunks: List[Dict]) -> Optional[str]:
    """
    Lightweight heuristic second-search decision — no extra LLM call.
    Only do a second retrieval if the first pass returned fewer than 4 chunks
    OR the query contains comparison/contrast keywords that suggest multi-angle retrieval.
    """
    if not first_chunks or len(first_chunks) >= 6:
        return None  # plenty of results, skip second hop

    COMPARE_KEYWORDS = {"compare", "versus", "vs", "difference", "contrast",
                        "better", "worse", "gap", "missing", "lacks"}
    words = set(user_query.lower().split())
    if words & COMPARE_KEYWORDS:
        # Build a complementary query focusing on the other document
        sources = {c["metadata"].get("source", "") for c in first_chunks}
        if any("resume" in s.lower() or "cv" in s.lower() for s in sources):
            return f"job requirements {user_query}"
        return f"candidate skills {user_query}"

    return None


def _history_to_messages(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    Convert stored history to Ollama message format.
    - Keep last MAX_HISTORY_TURNS pairs
    - Truncate assistant messages to 300 chars so they don't overwhelm context
    """
    trimmed = []
    for m in history[-(MAX_HISTORY_TURNS * 2):]:
        if m["role"] == "assistant":
            # Keep first sentence + truncated remainder so model knows what was said
            # but can't just copy-paste it
            content = m["content"][:300].rsplit(" ", 1)[0] + "…" if len(m["content"]) > 300 else m["content"]
            trimmed.append({"role": "assistant", "content": content})
        else:
            trimmed.append({"role": "user", "content": m["content"]})
    return trimmed


def run_agent(
    session_id: str,
    user_query: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Conversational retrieve-then-read RAG:
    1. Rewrite contextual queries using history (for accurate retrieval)
    2. Search ChromaDB with the rewritten query
    3. Optionally do a second search with a refined angle
    4. Answer using retrieved context + conversation history
    """
    history = history or []

    # --- Query rewriting for retrieval ---
    retrieval_query = rewrite_query(user_query, history)

    # --- First retrieval ---
    first_chunks = query_collection(session_id, retrieval_query, n_results=10)

    # --- Optional second retrieval ---
    refined_query = _refine_query(retrieval_query, first_chunks)
    second_chunks: List[Dict] = []
    hops = 1
    if refined_query:
        second_chunks = query_collection(session_id, refined_query, n_results=6)
        hops = 2

    # Merge and deduplicate by text hash (not page — single-page docs
    # like a resume produce multiple chunks all tagged as "page 1")
    import hashlib
    all_chunks = first_chunks + second_chunks
    seen: set = set()
    unique_chunks: List[Dict] = []
    for c in all_chunks:
        key = hashlib.md5(c["text"].encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    if not unique_chunks:
        return {
            "answer": "I couldn't find relevant information in the uploaded documents.",
            "sources": [],
            "hops": hops,
        }

    context = _build_context(unique_chunks)

    # --- Build messages: system + history + grounded question ---
    system_msg = (
        "You are a precise document analyst with memory of the conversation. "
        "Each excerpt is labeled with its document type (JOB DESCRIPTION, CANDIDATE RESUME, or DOCUMENT). "
        "CRITICAL RULES:\n"
        "1. Never confuse what a JOB DESCRIPTION requires with what a CANDIDATE RESUME demonstrates.\n"
        "2. Only attribute a skill to the candidate if a CANDIDATE RESUME excerpt explicitly states it.\n"
        "3. Only attribute a requirement to the job if a JOB DESCRIPTION excerpt explicitly states it.\n"
        "4. Cite every claim with its excerpt number [1], [2], etc.\n"
        "5. If an excerpt does not contain the answer, say so — do not infer or hallucinate.\n"
        "6. Use conversation history only to understand what 'those', 'that', 'it' refers to — not as a source of facts.\n"
        "7. When asked to compare, explicitly list matches and gaps side-by-side using what JOB DESCRIPTION excerpts require vs what CANDIDATE RESUME excerpts show."
    )

    history_messages = _history_to_messages(history)

    # Inject the document context as the final user turn
    grounded_question = (
        f"DOCUMENT EXCERPTS:\n\n{context}\n\n"
        f"---\n\n"
        f"Question: {user_query}\n\n"
        "Answer using only the excerpts above. Cite with [1], [2], etc."
    )

    messages = (
        [{"role": "system", "content": system_msg}]
        + history_messages
        + [{"role": "user", "content": grounded_question}]
    )

    answer = _call_ollama(messages)

    return {
        "answer": answer,
        "sources": unique_chunks,
        "hops": hops,
    }
