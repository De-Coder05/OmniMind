import fitz  # pymupdf
import base64
import httpx
import os
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
VISION_MODEL = os.getenv("OLLAMA_VISION_MODEL", "llava:7b")


def _describe_image_with_llava(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "model": VISION_MODEL,
        "prompt": "Describe this image in detail. If it contains charts, tables, or diagrams, extract and explain the data shown.",
        "images": [b64],
        "stream": False,
    }
    try:
        resp = httpx.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception:
        return ""


def process_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Extract text chunks and image descriptions from a PDF.
    Returns list of chunk dicts with text, metadata, and modality.
    """
    doc = fitz.open(file_path)
    chunks = []
    filename = Path(file_path).name

    for page_num, page in enumerate(doc, start=1):
        # --- Text chunks ---
        text = page.get_text("text").strip()
        if text:
            # Split into ~200-word chunks with overlap
            for chunk in _split_text(text, chunk_size=200, overlap=30):
                chunks.append({
                    "text": chunk,
                    "modality": "text",
                    "source": filename,
                    "page": page_num,
                    "type": "pdf_text",
                })

        # --- Embedded images ---
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            description = _describe_image_with_llava(image_bytes)
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


def _split_text(text: str, chunk_size: int = 200, overlap: int = 30) -> List[str]:
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i: i + chunk_size])
        chunks.append(chunk)
        i += chunk_size - overlap
    return chunks
