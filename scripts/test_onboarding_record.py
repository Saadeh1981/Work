from backend.schemas.onboarding_record import OnboardingRecord, ExtractedField, Evidence


def test_create_minimal_onboarding_record():
    record = OnboardingRecord(
        project_name="Desert Sun Plant",
        plant_type="solar",
        source_files=["site_form.pdf"],
        fields=[
            ExtractedField(
                name="installed_capacity_mw",
                raw_value="120 MW",
                normalized_value=120.0,
                confidence=0.96,
                evidence=[
                    Evidence(
                        file_name="site_form.pdf",
                        page=2,
                        section="Project Summary",
                        snippet="Installed Capacity: 120 MW"
                    )
                ],
                status="valid",
            )
        ],
        readiness_status="needs_review",
    )

    assert record.project_name == "Desert Sun Plant"
    assert record.plant_type == "solar"
    assert len(record.fields) == 1
    assert record.fields[0].name == "installed_capacity_mw"
    assert record.fields[0].confidence == 0.96