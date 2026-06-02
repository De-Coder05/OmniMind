import os
import uuid
import json
import aiofiles
import httpx
from pathlib import Path
from typing import List, Dict, Any, AsyncIterator
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.ingestion.router import ingest_file
from backend.embeddings.store import add_chunks, delete_collection, query_collection
from backend.agent.omnimind_agent import run_agent, _build_context, _refine_query, rewrite_query, _history_to_messages

load_dotenv()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()

# Per-session state: files list + conversation history
_sessions: Dict[str, Dict[str, Any]] = {}


def _get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return _sessions[session_id]


class QueryRequest(BaseModel):
    session_id: str
    query: str


class SessionResponse(BaseModel):
    session_id: str


@router.post("/session/create", response_model=SessionResponse)
async def create_session():
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {"files": [], "history": []}
    return {"session_id": session_id}


@router.post("/session/{session_id}/upload")
async def upload_files(session_id: str, files: List[UploadFile] = File(...)):
    session = _get_session(session_id)
    results = []
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(exist_ok=True)

    for file in files:
        dest = session_dir / file.filename
        async with aiofiles.open(dest, "wb") as out:
            content = await file.read()
            await out.write(content)

        try:
            chunks = ingest_file(str(dest))
            count = add_chunks(session_id, chunks)
            session["files"].append(file.filename)
            results.append({"file": file.filename, "chunks_indexed": count, "status": "ok"})
        except Exception as e:
            results.append({"file": file.filename, "chunks_indexed": 0, "status": f"error: {str(e)}"})

    return {"session_id": session_id, "files": results}


@router.post("/query/stream")
async def query_stream(req: QueryRequest):
    """SSE streaming endpoint with conversation memory."""
    session = _get_session(req.session_id)
    if not session["files"]:
        raise HTTPException(status_code=400, detail="No files uploaded in this session")

    history: List[Dict] = session["history"]
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model = os.getenv("OLLAMA_LLM_MODEL", "llama3")

    async def event_stream() -> AsyncIterator[str]:
        # --- Query rewriting + retrieval (non-streaming) ---
        retrieval_query = rewrite_query(req.query, history)

        first_chunks = query_collection(req.session_id, retrieval_query, n_results=10)
        refined = _refine_query(retrieval_query, first_chunks)
        second_chunks: List[Dict] = []
        hops = 1
        if refined:
            second_chunks = query_collection(req.session_id, refined, n_results=6)
            hops = 2

        # Deduplicate by text hash (not page — single-page docs like resumes
        # produce multiple chunks all tagged as the same page number)
        import hashlib
        seen: set = set()
        unique_chunks: List[Dict] = []
        for c in first_chunks + second_chunks:
            key = hashlib.md5(c["text"].encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique_chunks.append(c)

        if not unique_chunks:
            yield "data: " + json.dumps({"token": "I couldn't find relevant information in the uploaded documents."}) + "\n\n"
            yield "data: " + json.dumps({"sources": [], "hops": hops}) + "\n\n"
            yield "data: [DONE]\n\n"
            return

        context = _build_context(unique_chunks)

        # --- Build messages with history ---
        MAX_TURNS = 4
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

        history_messages = []
        for m in history[-(MAX_TURNS * 2):]:
            if m["role"] == "assistant":
                content = m["content"][:300].rsplit(" ", 1)[0] + "…" if len(m["content"]) > 300 else m["content"]
                history_messages.append({"role": "assistant", "content": content})
            else:
                history_messages.append({"role": "user", "content": m["content"]})

        grounded_question = (
            f"DOCUMENT EXCERPTS:\n\n{context}\n\n"
            f"---\n\n"
            f"Question: {req.query}\n\n"
            "Answer using only the excerpts above. Cite with [1], [2], etc."
        )

        messages = (
            [{"role": "system", "content": system_msg}]
            + history_messages
            + [{"role": "user", "content": grounded_question}]
        )

        payload = {"model": llm_model, "messages": messages, "stream": True}

        # --- Stream tokens ---
        full_answer = ""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{ollama_url}/api/chat", json=payload) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        token = data.get("message", {}).get("content", "")
                        if token:
                            full_answer += token
                            yield "data: " + json.dumps({"token": token}) + "\n\n"
                        if data.get("done"):
                            break
                    except Exception:
                        continue

        # --- Update conversation history ---
        history.append({"role": "user", "content": req.query})
        history.append({"role": "assistant", "content": full_answer})
        # Keep history bounded
        if len(history) > MAX_TURNS * 2:
            history[:] = history[-(MAX_TURNS * 2):]

        # --- Send sources ---
        sources_payload = [
            {"text": c["text"], "metadata": c["metadata"], "score": c.get("score", 0)}
            for c in unique_chunks
        ]
        yield "data: " + json.dumps({"sources": sources_payload, "hops": hops}) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/session/{session_id}/files")
async def list_files(session_id: str):
    session = _get_session(session_id)
    return {"session_id": session_id, "files": session["files"]}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    _get_session(session_id)
    delete_collection(session_id)
    del _sessions[session_id]
    return {"status": "deleted"}
