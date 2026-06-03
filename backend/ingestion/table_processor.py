import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

SUPPORTED = {".csv", ".tsv", ".xlsx", ".xls"}


def process_table(file_path: str) -> List[Dict[str, Any]]:
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED:
        return []

    try:
        if path.suffix.lower() == ".csv":
            df = pd.read_csv(file_path)
        elif path.suffix.lower() == ".tsv":
            df = pd.read_csv(file_path, sep="\t")
        else:
            df = pd.read_excel(file_path)
    except Exception:
        return []

    chunks = []
    for start in range(0, len(df), 50):
        subset = df.iloc[start:start + 50]
        chunks.append({
            "text": f"Table from {path.name} (rows {start + 1}–{start + len(subset)}):\n{subset.to_string(index=False)}",
            "modality": "table",
            "source": path.name,
            "page": 1,
            "type": "tabular_data",
            "row_start": start + 1,
            "row_end": start + len(subset),
        })

    return chunks
