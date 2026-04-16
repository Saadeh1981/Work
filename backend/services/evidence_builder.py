from __future__ import annotations

from typing import Any


def build_evidence(
    file_name: str,
    snippet: str,
    method: str,
    block_index: int,
    file_type: str | None = None,
    page: int | None = None,
    sheet_name: str | None = None,
    confidence: float = 0.8,
) -> dict[str, Any]:
    cleaned = (snippet or "").replace("\n", " ").strip()

    return {
        "source_file": file_name,
        "file_type": file_type,
        "page": page,
        "sheet_name": sheet_name,
        "block_index": block_index,
        "snippet": cleaned[:250],
        "method": method,
        "confidence": confidence,
    }