from typing import Any, Dict, List, Optional

from backend.schemas.onboarding_record import (
    Evidence,
    ExtractedField,
    OnboardingRecord,
)


def _get_site_field(site_fields: dict, *keys: str):
    for key in keys:
        value = site_fields.get(key)
        if value not in (None, "", [], {}):
            return value
    return None


def _field_exists(fields: List[ExtractedField], name: str) -> bool:
    return any(f.name == name for f in fields)


def build_onboarding_record(
    project_name: str | None,
    plant_type: str,
    source_files: List[str],
    raw_fields: List[Dict[str, Any]],
    site_fields: Optional[Dict[str, Any]] = None,
) -> OnboardingRecord:
    extracted_fields: List[ExtractedField] = []

    for raw_field in raw_fields:
        evidence_items = [
            Evidence(
                file_name=item["file_name"],
                page=item.get("page"),
                sheet=item.get("sheet"),
                section=item.get("section"),
                snippet=item.get("snippet"),
            )
            for item in raw_field.get("evidence", [])
        ]

        extracted_field = ExtractedField(
            name=raw_field["name"],
            raw_value=raw_field.get("raw_value"),
            normalized_value=raw_field.get("normalized_value"),
            confidence=raw_field.get("confidence", 0.0),
            evidence=evidence_items,
            status=raw_field.get("status", "needs_review"),
        )
        extracted_fields.append(extracted_field)

    site_fields = site_fields or {}

    address = _get_site_field(site_fields, "Address")
    country = _get_site_field(site_fields, "Country")
    lat = _get_site_field(site_fields, "Latitude")
    long = _get_site_field(site_fields, "Longitude")

    if address is not None and not _field_exists(extracted_fields, "address"):
        extracted_fields.append(
            ExtractedField(
                name="address",
                raw_value=address,
                normalized_value=address,
                confidence=0.85,
                evidence=[],
                status="valid",
            )
        )

    if country is not None and not _field_exists(extracted_fields, "country"):
        extracted_fields.append(
            ExtractedField(
                name="country",
                raw_value=country,
                normalized_value=country,
                confidence=0.85,
                evidence=[],
                status="valid",
            )
        )

    if lat is not None and not _field_exists(extracted_fields, "lat"):
        extracted_fields.append(
            ExtractedField(
                name="lat",
                raw_value=lat,
                normalized_value=lat,
                confidence=0.85,
                evidence=[],
                status="valid",
            )
        )

    if long is not None and not _field_exists(extracted_fields, "long"):
        extracted_fields.append(
            ExtractedField(
                name="long",
                raw_value=long,
                normalized_value=long,
                confidence=0.85,
                evidence=[],
                status="valid",
            )
        )

    return OnboardingRecord(
        project_name=project_name,
        plant_type=plant_type,
        source_files=source_files,
        fields=extracted_fields,
        readiness_status="needs_review",
    )