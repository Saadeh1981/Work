from backend.services.builders.onboarding_record_builder import build_onboarding_record


def test_build_onboarding_record_from_raw_fields():
    raw_fields = [
        {
            "name": "installed_capacity_mw",
            "raw_value": "120 MW",
            "normalized_value": 120.0,
            "confidence": 0.96,
            "evidence": [
                {
                    "file_name": "site_form.pdf",
                    "page": 2,
                    "section": "Project Summary",
                    "snippet": "Installed Capacity: 120 MW",
                }
            ],
            "status": "valid",
        },
        {
            "name": "site_name",
            "raw_value": "Desert Sun",
            "normalized_value": "Desert Sun",
            "confidence": 0.93,
            "evidence": [],
            "status": "valid",
        },
    ]

    record = build_onboarding_record(
        project_name="Desert Sun Plant",
        plant_type="solar",
        source_files=["site_form.pdf"],
        raw_fields=raw_fields,
    )

    assert record.project_name == "Desert Sun Plant"
    assert record.plant_type == "solar"
    assert len(record.fields) == 2
    assert record.fields[0].name == "installed_capacity_mw"
    assert record.fields[0].confidence == 0.96
    assert record.fields[0].evidence[0].file_name == "site_form.pdf"
    assert record.readiness_status == "needs_review"