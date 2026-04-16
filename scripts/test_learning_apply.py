from __future__ import annotations

from backend.services.learning_apply import apply_learning_rule


def main() -> None:
    print("Apply header mapping")
    print(apply_learning_rule("header_mapping", "Project Name", "plant_name"))

    print("\nApply model alias")
    print(apply_learning_rule("model_alias", "CS3W-450", "Canadian Solar CS3W 450"))

    print("\nApply unit override")
    print(apply_learning_rule("unit_override", "kWp", "kWdc"))

    print("\nApply vendor term")
    print(apply_learning_rule("vendor_term", "SMA America", "SMA"))

    print("\nApply regex override")
    print(
        apply_learning_rule(
            "regex_override",
            "module_count",
            r"(\\d+)\\s*(modules|panels)",
        )
    )

    print("\nApply unsupported type")
    print(apply_learning_rule("other", "a", "b"))


if __name__ == "__main__":
    main()