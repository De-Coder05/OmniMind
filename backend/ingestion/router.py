from pathlib import Path
from typing import List, Dict, Any

from .pdf_processor import process_pdf
from .image_processor import process_image
from .audio_processor import process_audio
from .table_processor import process_table

PDF_EXT = {".pdf"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".mp4"}
TABLE_EXT = {".csv", ".tsv", ".xlsx", ".xls"}


def ingest_file(file_path: str) -> List[Dict[str, Any]]:
    """Route a file to the appropriate processor and return chunks."""
    suffix = Path(file_path).suffix.lower()

    if suffix in PDF_EXT:
        return process_pdf(file_path)
    elif suffix in IMAGE_EXT:
        return process_image(file_path)
    elif suffix in AUDIO_EXT:
        return process_audio(file_path)
    elif suffix in TABLE_EXT:
        return process_table(file_path)
    else:
        return []
