import os
import uuid
import json
import hashlib
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
from backend.agent.omnimind_agent import (
    SYSTEM_PROMPT, _build_context, _refine_query, rewrite_query, _build_history_messages
)

load_dotenv()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()

_sessions: Dict[str, Dict[str, Any]] = {}


class QueryRequest(BaseModel):
    session_id: str
    query: str


def _get_session(session_id: str) -> Dict[str, Any]:
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return _sessions[session_id]


@router.post("/session/create")
async def create_session():
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {"files": [], "history": []}
    return {"session_id": session_id}


@router.post("/session/{session_id}/upload")
async def upload_files(session_id: str, files: List[UploadFile] = File(...)):
    session = _get_session(session_id)
    session_dir = UPLOAD_DIR / session_id
    session_dir.mkdir(exist_ok=True)
    results = []

    for file in files:
        dest = session_dir / file.filename
        async with aiofiles.open(dest, "wb") as out:
            await out.write(await file.read())
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
    session = _get_session(req.session_id)
    if not session["files"]:
        raise HTTPException(status_code=400, detail="No files uploaded in this session")

    history: List[Dict] = session["history"]
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    llm_model = os.getenv("OLLAMA_LLM_MODEL", "llama3")

    async def event_stream() -> AsyncIterator[str]:
        retrieval_query = rewrite_query(req.query, history)
        first_chunks = query_collection(req.session_id, retrieval_query, n_results=10)
        refined = _refine_query(retrieval_query, first_chunks)
        second_chunks: List[Dict] = []
        hops = 1

        if refined:
            second_chunks = query_collection(req.session_id, refined, n_results=6)
            hops = 2

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
        grounded_question = f"DOCUMENT EXCERPTS:\n\n{context}\n\n---\n\nQuestion: {req.query}\n\nAnswer using only the excerpts above. Cite with [1], [2], etc."

        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + _build_history_messages(history)
            + [{"role": "user", "content": grounded_question}]
        )

        full_answer = ""
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", f"{ollama_url}/api/chat", json={"model": llm_model, "messages": messages, "stream": True}) as resp:
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

        MAX_TURNS = 4
        history.append({"role": "user", "content": req.query})
        history.append({"role": "assistant", "content": full_answer})
        if len(history) > MAX_TURNS * 2:
            history[:] = history[-(MAX_TURNS * 2):]

        yield "data: " + json.dumps({"sources": [{"text": c["text"], "metadata": c["metadata"], "score": c.get("score", 0)} for c in unique_chunks], "hops": hops}) + "\n\n"
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
