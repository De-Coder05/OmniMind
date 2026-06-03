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
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED:
        return []

    result = _get_model().transcribe(file_path)
    full_text = result.get("text", "").strip()
    if not full_text:
        return []

    chunks = []
    words = full_text.split()
    i = 0
    while i < len(words):
        chunks.append({
            "text": " ".join(words[i:i + 400]),
            "modality": "audio",
            "source": path.name,
            "page": 1,
            "type": "audio_transcript",
        })
        i += 360

    return chunks
