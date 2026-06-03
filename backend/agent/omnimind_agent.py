import os
import hashlib
import httpx
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from backend.embeddings.store import query_collection

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3")
MAX_HISTORY_TURNS = 4

CONTEXT_PRONOUNS = {
    "those", "that", "it", "they", "them", "these", "this",
    "what about", "and the", "how about", "same", "above", "mentioned"
}

SYSTEM_PROMPT = (
    "You are a precise document analyst with memory of the conversation. "
    "Each excerpt is labeled with its document type (JOB DESCRIPTION, CANDIDATE RESUME, or DOCUMENT). "
    "CRITICAL RULES:\n"
    "1. Never confuse what a JOB DESCRIPTION requires with what a CANDIDATE RESUME demonstrates.\n"
    "2. Only attribute a skill to the candidate if a CANDIDATE RESUME excerpt explicitly states it.\n"
    "3. Only attribute a requirement to the job if a JOB DESCRIPTION excerpt explicitly states it.\n"
    "4. Cite every claim with its excerpt number [1], [2], etc.\n"
    "5. If an excerpt does not contain the answer, say so — do not infer or hallucinate.\n"
    "6. Use conversation history only to understand what 'those', 'that', 'it' refers to — not as a source of facts.\n"
    "7. When asked to compare, explicitly list matches and gaps side-by-side."
)


def _call_ollama(messages: List[Dict]) -> str:
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat",
        json={"model": LLM_MODEL, "messages": messages, "stream": False},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _infer_doc_role(filename: str) -> str:
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
        label = f"[{i+1}] {_infer_doc_role(src)}: {src}, p.{page} ({modality})"
        parts.append(f"{label}\n{c['text']}")
    return "\n\n---\n\n".join(parts)


def _build_history_messages(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    result = []
    for m in history[-(MAX_HISTORY_TURNS * 2):]:
        if m["role"] == "assistant":
            content = m["content"][:300].rsplit(" ", 1)[0] + "…" if len(m["content"]) > 300 else m["content"]
            result.append({"role": "assistant", "content": content})
        else:
            result.append({"role": "user", "content": m["content"]})
    return result


def rewrite_query(user_query: str, history: List[Dict[str, str]]) -> str:
    if not history:
        return user_query

    words = user_query.lower()
    if not any(p in words for p in CONTEXT_PRONOUNS):
        return user_query

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
            "content": f"Conversation so far:\n{history_text}\n\nFollow-up question: {user_query}\n\nRewrite as a standalone search query.",
        },
    ]

    rewritten = _call_ollama(messages).strip().strip('"').strip("'")
    return rewritten if rewritten and len(rewritten) <= 200 else user_query


def _refine_query(user_query: str, first_chunks: List[Dict]) -> Optional[str]:
    if not first_chunks or len(first_chunks) >= 6:
        return None

    compare_keywords = {"compare", "versus", "vs", "difference", "contrast", "better", "worse", "gap", "missing", "lacks"}
    if set(user_query.lower().split()) & compare_keywords:
        sources = {c["metadata"].get("source", "") for c in first_chunks}
        if any("resume" in s.lower() or "cv" in s.lower() for s in sources):
            return f"job requirements {user_query}"
        return f"candidate skills {user_query}"

    return None


def run_agent(session_id: str, user_query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    history = history or []
    retrieval_query = rewrite_query(user_query, history)

    first_chunks = query_collection(session_id, retrieval_query, n_results=10)
    refined = _refine_query(retrieval_query, first_chunks)
    second_chunks: List[Dict] = []
    hops = 1

    if refined:
        second_chunks = query_collection(session_id, refined, n_results=6)
        hops = 2

    seen: set = set()
    unique_chunks: List[Dict] = []
    for c in first_chunks + second_chunks:
        key = hashlib.md5(c["text"].encode()).hexdigest()
        if key not in seen:
            seen.add(key)
            unique_chunks.append(c)

    if not unique_chunks:
        return {"answer": "I couldn't find relevant information in the uploaded documents.", "sources": [], "hops": hops}

    context = _build_context(unique_chunks)
    grounded_question = f"DOCUMENT EXCERPTS:\n\n{context}\n\n---\n\nQuestion: {user_query}\n\nAnswer using only the excerpts above. Cite with [1], [2], etc."

    messages = (
        [{"role": "system", "content": SYSTEM_PROMPT}]
        + _build_history_messages(history)
        + [{"role": "user", "content": grounded_question}]
    )

    return {
        "answer": _call_ollama(messages),
        "sources": unique_chunks,
        "hops": hops,
    }
