import base64
import httpx
import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")

SUPPORTED = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}


def process_image(file_path: str) -> List[Dict[str, Any]]:
    """Describe a standalone image file using LLaVA."""
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED:
        return []

    with open(file_path, "rb") as f:
        image_bytes = f.read()

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": VISION_MODEL,
        "prompt": (
            "Describe this image in detail. "
            "If it contains charts, graphs, tables, or diagrams, extract the data and explain what it shows. "
            "If it contains text, transcribe it."
        ),
        "images": [b64],
        "stream": False,
    }

    try:
        resp = httpx.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=90)
        resp.raise_for_status()
        description = resp.json().get("response", "")
    except Exception:
        description = f"Image file: {path.name}"

    return [{
        "text": description,
        "modality": "image",
        "source": path.name,
        "page": 1,
        "type": "standalone_image",
    }]
