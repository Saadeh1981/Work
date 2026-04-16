from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class FileSection(BaseModel):
    label: str
    start_page: Optional[int] = None
    end_page: Optional[int] = None
    sheet_name: Optional[str] = None
    confidence: float = 0.0
    signals: List[str] = Field(default_factory=list)

    domains: List[str] = Field(default_factory=list)
    content_types: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    attributes: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)


class FileSummary(BaseModel):
    file_id: Optional[str] = None
    file_name: str
    file_type: str
    path: Optional[str] = None

    page_count: Optional[int] = None
    sheet_count: Optional[int] = None
    text_layer_present: Optional[bool] = None
    scan_likelihood: Optional[float] = None

    likely_contents: List[str] = Field(default_factory=list)
    sections: List[FileSection] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    domains: List[str] = Field(default_factory=list)
    content_types: List[str] = Field(default_factory=list)
    entities: List[str] = Field(default_factory=list)
    attributes: List[str] = Field(default_factory=list)
    relationships: List[str] = Field(default_factory=list)


class SummaryRequest(BaseModel):
    root_path: str
    sample_pages: int = 5


class SummaryResponse(BaseModel):
    files: List[FileSummary] = Field(default_factory=list)
    global_findings: List[str] = Field(default_factory=list)
    extraction_plan: List[dict] = Field(default_factory=list)