from backend.schemas.onboarding_record import OnboardingRecord, ExtractedField
from backend.services.validators.required_fields_validator import validate_required_fields


def test_validator_flags_missing_required_fields():
    record = OnboardingRecord(
        project_name="Desert Sun Plant",
        plant_type="solar",
        source_files=["site_form.pdf"],
        fields=[
            ExtractedField(
                name="project_name",
                raw_value="Desert Sun Plant",
                normalized_value="Desert Sun Plant",
                confidence=0.99,
                evidence=[],
                status="valid",
            ),
            ExtractedField(
                name="plant_type",
                raw_value="solar",
                normalized_value="solar",
                confidence=0.99,
                evidence=[],
                status="valid",
            ),
        ],
        readiness_status="needs_review",
    )

    validated = validate_required_fields(record)

    assert validated.readiness_status == "incomplete"
    assert len(validated.validation_issues) > 0
    assert any(issue.field_name == "installed_capacity_mw" for issue in validated.validation_issues)
    assert all(issue.issue_type == "missing" for issue in validated.validation_issues)


def test_validator_passes_when_all_required_fields_exist():
    record = OnboardingRecord(
        project_name="Desert Sun Plant",
        plant_type="solar",
        source_files=["site_form.pdf"],
        fields=[
            ExtractedField(name="project_name", raw_value="Desert Sun Plant", normalized_value="Desert Sun Plant", confidence=0.99, evidence=[], status="valid"),
            ExtractedField(name="plant_type", raw_value="solar", normalized_value="solar", confidence=0.99, evidence=[], status="valid"),
            ExtractedField(name="installed_capacity_mw", raw_value="120 MW", normalized_value=120.0, confidence=0.95, evidence=[], status="valid"),
            ExtractedField(name="site_name", raw_value="Desert Sun", normalized_value="Desert Sun", confidence=0.95, evidence=[], status="valid"),
            ExtractedField(name="site_location", raw_value="Arizona", normalized_value="Arizona", confidence=0.95, evidence=[], status="valid"),
            ExtractedField(name="interconnection_voltage_kv", raw_value="33", normalized_value=33, confidence=0.95, evidence=[], status="valid"),
            ExtractedField(name="inverter_manufacturer", raw_value="SMA", normalized_value="SMA", confidence=0.95, evidence=[], status="valid"),
            ExtractedField(name="inverter_model", raw_value="Sunny Central", normalized_value="Sunny Central", confidence=0.95, evidence=[], status="valid"),
            ExtractedField(name="module_manufacturer", raw_value="First Solar", normalized_value="First Solar", confidence=0.95, evidence=[], status="valid"),
            ExtractedField(name="module_model", raw_value="Series 6", normalized_value="Series 6", confidence=0.95, evidence=[], status="valid"),
        ],
        readiness_status="needs_review",
    )

    validated = validate_required_fields(record)

    assert validated.readiness_status == "needs_review"
    assert len(validated.validation_issues) == 0