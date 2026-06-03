import fitz
import base64
import httpx
import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")


def _describe_image(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    try:
        resp = httpx.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": VISION_MODEL,
                "prompt": "Describe this image in detail. If it contains charts, tables, or diagrams, extract and explain the data shown.",
                "images": [b64],
                "stream": False,
            },
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception:
        return ""


def _split_text(text: str, chunk_size: int = 200, overlap: int = 30) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i:i + chunk_size]))
        i += chunk_size - overlap
    return chunks


def process_pdf(file_path: str) -> List[Dict[str, Any]]:
    doc = fitz.open(file_path)
    chunks = []
    filename = Path(file_path).name

    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text").strip()
        if text:
            for chunk in _split_text(text):
                chunks.append({
                    "text": chunk,
                    "modality": "text",
                    "source": filename,
                    "page": page_num,
                    "type": "pdf_text",
                })

        for img_index, img in enumerate(page.get_images(full=True)):
            base_image = doc.extract_image(img[0])
            description = _describe_image(base_image["image"])
            if description:
                chunks.append({
                    "text": f"[Image on page {page_num}]: {description}",
                    "modality": "image",
                    "source": filename,
                    "page": page_num,
                    "type": "pdf_image",
                    "image_index": img_index,
                })

    doc.close()
    return chunks
