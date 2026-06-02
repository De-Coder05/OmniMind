# OmniMind — Multimodal RAG Agent

> Ask anything about your documents. Get grounded, cited answers — across PDFs, images, audio, and tables — powered entirely by local inference.

![OmniMind UI](docs/screenshot.png)

---

## What it does

OmniMind is a conversational RAG (Retrieval-Augmented Generation) system that lets you upload heterogeneous documents and query across all of them in a single session. It processes four modalities, fuses retrieval signals from two independent rankers, maintains multi-turn conversation memory, and streams answers token-by-token directly in the browser.

**No API keys. No cloud. Everything runs on your machine.**

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (React)                           │
│  Drag-and-drop upload · Streaming chat · Cited source cards      │
└────────────────────────────┬────────────────────────────────────┘
                             │ SSE / REST  (Vite proxy → nginx)
┌────────────────────────────▼────────────────────────────────────┐
│                      FastAPI Backend                             │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                  Ingestion Pipeline                      │    │
│  │  PDF ──► PyMuPDF (text + images)                        │    │
│  │  Image ─► LLaVA via Ollama (caption + understanding)    │    │
│  │  Audio ─► Whisper (local transcription)                 │    │
│  │  CSV/Excel ──► pandas (structured → natural language)   │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │              Hybrid Retrieval (per query)                │    │
│  │  Semantic search  ──► BGE-Large embeddings + ChromaDB   │    │
│  │  Keyword search   ──► BM25 (rank-bm25, in-memory)       │    │
│  │  Fusion           ──► Reciprocal Rank Fusion (RRF)      │    │
│  │  Fairness         ──► Per-file slot reservation         │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                    │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │              Conversational Agent                        │    │
│  │  Query rewriting  ──► resolves "those", "it", "that"    │    │
│  │  Context building ──► role-labeled excerpts (JD/Resume) │    │
│  │  History          ──► last 4 turns, truncated to 300ch  │    │
│  │  Generation       ──► Qwen2.5:7b via Ollama (streaming) │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                             │
                    Ollama (local)
              qwen2.5:7b · llava:7b · whisper
```

---

## Features

| Feature | Details |
|---|---|
| **Multimodal ingestion** | PDF (text + embedded images), standalone images, audio/video, CSV/Excel |
| **Hybrid search** | BM25 keyword + BGE-Large semantic, fused via Reciprocal Rank Fusion |
| **Streaming responses** | Token-by-token SSE stream with rAF-buffered React rendering |
| **Conversation memory** | Last 4 turns with intelligent query rewriting for follow-ups |
| **Multi-file reasoning** | Per-file fair retrieval ensures all documents contribute to answers |
| **Document role labeling** | Distinguishes JOB DESCRIPTION vs CANDIDATE RESUME vs DOCUMENT |
| **Citation rendering** | Inline `[1]`, `[2]` badges mapped to expandable source cards |
| **Session persistence** | Conversation survives page refresh via localStorage |
| **Local inference** | No API costs, no data leaves your machine |
| **Docker deployment** | One command: `docker compose up` |

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Qwen2.5:7b via Ollama |
| **Vision** | LLaVA:7b via Ollama |
| **Audio** | OpenAI Whisper (local) |
| **Embeddings** | `BAAI/bge-large-en-v1.5` (HuggingFace) |
| **Vector DB** | ChromaDB (persistent) |
| **Keyword search** | rank-bm25 |
| **Backend** | FastAPI + uvicorn |
| **Frontend** | React + Vite + Tailwind |
| **Deployment** | Docker + nginx |

---

## Quick Start

### Prerequisites

- [Ollama](https://ollama.com) installed and running
- Required models pulled:

```bash
ollama pull qwen2.5:7b
ollama pull llava:7b
```

### Option A — Docker (recommended)

```bash
git clone https://github.com/your-username/OmniMind
cd OmniMind
docker compose up --build
```

Open `http://localhost:3000`

### Option B — Local development

```bash
# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001

# Frontend (new terminal)
cd frontend && npm install && npm run dev
```

Open `http://localhost:5173`

---

## How to use

1. **Upload** — drag any combination of PDFs, images, audio files, or CSVs into the sidebar
2. **Index** — click "Index Documents" (first run downloads the BGE embedding model, ~1 min)
3. **Ask** — type any question. Follow-up questions work naturally: "what about those requirements?" resolves correctly
4. **Explore sources** — click any source card to expand the raw excerpt that grounded the answer

### Demo scenario

Upload a job description PDF alongside your resume, then ask:
- *"What are the required skills for this job?"*
- *"Does the candidate have those?"*
- *"What are the main gaps?"*
- *"Write a cover letter opening paragraph based on both documents"*

---

## Project Structure

```
OmniMind/
├── backend/
│   ├── ingestion/
│   │   ├── router.py          # routes files to correct processor
│   │   ├── pdf_processor.py   # PyMuPDF + LLaVA for embedded images
│   │   ├── image_processor.py # LLaVA image understanding
│   │   ├── audio_processor.py # Whisper transcription
│   │   └── table_processor.py # pandas structured extraction
│   ├── embeddings/
│   │   └── store.py           # ChromaDB + BM25 + RRF hybrid retrieval
│   └── agent/
│       └── omnimind_agent.py  # query rewriting + retrieve-then-read RAG
├── frontend/
│   └── src/
│       ├── App.jsx            # layout + streaming logic
│       ├── api.js             # SSE client
│       └── components/
│           ├── ChatMessage.jsx
│           ├── SourceCard.jsx
│           └── Dropzone.jsx
├── main.py                    # FastAPI app + CORS
├── docker-compose.yml
├── Dockerfile.backend
├── Dockerfile.frontend
└── nginx.conf                 # SSE-aware reverse proxy
```

---

## Design decisions

**Why local inference?** Privacy — documents never leave the machine. No per-token API cost. Demonstrates production-grade LLM integration without relying on managed APIs.

**Why Qwen2.5:7b?** Outperforms Llama3-8B on instruction following benchmarks while fitting in 16GB unified memory. Critical for multi-document role labeling (JD vs Resume) without hallucination.

**Why RRF over pure semantic search?** BM25 catches exact keyword matches (model names, version numbers, proper nouns) that dense embeddings sometimes miss. RRF fuses both signals without requiring score normalization.

**Why per-file slot reservation?** Single-page documents (resumes) generate fewer chunks than multi-page documents (JDs). Without slot reservation, the larger document dominates retrieval entirely.

---

## License

MIT
