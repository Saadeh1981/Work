from backend.config.required_fields import get_required_fields
from backend.schemas.onboarding_record import OnboardingRecord, ValidationIssue


BAD_PLANT_NAMES = {
    "TITLE SHEET",
    "AS BUILT",
    "FOR CONSTRUCTION",
    "SYMBOL",
    "BATTERY",
    "BESS FIELD",
    "BLOCK ARRAY CONFIGURATION",
    "LINETYPE LEGEND",
    "WARNING SIGNS",
    "KEYED NOTES",
    "CIVIL DETAILS",
    "AREA 1 & 2 SITE MAP",
    "INVERTER 1.1.1",
    "INVERTER SPECIFIC WARNING",
    "COMBINER HARNESS NAMING CONVENTION",
    "COMBINER HARNESS AT TRACKER",
    "DC FEEDER TRENCH",
    "EQUIPMENT SPECIFICATIONS",
    "FIBER OPTIC DIAGRAM",
    "ZONE A",
    "BLYMYER",
    "DANGER",
    "50' UTILITY",
}


def is_bad_project_name(value: str | None) -> bool:
    if not value:
        return True
    return str(value).strip().upper() in BAD_PLANT_NAMES


def validate_required_fields(record: OnboardingRecord) -> OnboardingRecord:
    required_fields = get_required_fields(record.plant_type)

    # Demo mode override
    required_fields = [
        "project_name",
        "plant_type",
        "ac_capacity_kw",
        "timezone",
    ]

    extracted_field_names = {field.name for field in record.fields}
    missing_issues = []

    for field_name in required_fields:
        if field_name not in extracted_field_names:
            missing_issues.append(
                ValidationIssue(
                    field_name=field_name,
                    issue_type="missing",
                    message=f"Required field '{field_name}' is missing.",
                    severity="high",
                )
            )

    # Project name quality check
    if is_bad_project_name(record.project_name):
        missing_issues.append(
            ValidationIssue(
                field_name="project_name",
                issue_type="missing",
                message="Project name looks like a sheet label or non-site value.",
                severity="high",
            )
        )

    # Plant type quality check
    if not record.plant_type or record.plant_type not in {"solar", "bess", "hybrid", "wind", "hydro"}:
        missing_issues.append(
            ValidationIssue(
                field_name="plant_type",
                issue_type="missing",
                message="Plant type is missing or invalid.",
                severity="high",
            )
        )

    # AC capacity quality check
    ac_field = next((field for field in record.fields if field.name == "ac_capacity_kw"), None)

    if ac_field is None or ac_field.normalized_value in (None, "", [], {}):
        missing_issues.append(
            ValidationIssue(
                field_name="ac_capacity_kw",
                issue_type="missing",
                message="AC capacity is missing.",
                severity="high",
            )
        )
    else:
        try:
            ac_value = float(ac_field.normalized_value)
            if ac_value <= 0:
                missing_issues.append(
                    ValidationIssue(
                        field_name="ac_capacity_kw",
                        issue_type="missing",
                        message="AC capacity must be greater than zero.",
                        severity="high",
                    )
                )
        except (TypeError, ValueError):
            missing_issues.append(
                ValidationIssue(
                    field_name="ac_capacity_kw",
                    issue_type="missing",
                    message="AC capacity is not numeric.",
                    severity="high",
                )
            )

    blocking_issues = [
        i for i in record.validation_issues
        if i.issue_type == "missing" or i.severity == "high"
    ]

    if blocking_issues:
        record.readiness_status = "incomplete"
    else:
        record.readiness_status = "ready"

    return record