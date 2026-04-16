from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STORE_PATH = Path("data/learning_rules.json")


def load_rules() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return {}

    try:
        with open(STORE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
    except Exception:
        return {}


def save_rules(rules: dict[str, Any]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(STORE_PATH, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, ensure_ascii=False)


def save_rule(category: str, key: str, value: Any) -> dict[str, Any]:
    rules = load_rules()

    if category not in rules or not isinstance(rules.get(category), dict):
        rules[category] = {}

    rules[category][key] = value
    save_rules(rules)
    return rules


def get_rule(category: str, key: str, default: Any = None) -> Any:
    rules = load_rules()
    category_rules = rules.get(category, {})

    if not isinstance(category_rules, dict):
        return default

    return category_rules.get(key, default)


def delete_rule(category: str, key: str) -> dict[str, Any]:
    rules = load_rules()

    if category in rules and isinstance(rules[category], dict):
        rules[category].pop(key, None)

        if not rules[category]:
            rules.pop(category, None)

        save_rules(rules)

    return rules


def list_category(category: str) -> dict[str, Any]:
    rules = load_rules()
    category_rules = rules.get(category, {})

    if isinstance(category_rules, dict):
        return category_rules

    return {}


def upsert_header_mapping(source_header: str, target_field: str) -> dict[str, Any]:
    return save_rule("header_mapping", source_header, target_field)


def upsert_model_alias(source_model: str, canonical_model: str) -> dict[str, Any]:
    return save_rule("model_alias", source_model, canonical_model)


def upsert_unit_override(source_unit: str, normalized_unit: str) -> dict[str, Any]:
    return save_rule("unit_override", source_unit, normalized_unit)


def upsert_vendor_term(source_term: str, canonical_term: str) -> dict[str, Any]:
    return save_rule("vendor_term", source_term, canonical_term)


def upsert_regex_override(field_name: str, pattern: str) -> dict[str, Any]:
    return save_rule("regex_override", field_name, pattern)