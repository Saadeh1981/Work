from typing import Any, List, Optional, Literal
from pydantic import BaseModel, Field


FieldStatus = Literal[
    "valid",
    "missing",
    "low_confidence",
    "conflicting",
    "duplicate",
    "needs_review",
]

PlantType = Literal[
    "solar",
    "wind",
    "bess",
    "hydro",
    "hybrid",
    "unknown",
]

ReadinessStatus = Literal[
    "ready",
    "needs_review",
    "incomplete",
]


class Evidence(BaseModel):
    file_name: str
    page: Optional[int] = None
    sheet: Optional[str] = None
    section: Optional[str] = None
    snippet: Optional[str] = None


class ExtractedField(BaseModel):
    name: str
    raw_value: Optional[Any] = None
    normalized_value: Optional[Any] = None
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[Evidence] = Field(default_factory=list)
    status: FieldStatus = "needs_review"


class EquipmentItem(BaseModel):
    equipment_type: str
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    quantity: Optional[int] = None
    fields: List[ExtractedField] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    field_name: str
    issue_type: Literal["missing", "low_confidence", "conflict", "duplicate", "format_error"]
    message: str
    severity: Literal["low", "medium", "high"]


class OnboardingRecord(BaseModel):
    project_name: Optional[str] = None
    plant_type: PlantType = "unknown"
    source_files: List[str] = Field(default_factory=list)
    fields: List[ExtractedField] = Field(default_factory=list)
    equipment: List[EquipmentItem] = Field(default_factory=list)
    validation_issues: List[ValidationIssue] = Field(default_factory=list)
    readiness_status: ReadinessStatus = "needs_review"