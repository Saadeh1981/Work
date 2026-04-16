# backend/schemas/output_v1.py
from __future__ import annotations

from enum import Enum
from typing import Any, Optional, List

from pydantic import BaseModel, Field, ConfigDict


class FileType(str, Enum):
    pdf = "pdf"
    xlsx = "xlsx"
    docx = "docx"
    png = "png"
    jpg = "jpg"
    email = "email"
    zip = "zip"
    other = "other"
from typing import Literal

class SourceType(str, Enum):
    text = "text"
    table = "table"
    ocr = "ocr"
    image = "image"

class Scope(str, Enum):
    portfolio = "portfolio"
    plant = "plant"
    device = "device"
    signal = "signal"

class Reason(str, Enum):
    not_found = "not_found"
    unreadable = "unreadable"
    ambiguous = "ambiguous"
    conflict = "conflict"
    low_confidence = "low_confidence"

class Priority(str, Enum):
    high = "high"
    medium = "medium"
    low = "low"

class PlantType(str, Enum):
    solar = "solar"
    wind = "wind"
    hydro = "hydro"
    bess = "bess"
    hybrid = "hybrid"
    unknown = "unknown"

class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    page: Optional[int] = None
    source_type: SourceType
    snippet: str
    bbox: Optional[List[int]] = None


class FieldValue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    value: Any
    unit: Optional[str] = None
    normalized_value: Optional[Any] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)


class RunFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    file_name: str
    file_type: FileType
    source_uri: Optional[str] = None
    sha256: Optional[str] = None
    pages: Optional[int] = None


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_name: Optional[str] = None
    portfolio_name: Optional[str] = None
    source_files: List[RunFile] = Field(default_factory=list)


class RunInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    created_utc: str
    environment: str
    request: RunRequest


class MissingItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Scope
    plant_id: Optional[str] = None
    node_id: Optional[str] = None
    field: str
    required_by: str
    reason: Reason
    question_for_user: str
    priority: Priority


class ConflictCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: Any
    unit: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)


class ConflictItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Scope
    plant_id: str
    node_id: Optional[str] = None
    field: str
    candidates: List[ConflictCandidate] = Field(default_factory=list)
    recommended: Optional[ConflictCandidate] = None
    rule: Optional[str] = None


class QualityScores(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_confidence: float = Field(ge=0.0, le=1.0)
    completeness: float = Field(ge=0.0, le=1.0)
    readability: float = Field(ge=0.0, le=1.0)


class QualityBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    missing: List[MissingItem] = Field(default_factory=list)
    conflicts: List[ConflictItem] = Field(default_factory=list)
    scores: QualityScores


class TimingBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingest: int = 0
    ocr: int = 0
    parse: int = 0
    normalize: int = 0
    assemble_output: int = 0


class DebugError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    file_id: Optional[str] = None


class DebugBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timings_ms: TimingBlock = Field(default_factory=TimingBlock)
    warnings: List[str] = Field(default_factory=list)
    errors: List[DebugError] = Field(default_factory=list)


class PlantOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plant_id: str
    plant_name: Optional[str] = None
    plant_type: PlantType = PlantType.unknown
    location: Optional[dict] = None
    capacity: Optional[dict] = None
    key_dates: Optional[dict] = None
    metadata: List[FieldValue] = Field(default_factory=list)


class OverviewBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plants: List[PlantOverview] = Field(default_factory=list)


class DevicesPlantBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plant_id: str
    device_tree: List[dict] = Field(default_factory=list)


class DevicesBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plants: List[DevicesPlantBlock] = Field(default_factory=list)


class SignalRequired(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_key: str
    found: bool
    matched_to: Optional[str] = None
    unit: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)


class SignalsSummaryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plant_id: str
    device_node_id: Optional[str] = None
    signal_group: str
    total_signals: int = 0
    required_signals: List[SignalRequired] = Field(default_factory=list)
    tag_lists: List[dict] = Field(default_factory=list)


class SignalsBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: List[SignalsSummaryItem] = Field(default_factory=list)


class OutputV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    run: RunInfo
    overview: OverviewBlock
    devices: DevicesBlock
    signals: SignalsBlock
    quality: QualityBlock
    debug: DebugBlock
