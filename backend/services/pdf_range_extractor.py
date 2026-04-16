from __future__ import annotations

from pathlib import Path
from typing import Any

import fitz

from backend.services.evidence_builder import build_evidence
from backend.services.confidence_builder import score_text_block

def extract_pdf_page_range(path: str, start_page: int, end_page: int) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    combined_text: list[str] = []
    evidence: list[dict[str, Any]] = []

    try:
        doc = fitz.open(path)
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "pages": [],
            "combined_text": "",
            "text_len": 0,
            "evidence": [],
        }

    file_name = Path(path).name
    total_pages = len(doc)
    start_idx = max(0, start_page - 1)
    end_idx = min(end_page - 1, total_pages - 1)

    for page_idx in range(start_idx, end_idx + 1):
        page = doc[page_idx]
        text = (page.get_text("text") or "").strip()

        pages.append(
            {
                "page_number": page_idx + 1,
                "text": text,
            }
        )

        if text:
            combined_text.append(text)

            evidence.append(
                build_evidence(
                    file_name=file_name,
                    file_type="pdf",
                    page=page_idx + 1,
                    sheet_name=None,
                    snippet=text,
                    method="pdf_page_text",
                    block_index=0,
                    confidence=score_text_block(
                        text=text,
                        method="pdf_page_text",
                        file_type="pdf",
                    ),
                )
            )

    full_text = "\n".join(combined_text).strip()

    return {
        "status": "ok",
        "start_page": start_page,
        "end_page": end_page,
        "pages": pages,
        "combined_text": full_text,
        "text_len": len(full_text),
        "evidence": evidence,
    }