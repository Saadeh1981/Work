from backend.config.required_fields import get_required_fields


def test_get_required_fields_for_solar():
    fields = get_required_fields("solar")

    assert "project_name" in fields
    assert "installed_capacity_mw" in fields
    assert "module_model" in fields


def test_get_required_fields_for_unknown_type():
    fields = get_required_fields("unknown")

    assert fields == []


def test_get_required_fields_is_case_insensitive():
    fields = get_required_fields("SoLaR")

    assert "project_name" in fields
    assert "site_location" in fields