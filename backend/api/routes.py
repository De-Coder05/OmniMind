import os
import uuid
import aiofiles
from pathlib import Path
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.ingestion.router import ingest_file
from backend.embeddings.store import add_chunks, delete_collection
from backend.agent.omnimind_agent import run_agent

load_dotenv()

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "./data/uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()

# In-memory session store (file list per session)
_sessions: dict[str, List[str]] = {}


class QueryRequest(BaseModel):
    session_id: str
    query: str


class SessionResponse(BaseModel):
    session_id: str


@router.post("/session/create", response_model=SessionResponse)
async def create_session():
    session_id = str(uuid.uuid4())
    _sessions[session_id] = []
    return {"session_id": session_id}


@router.post("/session/{session_id}/upload")
async def upload_files(session_id: str, files: List[UploadFile] = File(...)):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")

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
            _sessions[session_id].append(file.filename)
            results.append({"file": file.filename, "chunks_indexed": count, "status": "ok"})
        except Exception as e:
            results.append({"file": file.filename, "chunks_indexed": 0, "status": f"error: {str(e)}"})

    return {"session_id": session_id, "files": results}


@router.post("/query")
async def query(req: QueryRequest):
    if req.session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    if not _sessions[req.session_id]:
        raise HTTPException(status_code=400, detail="No files uploaded in this session")

    result = run_agent(req.session_id, req.query)
    return {
        "session_id": req.session_id,
        "query": req.query,
        "answer": result["answer"],
        "sources": result["sources"],
        "hops": result["hops"],
    }


@router.get("/session/{session_id}/files")
async def list_files(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"session_id": session_id, "files": _sessions[session_id]}


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    delete_collection(session_id)
    del _sessions[session_id]
    return {"status": "deleted"}
