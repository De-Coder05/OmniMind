import os
import httpx
from typing import List, Dict, Any
from dotenv import load_dotenv
from backend.embeddings.store import query_collection

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "llama3")
MAX_HOPS = 3  # max tool-call iterations


def _call_ollama(messages: List[Dict]) -> str:
    payload = {"model": LLM_MODEL, "messages": messages, "stream": False}
    resp = httpx.post(
        f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=120
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"]


def _build_system_prompt() -> str:
    return """You are OmniMind, an expert research assistant with access to a multimodal document store containing text, images, audio transcripts, and tables.

You answer questions by reasoning step-by-step and searching the document store for relevant information.

TOOL AVAILABLE:
- search(query: str) → returns relevant excerpts from the document store

RULES:
1. Always search before answering. Do not rely on prior knowledge alone.
2. If one search is not enough, search again with a refined query (up to 3 searches).
3. After gathering evidence, synthesize a final answer with inline citations like [Source: filename, page X].
4. If information is not found in the documents, say so clearly.
5. For image or audio content, treat the description/transcript as the source.

FORMAT your response as:
THOUGHT: <your reasoning>
SEARCH: <query> (repeat THOUGHT/SEARCH up to 3 times if needed)
ANSWER: <final synthesized answer with citations>"""


def _parse_search_query(text: str) -> str | None:
    """Extract the query from a SEARCH: line."""
    for line in text.split("\n"):
        if line.strip().upper().startswith("SEARCH:"):
            return line.split(":", 1)[1].strip()
    return None


def _parse_final_answer(text: str) -> str | None:
    """Extract the final ANSWER: block."""
    for i, line in enumerate(text.split("\n")):
        if line.strip().upper().startswith("ANSWER:"):
            return "\n".join(text.split("\n")[i:]).split(":", 1)[1].strip()
    return None


def run_agent(session_id: str, user_query: str) -> Dict[str, Any]:
    """
    ReAct-style agent loop:
    - Thinks about what to search
    - Retrieves from ChromaDB
    - Injects results and continues reasoning
    - Returns final answer + sources used
    """
    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {"role": "user", "content": user_query},
    ]

    all_sources: List[Dict] = []
    reasoning_trace: List[str] = []

    for hop in range(MAX_HOPS):
        response = _call_ollama(messages)
        reasoning_trace.append(response)

        search_query = _parse_search_query(response)

        if search_query:
            retrieved = query_collection(session_id, search_query, n_results=6)
            all_sources.extend(retrieved)

            context_block = "\n\n".join([
                f"[{i+1}] Source: {c['metadata'].get('source','?')}, "
                f"Page: {c['metadata'].get('page','?')}, "
                f"Modality: {c['metadata'].get('modality','text')}\n{c['text']}"
                for i, c in enumerate(retrieved)
            ])

            tool_result = (
                f"SEARCH RESULTS for '{search_query}':\n\n{context_block}"
                if retrieved
                else f"SEARCH RESULTS for '{search_query}': No relevant content found."
            )

            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": tool_result})

        final_answer = _parse_final_answer(response)
        if final_answer:
            # Deduplicate sources by (source, page)
            seen = set()
            unique_sources = []
            for s in all_sources:
                key = (s["metadata"].get("source"), s["metadata"].get("page"))
                if key not in seen:
                    seen.add(key)
                    unique_sources.append(s)

            return {
                "answer": final_answer,
                "sources": unique_sources,
                "hops": hop + 1,
                "reasoning_trace": reasoning_trace,
            }

    # Fallback: return last response as-is
    return {
        "answer": reasoning_trace[-1] if reasoning_trace else "I could not find an answer.",
        "sources": all_sources,
        "hops": MAX_HOPS,
        "reasoning_trace": reasoning_trace,
    }
