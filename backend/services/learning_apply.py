from __future__ import annotations

from typing import Any

from backend.services.learning_store import (
    upsert_header_mapping,
    upsert_model_alias,
    upsert_regex_override,
    upsert_unit_override,
    upsert_vendor_term,
)


def apply_learning_rule(
    rule_type: str,
    source_value: str,
    target_value: str,
) -> dict[str, Any]:
    if rule_type == "header_mapping":
        return upsert_header_mapping(source_value, target_value)

    if rule_type == "model_alias":
        return upsert_model_alias(source_value, target_value)

    if rule_type == "unit_override":
        return upsert_unit_override(source_value, target_value)

    if rule_type == "vendor_term":
        return upsert_vendor_term(source_value, target_value)

    if rule_type == "regex_override":
        return upsert_regex_override(source_value, target_value)

    return {
        "status": "error",
        "error": f"unsupported rule_type: {rule_type}",
    }