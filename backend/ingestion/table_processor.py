import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

SUPPORTED = {".csv", ".tsv", ".xlsx", ".xls"}


def process_table(file_path: str) -> List[Dict[str, Any]]:
    """Convert tabular files into natural-language text chunks."""
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED:
        return []

    try:
        if suffix == ".csv":
            df = pd.read_csv(file_path)
        elif suffix == ".tsv":
            df = pd.read_csv(file_path, sep="\t")
        else:
            df = pd.read_excel(file_path)
    except Exception:
        return []

    chunks = []
    # Convert each row group (50 rows) into a natural-language chunk
    row_chunk_size = 50
    for start in range(0, len(df), row_chunk_size):
        subset = df.iloc[start: start + row_chunk_size]
        text = f"Table from {path.name} (rows {start + 1}–{start + len(subset)}):\n"
        text += subset.to_string(index=False)
        chunks.append({
            "text": text,
            "modality": "table",
            "source": path.name,
            "page": 1,
            "type": "tabular_data",
            "row_start": start + 1,
            "row_end": start + len(subset),
        })

    return chunks
