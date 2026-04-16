from __future__ import annotations

from backend.services.learning_store import (
    delete_rule,
    get_rule,
    list_category,
    load_rules,
    upsert_header_mapping,
    upsert_model_alias,
    upsert_regex_override,
    upsert_unit_override,
    upsert_vendor_term,
)


def main() -> None:
    print("Saving sample rules...\n")

    upsert_header_mapping("Platform Name", "plant_name")
    upsert_header_mapping("Site Name", "plant_name")
    upsert_model_alias("CS6X-305", "Canadian Solar CS6X 305")
    upsert_unit_override("MWdc", "MW")
    upsert_vendor_term("Can. Solar", "Canadian Solar")
    upsert_regex_override("plant_capacity_dc", r"(\d+(?:\.\d+)?)\s*(kWdc|MWdc|kW|MW)")

    print("All rules:")
    print(load_rules())

    print("\nHeader mapping category:")
    print(list_category("header_mapping"))

    print("\nGet one rule:")
    print(get_rule("model_alias", "CS6X-305"))

    print("\nDelete one rule:")
    delete_rule("header_mapping", "Site Name")
    print(list_category("header_mapping"))


if __name__ == "__main__":
    main()