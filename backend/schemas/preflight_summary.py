from __future__ import annotations

from pydantic import BaseModel
from typing import Literal, Optional


class PreflightSummary(BaseModel):
    file_type: Literal["pdf", "docx", "xlsx", "other"]
    method: Literal["native_preflight"] = "native_preflight"

    page_count: Optional[int] = None  # pdf pages, xlsx sheets, docx=1
    native_text_detected: bool = False

    sampled_units: int = 0  # pages/sheets sampled
    sample_text: str = ""   # bounded
    notes: list[str] = []
