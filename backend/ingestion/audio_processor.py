import os
import whisper
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
SUPPORTED = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4"}

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = whisper.load_model(WHISPER_MODEL)
    return _model


def process_audio(file_path: str) -> List[Dict[str, Any]]:
    """Transcribe audio/video file using Whisper, return as text chunks."""
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED:
        return []

    model = _get_model()
    result = model.transcribe(file_path)
    full_text = result.get("text", "").strip()

    if not full_text:
        return []

    chunks = []
    words = full_text.split()
    chunk_size = 400
    overlap = 40

    i = 0
    while i < len(words):
        chunk = " ".join(words[i: i + chunk_size])
        chunks.append({
            "text": chunk,
            "modality": "audio",
            "source": path.name,
            "page": 1,
            "type": "audio_transcript",
        })
        i += chunk_size - overlap

    return chunks
