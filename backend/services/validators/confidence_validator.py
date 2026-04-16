from collections import defaultdict

from backend.schemas.onboarding_record import OnboardingRecord, ValidationIssue


LOW_CONFIDENCE_THRESHOLD = 0.85


def validate_confidence_and_review(record: OnboardingRecord) -> OnboardingRecord:
    issues = []
    values_by_field = defaultdict(list)

    for field in record.fields:
        values_by_field[field.name].append(field)

        if field.confidence < LOW_CONFIDENCE_THRESHOLD:
            field.status = "low_confidence"
            issues.append(
                ValidationIssue(
                    field_name=field.name,
                    issue_type="low_confidence",
                    message=f"Field '{field.name}' has low confidence: {field.confidence}",
                    severity="medium",
                )
            )

    multi_value_allowed_fields = {
        "inverter_model",
        "inverter_manufacturer",
    }

    for field_name, fields in values_by_field.items():
        if field_name in multi_value_allowed_fields:
            continue

        unique_values = {
            str(f.normalized_value).strip().upper()
            for f in fields
            if f.normalized_value is not None
        }

        if len(unique_values) > 1:
            for field in fields:
                field.status = "conflicting"
            issues.append(
                ValidationIssue(
                    field_name=field_name,
                    issue_type="conflict",
                    message=f"Field '{field_name}' has multiple candidate values and needs review.",
                    severity="high",
                )
            )

    record.validation_issues.extend(issues)

    blocking_issues = [
        i for i in issues
        if i.issue_type == "missing" or i.severity == "high"
    ]

    if record.readiness_status != "incomplete":
        if blocking_issues:
            record.readiness_status = "needs_review"
        else:
            record.readiness_status = "ready"

    return record